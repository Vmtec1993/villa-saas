import os
import json
import gspread
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from oauth2client.service_account import ServiceAccountCredentials
import requests
from datetime import datetime
import urllib.parse

app = Flask(__name__)
app.secret_key = "morevistas_secure_2026" 

# --- CONFIG ---
TELEGRAM_TOKEN = "7913354522:AAH1XxMP1EMWC59fpZezM8zunZrWQcAqH18"
TELEGRAM_CHAT_ID = "6746178673"

ADMIN_USER = "Admin"
ADMIN_PASS = "MV@2026" 

# --- Google Sheets Setup ---
creds_json = os.environ.get('GOOGLE_CREDS')
sheet = None
places_sheet = None
enquiry_sheet = None
settings_sheet = None
vendor_sheet = None 

def init_sheets():
    global sheet, places_sheet, enquiry_sheet, settings_sheet, vendor_sheet
    if creds_json:
        try:
            info = json.loads(creds_json)
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(info, scope)
            client = gspread.authorize(creds)
            
            SHEET_ID = "1wXlMNAUuW2Fr4L05ahxvUNn0yvMedcVosTRJzZf_1ao"
            main_spreadsheet = client.open_by_key(SHEET_ID)
            
            sheet = main_spreadsheet.sheet1
            all_ws = {ws.title: ws for ws in main_spreadsheet.worksheets()}
            
            places_sheet = all_ws.get("Places")
            enquiry_sheet = all_ws.get("Enquiries")
            settings_sheet = all_ws.get("Settings")
            vendor_sheet = all_ws.get("Vendors") 
            print("✅ All Sheets Linked Successfully")
        except Exception as e:
            print(f"❌ Sheet Init Error: {e}")

init_sheets()

# ✅ FIXED: get_rows function to handle "None" values and spaces
def get_rows(target_sheet):
    if not target_sheet: return []
    try:
        data = target_sheet.get_all_values()
        if not data or len(data) < 1: return []
        
        # Headers ko clean karein (spaces hata dein)
        headers = [h.strip() for h in data[0]]
        final_list = []
        
        today_day = datetime.now().weekday()
        today_str = datetime.now().strftime("%Y-%m-%d") 
        
        for row in data[1:]:
            padded_row = row + [''] * (len(headers) - len(row))
            # Sabhi keys/values ko clean karein
            item = {k: v.strip() for k, v in zip(headers, padded_row)}
            
            # --- Status Check ---
            sold_dates_str = str(item.get('Sold_Dates', '')).strip()
            if today_str in sold_dates_str:
                item['Status'] = 'Sold Out'

            # --- Price Cleaning ---
            def clean_p(key):
                val = str(item.get(key, '')).replace(',', '').replace('₹', '').strip()
                if not val or val.lower() == 'nan' or val == '0' or val.lower() == 'none':
                    return 0
                try: return int(float(val))
                except: return 0

            # Price calculations (sirf un sheets ke liye jahan prices hain)
            if 'Price' in item:
                try:
                    item['Price'] = clean_p('Price')
                    item['Original_Price'] = clean_p('Original_Price')
                    item['Weekday_Price'] = clean_p('Weekday_Price')
                    item['Weekend_Price'] = clean_p('Weekend_Price')
                    
                    p_base = item['Price']
                    if today_day >= 4: 
                        item['current_display_price'] = item['Weekend_Price'] if item['Weekend_Price'] > 0 else p_base
                    else:
                        item['current_display_price'] = item['Weekday_Price'] if item['Weekday_Price'] > 0 else p_base
                    
                    p = item['current_display_price']
                    op = item['Original_Price']
                    item['amount_saved'] = op - p if op > p else 0
                    item['discount_perc'] = int(((op - p) / op) * 100) if op > p > 0 else 0
                except: pass

            # Rules logic
            raw_rules = str(item.get('Rules', '')).strip()
            if raw_rules:
                item['Rules_List'] = [r.strip() for r in raw_rules.replace('|','\n').replace('•','\n').split('\n') if r.strip()]
            else:
                item['Rules_List'] = ["ID Proof Required", "Standard Rules Apply"]

            item['Villa_ID'] = str(item.get('Villa_ID', '')).strip()
            final_list.append(item)
        return final_list
    except Exception as e:
        print(f"Error in get_rows: {e}")
        return []

