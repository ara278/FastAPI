# main.py
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import pandas as pd
import io
import os
import json

app = FastAPI()

# グローバル変数でデータを保持
df = None

def load_csv_data():
    """起動時にCSVファイルを読み込む"""
    global df
    try:
        csv_path = "data.csv"
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            # ヘッダーの確認
            expected_headers = ["レセプト電算処理システム用コード", "薬品名称"]
            if not all(header in df.columns for header in expected_headers):
                print(f"警告: CSVファイルのヘッダーが正しくありません。期待されるヘッダー: {expected_headers}")
                df = None
            else:
                print(f"CSVファイル '{csv_path}' を正常に読み込みました。データ件数: {len(df)} 件")
        else:
            print(f"警告: '{csv_path}' ファイルが見つかりません。")
            df = None
    except Exception as e:
        print(f"CSVファイルの読み込み中にエラーが発生しました: {str(e)}")
        df = None

# 起動時にCSVファイルを読み込み
load_csv_data()

@app.get("/", response_class=HTMLResponse)
def read_root():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>薬品検索</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .search-container { margin: 20px 0; padding: 20px; border: 2px solid #007bff; border-radius: 8px; }
            .search-input { width: 70%; padding: 10px; font-size: 16px; border: 1px solid #ddd; border-radius: 4px; }
            .search-button { padding: 10px 20px; font-size: 16px; background-color: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
            .search-button:hover { background-color: #0056b3; }
            .suggestions { margin-top: 10px; }
            .suggestion-item { padding: 8px; cursor: pointer; border-bottom: 1px solid #eee; }
            .suggestion-item:hover { background-color: #f8f9fa; }
            .csv-table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            .csv-table th, .csv-table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            .csv-table th { background-color: #f2f2f2; }
            .error { color: red; }
            .success { color: green; }
            .info { color: #007bff; }
            .upload-form { margin: 20px 0; padding: 20px; border: 2px dashed #ccc; }
        </style>
        <script>
            let searchTimeout;
            
            function searchDrugs() {
                const searchTerm = document.getElementById('searchInput').value;
                if (searchTerm.length >= 3) {
                    clearTimeout(searchTimeout);
                    searchTimeout = setTimeout(() => {
                        fetch('/search?q=' + encodeURIComponent(searchTerm))
                            .then(response => response.json())
                            .then(data => {
                                displaySuggestions(data.suggestions);
                            });
                    }, 300);
                } else {
                    clearSuggestions();
                }
            }
            
            function displaySuggestions(suggestions) {
                const suggestionsDiv = document.getElementById('suggestions');
                suggestionsDiv.innerHTML = '';
                
                if (suggestions.length > 0) {
                    suggestions.forEach(suggestion => {
                        const div = document.createElement('div');
                        div.className = 'suggestion-item';
                        div.textContent = suggestion;
                        div.onclick = () => {
                            document.getElementById('searchInput').value = suggestion;
                            clearSuggestions();
                            performSearch();
                        };
                        suggestionsDiv.appendChild(div);
                    });
                }
            }
            
            function clearSuggestions() {
                document.getElementById('suggestions').innerHTML = '';
            }
            
            function performSearch() {
                const searchTerm = document.getElementById('searchInput').value;
                if (searchTerm.trim() !== '') {
                    fetch('/search?q=' + encodeURIComponent(searchTerm))
                        .then(response => response.json())
                        .then(data => {
                            displayResults(data.results);
                        });
                }
            }
            
            function displayResults(results) {
                const resultsDiv = document.getElementById('searchResults');
                if (results.length === 0) {
                    resultsDiv.innerHTML = '<p class="info">検索結果が見つかりませんでした。</p>';
                    return;
                }
                
                let tableHtml = '<table class="csv-table"><thead><tr><th>レセプト電算処理システム用コード</th><th>薬品名称</th></tr></thead><tbody>';
                results.forEach(row => {
                    tableHtml += `<tr><td>${row['レセプト電算処理システム用コード']}</td><td>${row['薬品名称']}</td></tr>`;
                });
                tableHtml += '</tbody></table>';
                
                resultsDiv.innerHTML = `<h3>検索結果 (${results.length}件)</h3>${tableHtml}`;
            }
            
            function clearSearch() {
                document.getElementById('searchInput').value = '';
                document.getElementById('searchResults').innerHTML = '';
                clearSuggestions();
            }
        </script>
    </head>
    <body>
        <h1>薬品検索</h1>
        
        <div class="search-container">
            <h2>薬品名称検索</h2>
            <div>
                <input type="text" id="searchInput" class="search-input" placeholder="薬品名称を入力してください（3文字以上）" oninput="searchDrugs()">
                <button onclick="performSearch()" class="search-button">検索</button>
                <button onclick="clearSearch()" class="search-button" style="background-color: #6c757d;">クリア</button>
            </div>
            <div id="suggestions" class="suggestions"></div>
            <div id="searchResults"></div>
        </div>
        
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

@app.get("/search")
async def search_drugs(q: str = ""):
    global df
    
    if df is None:
        return {"suggestions": [], "results": []}
    
    if len(q) < 3:
        return {"suggestions": [], "results": []}
    
    # 薬品名称で検索
    filtered_df = df[df['薬品名称'].str.contains(q, case=False, na=False)]
    
    # 候補（最初の10件）
    suggestions = filtered_df['薬品名称'].head(10).tolist()
    
    # 検索結果（全件）
    results = filtered_df.to_dict('records')
    
    return {
        "suggestions": suggestions,
        "results": results
    }

@app.post("/upload", response_class=HTMLResponse)
async def upload_csv(file: UploadFile = File(...)):
    global df
    
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
        new_df = pd.read_csv(io.StringIO(content.decode('utf-8')))
        
        # ヘッダーの確認
        expected_headers = ["レセプト電算処理システム用コード", "薬品名称"]
        if not all(header in new_df.columns for header in expected_headers):
            return HTMLResponse(content=f"""
            <!DOCTYPE html>
            <html>
            <head><title>エラー</title><meta charset="utf-8"></head>
            <body>
                <h1>エラー</h1>
                <p class="error">CSVファイルのヘッダーが正しくありません。</p>
                <p>期待されるヘッダー: {expected_headers}</p>
                <p>実際のヘッダー: {list(new_df.columns)}</p>
                <a href="/">戻る</a>
            </body>
            </html>
            """, status_code=400)
        
        # データの検証
        validation_errors = []
        for index, row in new_df.iterrows():
            # レセプト電算処理システム用コードの検証（数字9桁）
            code = str(row["レセプト電算処理システム用コード"])
            if not code.isdigit() or len(code) != 9:
                validation_errors.append(f"行{index + 1}: レセプト電算処理システム用コードが9桁の数字ではありません ({code})")
            
            # 薬品名称の検証（全角64文字以内）
            name = str(row["薬品名称"])
            if len(name) > 64:
                validation_errors.append(f"行{index + 1}: 薬品名称が64文字を超えています ({len(name)}文字)")
        
        # データを更新
        df = new_df
        
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
