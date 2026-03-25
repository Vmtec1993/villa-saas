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
            
            # Pricing & Commission Logic
            if target_sheet == sheet:
                try:
                    v_price = str(item.get('Price', '0')).replace(',', '').strip()
                    vendor_base = int(float(v_price)) if v_price and v_price.lower() != 'nan' else 0
                    if item.get('Owner_ID', '').startswith('OWN'):
                        item['current_display_price'] = int(vendor_base * MY_COMMISSION)
                    else:
                        item['current_display_price'] = vendor_base
                    
                    op = str(item.get('Original_Price', '0')).replace(',', '').strip()
                    item['amount_saved'] = int(float(op)) - item['current_display_price'] if int(float(op)) > item['current_display_price'] else 0
                except: item['current_display_price'] = 0
            
            final_list.append(item)
        return final_list
    except: return []

# --- 🚀 PUBLIC ROUTES ---
@app.route('/')
def index():
    settings = {'Banner_URL': settings_sheet.acell('B1').value, 'Offer_Text': settings_sheet.acell('B2').value, 'Banner_Show': settings_sheet.acell('B3').value}
    return render_template('index.html', villas=get_rows(sheet), tourist_places=get_rows(places_sheet), settings=settings)

# --- 🔐 ADMIN ACTIONS (DELETE/ADD/CLEAR) ---

@app.route('/admin-action/<target>/<action>/<id>')
def admin_action(target, action, id):
    if not session.get('logged_in'): return redirect(url_for('admin_login'))
    
    # Target Selection
    t_sheet = sheet if target == 'villa' else places_sheet
    col_name = 'Villa_ID' if target == 'villa' else 'Place_Name'
    
    data = t_sheet.get_all_values()
    headers = data[0]
    
    if action == 'delete':
        for i, row in enumerate(data[1:], start=2):
            if str(row[headers.index(col_name)]).strip() == str(id).strip():
                t_sheet.delete_rows(i)
                break
    return redirect(url_for('admin_dashboard'))

@app.route('/add-place', methods=['POST'])
def add_place():
    if not session.get('logged_in'): return redirect(url_for('admin_login'))
    places_sheet.append_row([request.form.get('Place_Name'), request.form.get('Image_URL'), request.form.get('Description')])
    return redirect(url_for('admin_dashboard'))

@app.route('/clear-enquiries')
def clear_enquiries():
    if not session.get('logged_in'): return redirect(url_for('admin_login'))
    enquiry_sheet.resize(rows=1)
    return redirect(url_for('admin_dashboard'))

@app.route('/admin')
def admin_dashboard():
    if not session.get('logged_in'): return redirect(url_for('admin_login'))
    return render_template('admin_dashboard.html', villas=get_rows(sheet), tourist_places=get_rows(places_sheet), enquiries=get_rows(enquiry_sheet)[-20:][::-1])

# ... (Include original login/logout routes from your code)