# --- ROUTES ---

@app.route('/')
def index():
    villas = get_rows(sheet)
    places = get_rows(places_sheet)
    settings = {'Offer_Text': "Welcome", 'Banner_URL': "", 'Banner_Show': 'FALSE'}
    if settings_sheet:
        try:
            s_data = settings_sheet.get_all_values()
            for r in s_data:
                if len(r) >= 2: settings[r[0].strip()] = r[1].strip()
        except: pass
    return render_template('index.html', villas=villas, tourist_places=places, settings=settings)

@app.route('/vendor-onboarding', methods=['GET', 'POST'])
def vendor_onboarding():
    if request.method == 'POST':
        # Form se data uthana (Ensuring names match HTML)
        o_name = request.form.get('owner_name')
        phone = request.form.get('phone')
        v_name = request.form.get('villa_name')
        loc = request.form.get('location')
        rent = request.form.get('expected_rent')
        amen = request.form.get('amenities')
        
        v_data = [datetime.now().strftime("%d-%m-%Y %H:%M"), o_name, phone, v_name, loc, rent, amen]
        
        if vendor_sheet:
            try: vendor_sheet.append_row(v_data)
            except: pass
        
        v_alert = f"💼 *New Partner Request!*\n👤 *Owner:* {o_name}\n📞 *Phone:* {phone}\n🏡 *Villa:* {v_name}\n📍 *Loc:* {loc}\n💰 *Rent:* {rent}"
        try:
            requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", params={"chat_id": TELEGRAM_CHAT_ID, "text": v_alert, "parse_mode": "Markdown"})
        except: pass
        return render_template('list_property_success.html', name=o_name)
    return render_template('vendor_form.html')

@app.route('/villa/<villa_id>')
def villa_details(villa_id):
    villas = get_rows(sheet)
    villa = next((v for v in villas if v.get('Villa_ID') == str(villa_id).strip()), None)
    if not villa: return "Villa Not Found", 404
    imgs = [villa.get(f'Image_URL_{i}') for i in range(1, 21) if villa.get(f'Image_URL_{i}')]
    if not imgs: imgs = [villa.get('Image_URL')]
    return render_template('villa_details.html', villa=villa, villa_images=imgs)

@app.route('/enquiry/<villa_id>', methods=['GET', 'POST'])
def enquiry(villa_id):
    villas = get_rows(sheet)
    villa = next((v for v in villas if v.get('Villa_ID') == str(villa_id).strip()), None)
    
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        dates = request.form.get('stay_dates') 
        guests = request.form.get('guests')
        v_name = villa.get('Villa_Name', 'Villa') if villa else "Villa"
        
        if enquiry_sheet:
            try: enquiry_sheet.append_row([datetime.now().strftime("%d-%m-%Y %H:%M"), name, phone, dates, guests, v_name])
            except: pass
            
        alert = f"🚀 *New Enquiry!*\n🏡 *Villa:* {v_name}\n👤 *Name:* {name}\n📞 *Phone:* {phone}\n📅 *Dates:* {dates}\n👥 *Guests:* {guests}"
        try:
            requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", params={"chat_id": TELEGRAM_CHAT_ID, "text": alert, "parse_mode": "Markdown"})
        except: pass
        
        whatsapp_msg = f"Hi MoreVistas, I am *{name}*.\nI want to enquire about *{v_name}* 🏡\n📅 *Dates:* {dates}\n👥 *Guests:* {guests}"
        encoded_msg = urllib.parse.quote(whatsapp_msg)
        return redirect(f"https://wa.me/918830024994?text={encoded_msg}")
        
    return render_template('enquiry.html', villa=villa)

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USER and request.form.get('password') == ADMIN_PASS:
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        error = "Invalid Credentials"
    return render_template('admin_login.html', error=error)

