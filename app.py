from flask import Flask, render_template, request, jsonify
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import json
import os

app = Flask(__name__)

SCOPES = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
]

SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID', '')
SHEET_NAME = os.environ.get('SHEET_NAME', 'Бүртгэл')

HEADERS = ['Овог Нэр', 'Утасны дугаар', 'Имэйл', 'Бүртгүүлсэн огноо', 'Төлбөрийн арга', 'Төлбөрийн төлөв']


def get_sheet():
    creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON', '')
    if creds_json:
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    try:
        sheet = spreadsheet.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=10)
        sheet.append_row(HEADERS)
    return sheet


@app.route('/')
def home():
    return render_template('index.html')


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
        return jsonify({'success': False, 'error': 'Хадгалахад алдаа гарлаа'}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
