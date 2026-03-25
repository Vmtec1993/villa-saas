import os
import json
import gspread
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from oauth2client.service_account import ServiceAccountCredentials
import requests
from datetime import datetime

app = Flask(__name__)
app.secret_key = "morevistas_secure_2026" 

# --- CONFIG (WhatsApp Number: 8830024994) ---
TELEGRAM_TOKEN = "7913354522:AAH1XxMP1EMWC59fpZezM8zunZrWQcAqH18"
TELEGRAM_CHAT_ID = "6746178673"
WHATSAPP_NUMBER = "918830024994" 

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
            sheet = main_spreadsheet.sheet1
            all_ws = {ws.title: ws for ws in main_spreadsheet.worksheets()}
            places_sheet = all_ws.get("Places")
            enquiry_sheet = all_ws.get("Enquiries")
            settings_sheet = all_ws.get("Settings")
            print("✅ All Sheets Linked")
        except Exception as e: print(f"❌ Error: {e}")

init_sheets()

def get_rows(target_sheet):
    if not target_sheet: return []
    try:
        data = target_sheet.get_all_values()
        if not data or len(data) < 1: return []
        headers = [h.strip() for h in data[0]]
        final_list = []
        today_day = datetime.now().weekday()
        for row in data[1:]:
            padded_row = row + [''] * (len(headers) - len(row))
            item = dict(zip(headers, padded_row))
            
            # --- 💰 Pricing & amount_saved Fix ---
            try:
                p = int(str(item.get('Price', '0')).replace(',', '').strip())
                op = int(str(item.get('Original_Price', '0')).replace(',', '').strip())
                item['Original_Price'] = op
                
                wd = int(str(item.get('Weekday_Price', '0')).replace(',', '').strip())
                we = int(str(item.get('Weekend_Price', '0')).replace(',', '').strip())
                
                if today_day >= 4: # Fri-Sun
                    item['current_display_price'] = we if we > 0 else p
                else:
                    item['current_display_price'] = wd if wd > 0 else p
                
                item['amount_saved'] = op - item['current_display_price'] if op > item['current_display_price'] else 0
            except:
                item['current_display_price'] = 0
                item['amount_saved'] = 0

            raw_rules = str(item.get('Rules', '')).strip()
            item['Rules_List'] = [r.strip() for r in (raw_rules.split('|') if '|' in raw_rules else raw_rules.split('\n')) if r.strip()]
            item['Villa_ID'] = str(item.get('Villa_ID', '')).strip()
            final_list.append(item)
        return final_list
    except: return []

# --- 🚀 Routes ---

@app.route('/')
def index():
    villas = get_rows(sheet)
    places = get_rows(places_sheet)
    settings = {}
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
    imgs = [villa.get(f'Image_URL_{i}') for i in range(1, 11) if villa.get(f'Image_URL_{i}')]
    if not imgs or not imgs[0]: imgs = [villa.get('Image_URL')]
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
        
        msg = f"Hi MoreVistas, I want to book {v_name} for {guests} guests on {dates}. My name is {name}."
        return redirect(f"https://wa.me/{WHATSAPP_NUMBER}?text={requests.utils.quote(msg)}")
    return render_template('enquiry.html', villa=villa)

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
    return render_template('admin_dashboard.html', villas=get_rows(sheet), enquiries=get_rows(enquiry_sheet)[-20:][::-1])

@app.route('/admin-logout')
def admin_logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
    
