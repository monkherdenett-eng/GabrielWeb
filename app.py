from flask import Flask, render_template, request, jsonify
import gspread
from datetime import datetime
import json
import os
import base64
import requests as http

app = Flask(__name__)

SCOPES = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
]

SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID', '')
SHEET_NAME = os.environ.get('SHEET_NAME', 'Бүртгэл')
HEADERS = ['Овог Нэр', 'Утасны дугаар', 'Имэйл', 'Бүртгүүлсэн огноо', 'Төлбөрийн арга', 'Төлбөрийн төлөв']

BYL_TOKEN = os.environ.get('BYL_TOKEN', '')
BYL_PROJECT_ID = os.environ.get('BYL_PROJECT_ID', '547')
BYL_BASE = 'https://byl.mn/api/v1'


def byl_headers():
    return {
        'Authorization': f'Bearer {BYL_TOKEN}',
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }


def get_sheet():
    creds_b64 = os.environ.get('GOOGLE_CREDENTIALS_B64', '')
    if creds_b64:
        creds_dict = json.loads(base64.b64decode(creds_b64).decode('utf-8'))
        client = gspread.service_account_from_dict(creds_dict)
    else:
        client = gspread.service_account(filename='credentials.json')
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    try:
        sheet = spreadsheet.worksheet(SHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=10)
        sheet.append_row(HEADERS)
    return sheet


def save_to_sheet(full_name, phone, email, method='byl.mn'):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    row = [full_name, phone, email, now, method, 'Төлөгдсөн']
    sheet = get_sheet()
    sheet.append_row(row)


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/api/create-invoice', methods=['POST'])
def create_invoice():
    data = request.get_json()
    full_name = (data.get('fullName') or '').strip()
    phone = (data.get('phone') or '').strip()
    email = (data.get('email') or '').strip()

    if not full_name or not phone:
        return jsonify({'success': False, 'error': 'Овог нэр болон утасны дугаар шаардлагатай'}), 400

    try:
        resp = http.post(
            f'{BYL_BASE}/projects/{BYL_PROJECT_ID}/invoices',
            json={
                'amount': 25000,
                'description': f'Семинарын бүртгэл - {full_name} ({phone})'
            },
            headers=byl_headers(),
            timeout=10
        )
        result = resp.json()
        if resp.status_code in (200, 201):
            return jsonify({'success': True, 'invoice': result})
        else:
            return jsonify({'success': False, 'error': str(result)}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/check-invoice/<invoice_id>', methods=['GET'])
def check_invoice(invoice_id):
    try:
        resp = http.get(
            f'{BYL_BASE}/projects/{BYL_PROJECT_ID}/invoices/{invoice_id}',
            headers=byl_headers(),
            timeout=10
        )
        result = resp.json()
        return jsonify({'success': True, 'invoice': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/webhook/byl', methods=['POST'])
def byl_webhook():
    data = request.get_json(silent=True) or {}
    app.logger.info(f'byl webhook: {data}')
    # Төлбөр амжилттай бол Google Sheets-т хадгалах
    status = data.get('status') or data.get('payment_status') or ''
    if status in ('paid', 'success', 'completed', 'PAID', 'SUCCESS'):
        meta = data.get('description', '')
        full_name = data.get('full_name', meta)
        phone = data.get('phone', '')
        email = data.get('email', '')
        try:
            save_to_sheet(full_name, phone, email, 'byl.mn')
        except Exception as e:
            app.logger.error(f'Sheet error on webhook: {e}')
    return jsonify({'success': True}), 200


@app.route('/api/save-registration', methods=['POST'])
def save_registration():
    data = request.get_json()
    full_name = (data.get('fullName') or '').strip()
    phone = (data.get('phone') or '').strip()
    email = (data.get('email') or '').strip()

    if not full_name or not phone:
        return jsonify({'success': False, 'error': 'Мэдээлэл дутуу байна'}), 400

    try:
        save_to_sheet(full_name, phone, email, 'byl.mn')
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f'Google Sheets error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
