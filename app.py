from flask import Flask, render_template, request, jsonify
import gspread
from datetime import datetime
import json
import os
import base64

app = Flask(__name__)

SCOPES = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
]

SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID', '')
SHEET_NAME = os.environ.get('SHEET_NAME', 'Бүртгэл')

HEADERS = ['Овог Нэр', 'Утасны дугаар', 'Имэйл', 'Бүртгүүлсэн огноо', 'Төлбөрийн арга', 'Төлбөрийн төлөв']


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


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/api/debug')
def debug():
    import sys
    results = {}
    results['python'] = sys.version
    results['SPREADSHEET_ID'] = os.environ.get('SPREADSHEET_ID', 'NOT SET')
    results['SHEET_NAME'] = os.environ.get('SHEET_NAME', 'NOT SET')
    creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON', '')
    results['CREDENTIALS'] = 'SET' if creds_json else 'NOT SET'
    try:
        import gspread
        results['gspread'] = gspread.__version__
    except Exception as e:
        results['gspread'] = f'ERROR: {e}'
    try:
        sheet = get_sheet()
        results['sheet'] = f'OK: {sheet.title}'
    except Exception as e:
        results['sheet_error'] = str(e)
    return jsonify(results)


@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    full_name = (data.get('fullName') or '').strip()
    phone = (data.get('phone') or '').strip()

    if not full_name or not phone:
        return jsonify({'success': False, 'error': 'Овог нэр болон утасны дугаар шаардлагатай'}), 400

    return jsonify({'success': True})


@app.route('/api/save-registration', methods=['POST'])
def save_registration():
    data = request.get_json()
    full_name = (data.get('fullName') or '').strip()
    phone = (data.get('phone') or '').strip()
    email = (data.get('email') or '').strip()

    if not full_name or not phone:
        return jsonify({'success': False, 'error': 'Мэдээлэл дутуу байна'}), 400

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    row = [full_name, phone, email, now, 'QPay', 'Төлөгдсөн']

    try:
        sheet = get_sheet()
        sheet.append_row(row)
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f'Google Sheets error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
