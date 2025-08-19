import os
import json
import csv
from datetime import datetime
from flask import Flask, request, render_template, redirect, url_for, flash
from werkzeug.utils import secure_filename
import pytesseract
from PIL import Image
import google.generativeai as genai
import pillow_heif

# Register the HEIC opener with Pillow
pillow_heif.register_heif_opener()

# --- Configuration ---
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'heic'}
CSV_FILE = 'receipts.csv'

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# IMPORTANT: In a production environment, use a strong, randomly generated
# secret key and load it from an environment variable.
app.secret_key = 'super_secret_key_for_development_only'

# Configure Google Gemini API
try:
    # It's recommended to set your API key as an environment variable
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("APIキーが設定されていません。環境変数 'GOOGLE_API_KEY' を設定してください。")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    # If the app fails to start due to API key issues, we'll catch it here
    # and flash a message on the first request.
    app.config['API_KEY_ERROR'] = str(e)

# --- Helper Functions ---
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_receipt_with_ai(text):
    """Sends OCR text to Gemini API and parses the response."""
    prompt = f"""
あなたは優秀なレシートのアナリストです。以下のテキストはOCRによってレシートから抽出されたものです。
このテキストから以下の情報を抽出し、JSON形式で回答してください。

- store_name: 店名 (文字列)
- transaction_date: 購入日 (YYYY-MM-DD形式)
- total_amount: 合計金額 (整数)

もし情報が見つからない場合は、そのキーに対応する値として `null` を設定してください。
JSONオブジェクトのみを返し、他のテキストは含めないでください。

レシートテキスト:
---
{text}
---
"""
    try:
        response = model.generate_content(prompt)
        # Clean up the response to get only the JSON part
        json_str = response.text.strip().replace('```json', '').replace('```', '').strip()
        parsed_json = json.loads(json_str)
        return parsed_json
    except Exception as e:
        print(f"AI parsing error: {e}")
        return None

def save_to_csv(data):
    """Saves the extracted data to a CSV file."""
    file_exists = os.path.isfile(CSV_FILE)

    with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as csv_file:
        fieldnames = ['store_name', 'transaction_date', 'total_amount', 'saved_at']
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        writer.writerow({
            'store_name': data.get('store_name'),
            'transaction_date': data.get('transaction_date'),
            'total_amount': data.get('total_amount'),
            'saved_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

# --- Routes ---
@app.route('/')
def index():
    if 'API_KEY_ERROR' in app.config:
        flash(f"重大なエラー: {app.config['API_KEY_ERROR']}")
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'API_KEY_ERROR' in app.config:
        flash(f"重大なエラー: {app.config['API_KEY_ERROR']}")
        return redirect(url_for('index'))

    if 'file' not in request.files:
        flash('ファイルが見つかりません')
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        flash('ファイルが選択されていません')
        return redirect(request.url)
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        try:
            img = Image.open(filepath)
            extracted_text = pytesseract.image_to_string(img, lang='jpn')

            if not extracted_text.strip():
                flash('OCRでテキストを抽出できませんでした。画像の品質を確認してください。')
                return redirect(url_for('index'))

            # --- AI Processing ---
            ai_result = parse_receipt_with_ai(extracted_text)

            if ai_result:
                save_to_csv(ai_result)
                flash('レシートが解析され、CSVファイルに保存されました。')
                return render_template('result.html', extracted_data=ai_result, raw_text=extracted_text)
            else:
                flash('AIによる解析に失敗しました。データは保存されていません。')
                return render_template('result.html', extracted_data=None, raw_text=extracted_text)

        except Exception as e:
            flash(f'処理中にエラーが発生しました: {e}')
            return redirect(url_for('index'))
    else:
        flash('許可されているファイル形式は png, jpg, jpeg, gif です')
        return redirect(request.url)

@app.route('/history')
def history():
    """Displays the history of saved receipts."""
    records = []
    if os.path.isfile(CSV_FILE):
        try:
            with open(CSV_FILE, mode='r', newline='', encoding='utf-8') as csv_file:
                reader = csv.DictReader(csv_file)
                records = list(reader)
        except Exception as e:
            flash(f"履歴ファイルの読み込み中にエラーが発生しました: {e}")

    # Reverse the list to show the most recent entries first
    records.reverse()

    return render_template('history.html', records=records)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=8080)
