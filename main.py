# main.py
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse
import pandas as pd
import io
import os

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def read_root():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>CSVファイル表示システム</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .upload-form { margin: 20px 0; padding: 20px; border: 2px dashed #ccc; }
            .csv-table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            .csv-table th, .csv-table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            .csv-table th { background-color: #f2f2f2; }
            .error { color: red; }
            .success { color: green; }
        </style>
    </head>
    <body>
        <h1>レセプト電算処理システム用コード・薬品名称表示システム</h1>
        <div class="upload-form">
            <h2>CSVファイルをアップロード</h2>
            <form action="/upload" method="post" enctype="multipart/form-data">
                <input type="file" name="file" accept=".csv" required>
                <button type="submit">アップロード</button>
            </form>
        </div>
        <div>
            <p><strong>CSVファイル形式:</strong></p>
            <ul>
                <li>ヘッダー: "レセプト電算処理システム用コード","薬品名称"</li>
                <li>レセプト電算処理システム用コード: 数字9桁</li>
                <li>薬品名称: 全角64文字以内</li>
            </ul>
        </div>
    </body>
    </html>
    """

@app.post("/upload", response_class=HTMLResponse)
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head><title>エラー</title><meta charset="utf-8"></head>
        <body>
            <h1>エラー</h1>
            <p class="error">CSVファイルをアップロードしてください。</p>
            <a href="/">戻る</a>
        </body>
        </html>
        """, status_code=400)
    
    try:
        # CSVファイルを読み込み
        content = await file.read()
        df = pd.read_csv(io.StringIO(content.decode('utf-8')))
        
        # ヘッダーの確認
        expected_headers = ["レセプト電算処理システム用コード", "薬品名称"]
        if not all(header in df.columns for header in expected_headers):
            return HTMLResponse(content=f"""
            <!DOCTYPE html>
            <html>
            <head><title>エラー</title><meta charset="utf-8"></head>
            <body>
                <h1>エラー</h1>
                <p class="error">CSVファイルのヘッダーが正しくありません。</p>
                <p>期待されるヘッダー: {expected_headers}</p>
                <p>実際のヘッダー: {list(df.columns)}</p>
                <a href="/">戻る</a>
            </body>
            </html>
            """, status_code=400)
        
        # データの検証
        validation_errors = []
        for index, row in df.iterrows():
            # レセプト電算処理システム用コードの検証（数字9桁）
            code = str(row["レセプト電算処理システム用コード"])
            if not code.isdigit() or len(code) != 9:
                validation_errors.append(f"行{index + 1}: レセプト電算処理システム用コードが9桁の数字ではありません ({code})")
            
            # 薬品名称の検証（全角64文字以内）
            name = str(row["薬品名称"])
            if len(name) > 64:
                validation_errors.append(f"行{index + 1}: 薬品名称が64文字を超えています ({len(name)}文字)")
        
        # HTMLテーブルの生成
        table_html = df.to_html(classes='csv-table', index=False, escape=False)
        
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>CSVデータ表示</title>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .csv-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                .csv-table th, .csv-table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                .csv-table th {{ background-color: #f2f2f2; }}
                .error {{ color: red; }}
                .success {{ color: green; }}
                .back-link {{ margin-top: 20px; }}
            </style>
        </head>
        <body>
            <h1>CSVデータ表示</h1>
            <p class="success">ファイル "{file.filename}" が正常にアップロードされました。</p>
            <p>データ件数: {len(df)} 件</p>
            {f'<div class="error"><h3>検証エラー:</h3><ul>{"".join([f"<li>{error}</li>" for error in validation_errors])}</ul></div>' if validation_errors else '<p class="success">データ検証: エラーなし</p>'}
            {table_html}
            <div class="back-link">
                <a href="/">新しいファイルをアップロード</a>
            </div>
        </body>
        </html>
        """)
        
    except Exception as e:
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head><title>エラー</title><meta charset="utf-8"></head>
        <body>
            <h1>エラー</h1>
            <p class="error">ファイルの処理中にエラーが発生しました: {str(e)}</p>
            <a href="/">戻る</a>
        </body>
        </html>
        """, status_code=500)

@app.get("/health")
def health_check():
    return {"status": "healthy"}
