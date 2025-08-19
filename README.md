# AIレシート家計簿アプリ

これは、iPhoneなどで撮影したレシート画像をアップロードすると、AIが内容を解析し、家計簿データ（CSV形式）を自動で作成するシンプルなWebアプリケーションです。

## 機能
- **画像アップロード**: レシート画像（png, jpg, jpeg）をアップロードできます。
- **OCRによるテキスト抽出**: [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) を利用して、画像から日本語テキストを抽出します。
- **AIによるデータ解析**: [Google Gemini API](https://ai.google.dev/docs/gemini_api_overview) を利用して、抽出されたテキストから「店名」「購入日時」「合計金額」をJSON形式で取得します。
- **データ保存**: 解析結果を `receipts.csv` というファイルに自動で保存します。
- **履歴表示**: これまでに保存した全データをWebページ上で一覧表示できます。

## 必要なもの
- Python 3.8+
- **Tesseract OCR 本体**
  - **Windows:**
    1. [UB-MannheimのTesseractインストーラー](https://github.com/UB-Mannheim/tesseract/wiki) から最新のインストーラー（例: `tesseract-ocr-w64-setup-v5.x.x...exe`）をダウンロードして実行します。
    2. "Additional language data"のステップで、`Japanese` にチェックを入れて日本語言語パックをインストールします。
    3. Tesseractのインストールパスをシステムの環境変数 `Path` に追加します。（例: `C:\Program Files\Tesseract-OCR`）
  - **Debian/Ubuntu:** `sudo apt-get install tesseract-ocr tesseract-ocr-jpn`
  - **macOS (Homebrew):** `brew install tesseract tesseract-lang`
- **Google Gemini API キー**

## セットアップ手順

1. **リポジトリをクローン:**
   ```bash
   git clone <repository_url>
   cd <repository_directory>
   ```

2. **Python仮想環境の作成と有効化:**
   ```bash
   python -m venv venv
   ```
   - **Windows (コマンドプロンプト):** `venv\Scripts\activate`
   - **Windows (PowerShell):** `venv\Scripts\Activate.ps1`
   - **macOS / Linux:** `source venv/bin/activate`

3. **必要なライブラリをインストール:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Google Gemini APIキーの設定:**
   Google AI StudioからAPIキーを取得し、環境変数として設定します。

   - **Windows (コマンドプロンプト):**
     ```cmd
     setx GOOGLE_API_KEY "ここにあなたのAPIキーを貼り付け"
     ```
     （コマンドプロンプトを再起動すると反映されます）

   - **Windows (PowerShell):**
     ```powershell
     $env:GOOGLE_API_KEY="ここにあなたのAPIキーを貼り付け"
     ```
     （この設定は現在のセッションでのみ有効です。永続化するにはシステムの環境変数設定画面から追加してください）

   - **macOS / Linux:**
     ```bash
     export GOOGLE_API_KEY="ここにあなたのAPIキーを貼り付け"
     ```
     （シェルの設定ファイル（`.bashrc`, `.zshrc`など）にこの行を追加すると、永続的に設定できます）

## 実行方法

1. **Flaskアプリケーションを起動:**
   ```bash
   python app.py
   ```

2. **ブラウザでアクセス:**
   Webブラウザを開き、 `http://127.0.0.1:8080` にアクセスします。

3. **レシートをアップロード:**
   フォームからレシート画像を選択し、「アップロード」ボタンを押してください。
   解析結果が表示され、データが `receipts.csv` に保存されます。
   「保存済みデータ履歴を表示」リンクから、これまでの全データを確認できます。
