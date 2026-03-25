import os
import json
import gspread
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from oauth2client.service_account import ServiceAccountCredentials
import requests
from datetime import datetime

app = Flask(__name__)
app.secret_key = "morevistas_secure_2026" 

# --- CONFIG (WhatsApp Number Fixed) ---
# Yeh settings aapke business alerts aur redirection ke liye hain.
TELEGRAM_TOKEN = "7913354522:AAH1XxMP1EMWC59fpZezM8zunZrWQcAqH18"
TELEGRAM_CHAT_ID = "6746178673"
WHATSAPP_NUMBER = "918830024994" # ✅ Fixed Business Number

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
            
            # Aapka Database Sheet ID
            SHEET_ID = "1wXlMNAUuW2Fr4L05ahxvUNn0yvMedcVosTRJzZf_1ao"
            main_spreadsheet = client.open_by_key(SHEET_ID)
            
            sheet = main_spreadsheet.sheet1
            all_ws = {ws.title: ws for ws in main_spreadsheet.worksheets()}
            
            # Sabhi worksheets ko link kiya gaya hai
            places_sheet = all_ws.get("Places")
            enquiry_sheet = all_ws.get("Enquiries")
            settings_sheet = all_ws.get("Settings")
            print("✅ All Sheets Linked Successfully")
        except Exception as e: 
            print(f"❌ Error: {e}")

init_sheets()

def get_rows(target_sheet):
    if not target_sheet: return []
    try:
        data = target_sheet.get_all_values()
        if not data or len(data) < 1: return []
        headers = [h.strip() for h in data[0]]
        final_list = []
        today_day = datetime.now().weekday()
        today_str = datetime.now().strftime("%Y-%m-%d") 
        
        for row in data[1:]:
            padded_row = row + [''] * (len(headers) - len(row))
            item = dict(zip(headers, padded_row))
            
            # --- 🗓️ Auto Sold Out Logic ---
            # Agar aaj ki date Sold_Dates mein hai, toh status badal jayega.
            if today_str in str(item.get('Sold_Dates', '')): 
                item['Status'] = 'Sold Out'

            def clean_p(key):
                val = str(item.get(key, '')).replace(',', '').replace('₹', '').strip()
                try: 
                    return int(float(val)) if val and val.lower() != 'nan' else 0
                except: 
                    return 0

            # Price data ko clean aur process kiya gaya hai
            item['Price'] = clean_p('Price')
            item['Original_Price'] = clean_p('Original_Price')
            item['Weekday_Price'] = clean_p('Weekday_Price')
            item['Weekend_Price'] = clean_p('Weekend_Price')
            
            # --- 💰 Dynamic Pricing Logic ---
            # Weekend (Fri-Sun) aur Weekday ke liye alag rates.
            p_base = item['Price']
            if today_day >= 4: 
                item['current_display_price'] = item['Weekend_Price'] if item['Weekend_Price'] > 0 else p_base
            else:
                item['current_display_price'] = item['Weekday_Price'] if item['Weekday_Price'] > 0 else p_base
            
            p, op = item['current_display_price'], item['Original_Price']
            item['amount_saved'] = op - p if op > p else 0
            
            # --- 📜 Rules Logic ---
            # Guidelines ko clean list mein convert kiya gaya hai.
            raw_rules = str(item.get('Rules', '')).strip()
            item['Rules_List'] = [r.strip() for r in (raw_rules.split('|') if '|' in raw_rules else raw_rules.split('•') if '•' in raw_rules else raw_rules.split('\n')) if r.strip()] if raw_rules else ["ID Proof Required"]
            
            item['Villa_ID'] = str(item.get('Villa_ID', '')).strip()
            final_list.append(item)
        return final_list
    except: 
        return []

# --- 🚀 Routes ---

@app.route('/')
def index():
    # Website ka main landing page
    settings = {'Banner_URL': settings_sheet.acell('B1').value, 'Offer_Text': settings_sheet.acell('B2').value, 'Banner_Show': settings_sheet.acell('B3').value} if settings_sheet else {}
    return render_template('index.html', villas=get_rows(sheet), tourist_places=get_rows(places_sheet), settings=settings)

@app.route('/enquiry/<villa_id>', methods=['GET', 'POST'])
def enquiry(villa_id):
    villas = get_rows(sheet)
    villa = next((v for v in villas if v.get('Villa_ID') == str(villa_id).strip()), None)
    
    if request.method == 'POST':
        name, phone = request.form.get('name'), request.form.get('phone')
        dates, guests = request.form.get('stay_dates'), request.form.get('guests')
        v_name = villa.get('Villa_Name', 'Villa')
        
        # 1. Google Sheet mein data save karein
        if enquiry_sheet: 
            enquiry_sheet.append_row([datetime.now().strftime("%d-%m-%Y %H:%M"), name, phone, dates, guests, v_name])
            
        # 2. Telegram Alert bhejein
        alert = f"🚀 *New Lead!*\n🏡 *Villa:* {v_name}\n👤 *Name:* {name}\n📞 *Phone:* {phone}\n📅 *Dates:* {dates}"
        requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", params={"chat_id": TELEGRAM_CHAT_ID, "text": alert, "parse_mode": "Markdown"})
        
        # 3. ✅ THE MAGIC REDIRECT: Pehle lead save, phir WhatsApp redirect
        msg = f"Hi MoreVistas, I want to book {v_name} for {guests} guests on {dates}. My name is {name}."
        return redirect(f"https://wa.me/{WHATSAPP_NUMBER}?text={requests.utils.quote(msg)}")
        
    return render_template('enquiry.html', villa=villa)

@app.route('/admin')
def admin_dashboard():
    # Admin control panel
    if not session.get('logged_in'): 
        return redirect(url_for('admin_login'))
    return render_template('admin_dashboard.html', villas=get_rows(sheet), enquiries=get_rows(enquiry_sheet)[-10:], settings={})

# Baki routes jaise admin-login, logout, etc. aapke existing logic par chalenge.

if __name__ == '__main__':
    # Render deployment ke liye zaroori port configuration
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
    
