import os
import json
import gspread
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from oauth2client.service_account import ServiceAccountCredentials
import requests
from datetime import datetime

app = Flask(__name__)
app.secret_key = "morevistas_secure_2026_premium" 

# --- CONFIG ---
TELEGRAM_TOKEN = "7913354522:AAH1XxMP1EMWC59fpZezM8zunZrWQcAqH18"
TELEGRAM_CHAT_ID = "6746178673"
WHATSAPP_NUMBER = "918830024994"
MY_COMMISSION = 1.20 

ADMIN_USER = "Admin"
ADMIN_PASS = "MV@2026" 

# --- Google Sheets Setup ---
creds_json = os.environ.get('GOOGLE_CREDS')
sheet, places_sheet, enquiry_sheet, settings_sheet = None, None, None, None

def init_sheets():
    global sheet, places_sheet, enquiry_sheet, settings_sheet
    if creds_json:
        try:
            info = json.loads(creds_json)
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(info, scope)
            client = gspread.authorize(creds)
            SHEET_ID = "1wXlMNAUuW2Fr4L05ahxvUNn0yvMedcVosTRJzZf_1ao"
            main_spreadsheet = client.open_by_key(SHEET_ID)
            
            sheet = main_spreadsheet.worksheet("Villas")
            places_sheet = main_spreadsheet.worksheet("Places")
            enquiry_sheet = main_spreadsheet.worksheet("Enquiries")
            settings_sheet = main_spreadsheet.worksheet("Settings")
            print("✅ MoreVistas Business Engine Connected")
        except Exception as e: print(f"❌ Error: {e}")

init_sheets()

def get_rows(target_sheet):
    if not target_sheet: return []
    try:
        data = target_sheet.get_all_values()
        if not data or len(data) < 1: return []
        headers = [h.strip() for h in data[0]]
        final_list = []
        
        for row in data[1:]:
            padded_row = row + [''] * (len(headers) - len(row))
            item = dict(zip(headers, padded_row))
            
            # --- 💰 PRICING & SAVINGS LOGIC (Fixed for Templates) ---
            try:
                v_price = str(item.get('Price', '0')).replace(',', '').strip()
                vendor_base = int(float(v_price)) if v_price and v_price.lower() != 'nan' else 0
                
                # Commission Logic
                if item.get('Owner_ID', '').startswith('OWN'):
                    item['current_display_price'] = int(vendor_base * MY_COMMISSION)
                else:
                    item['current_display_price'] = vendor_base
                
                # amount_saved logic to prevent crash
                op = str(item.get('Original_Price', '0')).replace(',', '').strip()
                orig_p = int(float(op)) if op and op.lower() != 'nan' else 0
                item['Original_Price'] = orig_p
                item['amount_saved'] = orig_p - item['current_display_price'] if orig_p > item['current_display_price'] else 0
                
                item['is_on_request'] = True if vendor_base <= 0 else False
            except:
                item['current_display_price'] = 0
                item['amount_saved'] = 0
                item['is_on_request'] = True

            # Rules Logic (Split logic for messy lists)
            raw_rules = str(item.get('Rules', '')).strip()
            item['Rules_List'] = [r.strip() for r in (raw_rules.split('|') if '|' in raw_rules else raw_rules.split('\n')) if r.strip()]
            
            item['Villa_ID'] = str(item.get('Villa_ID', '')).strip()
            final_list.append(item)
        return final_list
    except: return []

# --- 🚀 PUBLIC ROUTES (Fixes 404 Errors) ---

@app.route('/')
def index():
    villas = get_rows(sheet)
    places = get_rows(places_sheet)
    settings = {'Banner_URL': '', 'Offer_Text': '', 'Banner_Show': 'FALSE'}
    if settings_sheet:
        try:
            settings = {'Banner_URL': settings_sheet.acell('B1').value, 'Offer_Text': settings_sheet.acell('B2').value, 'Banner_Show': settings_sheet.acell('B3').value}
        except: pass
    return render_template('index.html', villas=villas, tourist_places=places, settings=settings)

@app.route('/explore')
def explore():
    return render_template('explore.html', tourist_places=get_rows(places_sheet))

@app.route('/list-property')
def list_property():
    return render_template('list_property.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/legal')
def legal():
    return render_template('legal.html')

@app.route('/villa/<villa_id>')
def villa_details(villa_id):
    villas = get_rows(sheet)
    villa = next((v for v in villas if v.get('Villa_ID') == str(villa_id).strip()), None)
    if not villa: return redirect(url_for('index'))
    # Gallery Fix
    imgs = [villa.get('Image_URL')]
    for i in range(2, 12):
        if villa.get(f'Image_URL_{i}'): imgs.append(villa.get(f'Image_URL_{i}'))
    return render_template('villa_details.html', villa=villa, villa_images=imgs)

@app.route('/enquiry/<villa_id>', methods=['GET', 'POST'])
def enquiry(villa_id):
    villas = get_rows(sheet)
    villa = next((v for v in villas if v.get('Villa_ID') == str(villa_id).strip()), None)
    if request.method == 'POST':
        name, phone = request.form.get('name'), request.form.get('phone')
        dates, guests = request.form.get('stay_dates'), request.form.get('guests')
        v_name = villa.get('Villa_Name', 'Villa')
        if enquiry_sheet:
            enquiry_sheet.append_row([datetime.now().strftime("%d-%m-%Y %H:%M"), name, phone, dates, guests, v_name])
        alert = f"🚀 *New Lead!*\n🏡 *Villa:* {v_name}\n👤 *Name:* {name}\n📞 *Phone:* {phone}\n📅 *Dates:* {dates}"
        requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", params={"chat_id": TELEGRAM_CHAT_ID, "text": alert, "parse_mode": "Markdown"})
        return redirect(f"https://wa.me/{WHATSAPP_NUMBER}?text=Hi,%20I%20want%20to%20book%20{v_name}")
    return render_template('enquiry.html', villa=villa)

# --- 🔐 ADMIN SECTION ---

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USER and request.form.get('password') == ADMIN_PASS:
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
    return render_template('admin_login.html')

@app.route('/admin')
def admin_dashboard():
    if not session.get('logged_in'): return redirect(url_for('admin_login'))
    villas = get_rows(sheet)
    return render_template('admin_dashboard.html', villas=villas, enquiries=get_rows(enquiry_sheet)[-20:][::-1])

@app.route('/admin-logout')
def admin_logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
    
