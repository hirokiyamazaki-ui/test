import os
import json
import sqlite3
from datetime import datetime
from flask import Flask, request, render_template, redirect, url_for, flash, g, abort
from werkzeug.utils import secure_filename
import pytesseract
from PIL import Image
import google.generativeai as genai
import pillow_heif

# --- Configuration ---
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'heic'}
DATABASE = 'receipts.db'

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['DATABASE'] = DATABASE
# IMPORTANT: In a production environment, use a strong, randomly generated
# secret key and load it from an environment variable.
app.secret_key = 'super_secret_key_for_development_only'


# --- Database Functions ---
def get_db():
    """Opens a new database connection if there is none yet for the current application context."""
    if 'db' not in g:
        g.db = sqlite3.connect(
            app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    """Closes the database again at the end of the request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Initializes the database."""
    db = get_db()
    with app.open_resource('schema.sql', mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()

@app.cli.command('init-db')
def init_db_command():
    """Creates the database tables."""
    init_db()
    print('Initialized the database.')


# Configure Google Gemini API
try:
    # It's recommended to set your API key as an environment variable
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("APIキーが設定されていません。環境変数 'GOOGLE_API_KEY' を設定してください。")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
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
        json_str = response.text.strip().replace('```json', '').replace('```', '').strip()
        parsed_json = json.loads(json_str)
        return parsed_json
    except Exception as e:
        print(f"AI parsing error: {e}")
        return None

def save_to_db(data):
    """Saves the extracted data to the database."""
    db = get_db()
    db.execute(
        'INSERT INTO receipts (store_name, transaction_date, total_amount) VALUES (?, ?, ?)',
        (data.get('store_name'), data.get('transaction_date'), data.get('total_amount'))
    )
    db.commit()

def get_record(id):
    """Get a single record by id."""
    record = get_db().execute(
        'SELECT id, store_name, transaction_date, total_amount FROM receipts WHERE id = ?',
        (id,)
    ).fetchone()
    if record is None:
        abort(404, f"Record id {id} doesn't exist.")
    return record


# --- Routes ---
@app.route('/')
def index():
    if 'API_KEY_ERROR' in app.config:
        flash(f"重大なエラー: {app.config['API_KEY_ERROR']}")
    try:
        get_db()
    except Exception as e:
        flash(f"データベースに接続できませんでした。`flask init-db`コマンドは実行しましたか？ エラー: {e}")
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'API_KEY_ERROR' in app.config:
        flash(f"重大なエラー: {app.config['API_KEY_ERROR']}")
        return redirect(url_for('index'))

    if 'file' not in request.files:
        flash('ファイルが見つかりません')
        return redirect(url_for('index'))
    file = request.files['file']
    if file.filename == '':
        flash('ファイルが選択されていません')
        return redirect(url_for('index'))
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        try:
            if filename.rsplit('.', 1)[1].lower() == 'heic':
                heif_file = pillow_heif.read_heif(filepath)
                img = Image.frombytes(
                    heif_file.mode,
                    heif_file.size,
                    heif_file.data,
                    "raw",
                )
            else:
                img = Image.open(filepath)

            extracted_text = pytesseract.image_to_string(img, lang='jpn')

            if not extracted_text.strip():
                flash('OCRでテキストを抽出できませんでした。画像の品質を確認してください。')
                return redirect(url_for('index'))

            ai_result = parse_receipt_with_ai(extracted_text)

            if ai_result:
                save_to_db(ai_result)
                flash('レシートが解析され、データベースに保存されました。')
                return render_template('result.html', extracted_data=ai_result, raw_text=extracted_text)
            else:
                flash('AIによる解析に失敗しました。データは保存されていません。')
                return render_template('result.html', extracted_data=None, raw_text=extracted_text)

        except Exception as e:
            flash(f'処理中にエラーが発生しました: {e}')
            return redirect(url_for('index'))
    else:
        flash('許可されているファイル形式は png, jpg, jpeg, gif, heic です')
        return redirect(url_for('index'))

@app.route('/history')
def history():
    """Displays the history of saved receipts."""
    db = get_db()
    records = db.execute(
        'SELECT id, store_name, transaction_date, total_amount, saved_at FROM receipts ORDER BY saved_at DESC'
    ).fetchall()
    return render_template('history.html', records=records)

@app.route('/<int:id>/edit', methods=('GET', 'POST'))
def edit_record(id):
    """Edits a record."""
    record = get_record(id)

    if request.method == 'POST':
        store_name = request.form['store_name']
        transaction_date = request.form['transaction_date']
        total_amount = request.form['total_amount']
        error = None

        if not store_name:
            error = '店名は必須です。'

        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                'UPDATE receipts SET store_name = ?, transaction_date = ?, total_amount = ?'
                ' WHERE id = ?',
                (store_name, transaction_date, total_amount, id)
            )
            db.commit()
            flash('レコードが更新されました。')
            return redirect(url_for('history'))

    return render_template('edit.html', record=record)


@app.route('/<int:id>/delete', methods=('POST',))
def delete_record(id):
    """Deletes a record."""
    get_record(id) # check that the record exists
    db = get_db()
    db.execute('DELETE FROM receipts WHERE id = ?', (id,))
    db.commit()
    flash('レコードが削除されました。')
    return redirect(url_for('history'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=8080)
