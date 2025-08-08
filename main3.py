# main.py
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import pandas as pd
import os

app = FastAPI()

# グローバル変数でデータを保持
df = None

def resolve_data_csv_path() -> str | None:
    """data.csv の候補パスを順に確認し、存在する最初のパスを返す"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, "data.csv"),
        os.path.join(base_dir, "..", "data.csv"),
        os.path.join(os.getcwd(), "data.csv"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None

def load_csv_data():
    """起動時にCSVファイルを読み込む"""
    global df
    try:
        csv_path = resolve_data_csv_path()
        if csv_path and os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            # ヘッダーの確認
            expected_headers = ["レセプト電算処理システム用コード", "薬品名称"]
            if not all(header in df.columns for header in expected_headers):
                print(f"警告: CSVファイルのヘッダーが正しくありません。期待されるヘッダー: {expected_headers}")
                df = None
            else:
                print(f"CSVファイル '{csv_path}' を正常に読み込みました。データ件数: {len(df)} 件")
        else:
            print("警告: 'data.csv' ファイルが見つかりません。プロジェクト直下または 'FastAPI_Traning' 直下に配置してください。")
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

@app.get("/health")
def health_check():
    return {"status": "healthy"}
