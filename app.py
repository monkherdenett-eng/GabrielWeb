from flask import Flask, render_template, request, jsonify
import gspread
from datetime import datetime
import json
import os
import base64
import requests as http
import hmac
import hashlib

app = Flask(__name__)

SCOPES = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
]

SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID', '')
SHEET_NAME = os.environ.get('SHEET_NAME', 'Бүртгэл')
HEADERS = ['Овог Нэр', 'Утасны дугаар', 'Имэйл', 'Бүртгүүлсэн огноо', 'Төлбөрийн арга', 'Төлбөрийн төлөв']

BYL_BASE = 'https://byl.mn/api/v1'


def byl_headers():
    token = os.environ.get('BYL_TOKEN', '')
    return {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }


def byl_project():
    return os.environ.get('BYL_PROJECT_ID', '547')


def byl_price():
    return os.environ.get('BYL_PRICE_ID', '1555')


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


@app.route('/api/debug')
def debug():
    token = os.environ.get('BYL_TOKEN', '')
    results = {
        'BYL_TOKEN': f'SET ({len(token)} chars)' if token else 'NOT SET',
        'BYL_PROJECT_ID': os.environ.get('BYL_PROJECT_ID', 'NOT SET'),
        'BYL_PRICE_ID': os.environ.get('BYL_PRICE_ID', 'NOT SET'),
        'SPREADSHEET_ID': os.environ.get('SPREADSHEET_ID', 'NOT SET'),
        'GOOGLE_CREDENTIALS_B64': 'SET' if os.environ.get('GOOGLE_CREDENTIALS_B64') else 'NOT SET',
    }
    try:
        r = http.get(f'{BYL_BASE}/projects/{byl_project()}',
                     headers=byl_headers(), timeout=5)
        results['byl_api'] = f'{r.status_code}: {r.text[:150]}'
    except Exception as e:
        results['byl_api_error'] = str(e)
    return jsonify(results)


@app.route('/api/create-invoice', methods=['POST'])
def create_invoice():
    data = request.get_json()
    full_name = (data.get('fullName') or '').strip()
    phone = (data.get('phone') or '').strip()
    email = (data.get('email') or '').strip()

    if not full_name or not phone:
        return jsonify({'success': False, 'error': 'Овог нэр болон утасны дугаар шаардлагатай'}), 400

    try:
        payload = {
            'items': [{'price_id': byl_price(), 'quantity': 1}],
            'customer_email': email,
            'phone_number_collection': True,
            'client_reference_id': phone,
        }
        resp = http.post(
            f'{BYL_BASE}/projects/{byl_project()}/checkouts',
            json=payload,
            headers=byl_headers(),
            timeout=10
        )
        result = resp.json()
        app.logger.info(f'byl.mn response {resp.status_code}: {result}')
        if resp.status_code in (200, 201):
            # response: { data: { id, url, status, amount_total } }
            data = result.get('data', result)
            return jsonify({'success': True, 'invoice': data})
        else:
            return jsonify({'success': False, 'error': str(result)}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/check-invoice/<invoice_id>', methods=['GET'])
def check_invoice(invoice_id):
    try:
        resp = http.get(
            f'{BYL_BASE}/projects/{byl_project()}/checkouts/{invoice_id}',
            headers=byl_headers(),
            timeout=10
        )
        result = resp.json()
        return jsonify({'success': True, 'invoice': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/webhook/byl', methods=['POST'])
def byl_webhook():
    secret = os.environ.get('BYL_WEBHOOK_SECRET', '')
    if secret:
        sig = request.headers.get('X-Byl-Signature') or request.headers.get('X-Signature') or ''
        body = request.get_data()
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if sig and not hmac.compare_digest(expected, sig):
            return jsonify({'error': 'Invalid signature'}), 401

    data = request.get_json(silent=True) or {}
    app.logger.info(f'byl webhook: {data}')

    status = (data.get('status') or data.get('payment_status') or '').lower()
    if status in ('paid', 'success', 'completed', 'complete'):
        customer = data.get('customer') or {}
        full_name = customer.get('name') or data.get('customer_name') or data.get('full_name', '')
        phone = customer.get('phone') or data.get('customer_phone') or data.get('phone', '')
        email = customer.get('email') or data.get('customer_email') or data.get('email', '')
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