@app.route('/admin')
def admin_dashboard():
    if not session.get('logged_in'): return redirect(url_for('admin_login'))
    villas = get_rows(sheet)
    enquiries = get_rows(enquiry_sheet)[-15:] # Latest 15
    vendors = get_rows(vendor_sheet)[-15:]  # Latest 15
    
    settings = {}
    if settings_sheet:
        try:
            for r in settings_sheet.get_all_values():
                if len(r) >= 2: settings[r[0].strip()] = r[1].strip()
        except: pass
    return render_template('admin_dashboard.html', villas=villas, enquiries=enquiries, vendors=vendors, settings=settings)

@app.route('/admin-logout')
def admin_logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

@app.route('/update-settings', methods=['POST'])
def update_settings():
    if not session.get('logged_in'): return redirect(url_for('admin_login'))
    if settings_sheet:
        try:
            settings_sheet.update('B1', request.form.get('banner_url'))
            settings_sheet.update('B2', request.form.get('offer_text'))
            show = "TRUE" if request.form.get('banner_show') else "FALSE"
            settings_sheet.update('B3', show)
        except: pass
    return redirect(url_for('admin_dashboard'))

@app.route('/update-offline-dates', methods=['POST'])
def update_offline_dates():
    if not session.get('logged_in'): return redirect(url_for('admin_login'))
    v_id = request.form.get('Villa_ID')
    s_dates = request.form.get('Sold_Dates')
    if sheet:
        try:
            data = sheet.get_all_values()
            headers = data[0]
            id_idx = headers.index('Villa_ID')
            sold_idx = headers.index('Sold_Dates')
            for i, row in enumerate(data[1:], start=2):
                if str(row[id_idx]).strip() == str(v_id).strip():
                    sheet.update_cell(i, sold_idx + 1, s_dates)
                    break
        except: pass
    return redirect(url_for('admin_dashboard'))

@app.route('/update-full-villa', methods=['POST'])
def update_full_villa():
    if not session.get('logged_in'): return redirect(url_for('admin_login'))
    v_id = request.form.get('Villa_ID')
    updates = {
        'Villa_Name': request.form.get('Villa_Name'),
        'BHK': request.form.get('BHK'),
        'Status': request.form.get('Status'),
        'Original_Price': request.form.get('Original_Price', '').strip(),
        'Weekday_Price': request.form.get('Weekday_Price', '').strip(),
        'Weekend_Price': request.form.get('Weekend_Price', '').strip(),
        'Amenities': request.form.get('Amenities'),
        'Rules': request.form.get('Rules')
    }
    if sheet:
        try:
            data = sheet.get_all_values()
            headers = data[0]
            id_idx = headers.index('Villa_ID')
            for i, row in enumerate(data[1:], start=2):
                if str(row[id_idx]).strip() == str(v_id).strip():
                    for key, val in updates.items():
                        if key in headers:
                            sheet.update_cell(i, headers.index(key)+1, val)
                    break
        except: pass
    return redirect(url_for('admin_dashboard'))

@app.route('/quick-status-update', methods=['POST'])
def quick_status_update():
    if not session.get('logged_in'): return redirect(url_for('admin_login'))
    v_id = request.form.get('Villa_ID')
    curr = request.form.get('current_status')
    new_status = "Sold Out" if curr.lower() == 'available' else "Available"
    if sheet:
        try:
            data = sheet.get_all_values()
            headers = data[0]
            idx = headers.index('Villa_ID')
            st_idx = headers.index('Status')
            for i, row in enumerate(data[1:], start=2):
                if str(row[idx]).strip() == str(v_id).strip():
                    sheet.update_cell(i, st_idx + 1, new_status)
                    break
        except: pass
    return redirect(url_for('admin_dashboard'))

@app.route('/explore')
def explore(): return render_template('explore.html', tourist_places=get_rows(places_sheet))

@app.route('/contact')
def contact(): return render_template('contact.html')

@app.route('/legal')
def legal(): return render_template('legal.html')

@app.route('/list-property')
def list_property(): return render_template('list_property.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
            
