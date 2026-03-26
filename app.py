import os
import json
import gspread
import requests
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

app = Flask(__name__)
app.secret_key = "morevistas_secure_2026" 

# --- UPDATED CONFIG ---
# Aapka primary contact hamesha sync rahega
CONTACT_PRIMARY = "8830024994" 
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
            print("✅ All Sheets Linked Successfully")
        except Exception as e:
            print(f"❌ Sheet Init Error: {e}")

init_sheets()

# --- NEW FUNCTION: SMART PRICE & RULES CLEANER ---
def process_villa_data(headers, row):
    item = dict(zip(headers, row + [''] * (len(headers) - len(row))))
    today_day = datetime.now().weekday()
    today_str = datetime.now().strftime("%Y-%m-%d")

    # 1. Auto Sold Out Logic[span_0](start_span)[span_0](end_span)
    if today_str in str(item.get('Sold_Dates', '')).strip():
        item['Status'] = 'Sold Out'

    # 2. Advanced Price Cleaning[span_1](start_span)[span_1](end_span)
    def clean_p(key):
        val = str(item.get(key, '')).replace(',', '').replace('₹', '').strip()
        if not val or val.lower() == 'nan' or val == '0': return 0
        try: return int(float(val))
        except: return 0

    item['Price'] = clean_p('Price')
    item['Original_Price'] = clean_p('Original_Price')
    item['Weekday_Price'] = clean_p('Weekday_Price')
    item['Weekend_Price'] = clean_p('Weekend_Price')
    
    # 3. Dynamic Display Logic (Fri, Sat, Sun are Weekends)[span_2](start_span)[span_2](end_span)
    p_base = item['Price']
    if today_day >= 4:
        item['current_display_price'] = item['Weekend_Price'] if item['Weekend_Price'] > 0 else p_base
    else:
        item['current_display_price'] = item['Weekday_Price'] if item['Weekday_Price'] > 0 else p_base

    # 4. Savings Calculator[span_3](start_span)[span_3](end_span)
    p = item['current_display_price']
    op = item['Original_Price']
    item['amount_saved'] = op - p if op > p else 0
    item['discount_perc'] = int(((op - p) / op) * 100) if op > p > 0 else 0

    return item

def get_rows(target_sheet):
    if not target_sheet: return []
    try:
        data = target_sheet.get_all_values()
        if not data or len(data) < 1: return []
        headers = [h.strip() for h in data[0]]
        return [process_villa_data(headers, row) for row in data[1:]]
    except Exception as e:
        print(f"Error: {e}")
        return []

# --- UPDATED ROUTES ---

@app.route('/')
def index():
    villas = get_rows(sheet)
    # Target Settings Specifically to avoid cell shifting[span_4](start_span)[span_4](end_span)
    settings = {'Banner_URL': "", 'Offer_Text': "", 'Banner_Show': 'FALSE'}
    if settings_sheet:
        try:
            settings['Banner_URL'] = settings_sheet.acell('B1').value
            settings['Offer_Text'] = settings_sheet.acell('B2').value
            settings['Banner_Show'] = settings_sheet.acell('B3').value
        except: pass
    return render_template('index.html', villas=villas, settings=settings, contact=CONTACT_PRIMARY)

@app.route('/enquiry/<villa_id>', methods=['POST'])
def submit_enquiry(villa_id):
    # Improved Telegram formatting for better readability[span_5](start_span)[span_5](end_span)
    name, phone = request.form.get('name'), request.form.get('phone')
    dates, guests = request.form.get('stay_dates'), request.form.get('guests')
    villa_name = request.form.get('villa_name', 'Luxury Villa')
    
    if enquiry_sheet:
        enquiry_sheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), name, phone, dates, guests, villa_name])
    
    alert = (f"🏰 *MOREVISTAS BOOKING*\n"
             f"━━━━━━━━━━━━━━━━\n"
             f"🏡 *Villa:* {villa_name}\n"
             f"👤 *Guest:* {name}\n"
             f"📞 *Call:* {phone}\n"
             f"📅 *Dates:* {dates}\n"
             f"👥 *Total:* {guests} Guests")
    
    requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                 params={"chat_id": TELEGRAM_CHAT_ID, "text": alert, "parse_mode": "Markdown"})
    return render_template('success.html', name=name)

# Admin logic is kept secure[span_6](start_span)[span_6](end_span)
@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USER and request.form.get('password') == ADMIN_PASS:
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
    return render_template('admin_login.html')

# Render deployment optimization[span_7](start_span)[span_7](end_span)
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
    
