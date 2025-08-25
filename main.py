from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import pandas as pd
import uvicorn
from typing import List, Optional
import json

app = FastAPI(title="薬品検索", description="医療・看護必要度の対象薬品を検索するシステム")

# データを読み込む
def load_data():
    try:
        df = pd.read_csv('data.csv')
        return df
    except FileNotFoundError:
        # ファイルが見つからない場合はエラーメッセージを表示
        print("エラー: data.csvファイルが見つかりません")
        print("data.csvファイルが正しい場所に存在することを確認してください")
        return None

# 検索機能
def search_data(query: str, df: pd.DataFrame) -> List[dict]:
    if df is None:
        return []
    
    if not query:
        return []
    
    # 薬品名称とコードで検索
    results = []
    query_lower = query.lower()
    
    for _, row in df.iterrows():
        # 薬品名称とコードで検索
        if (query_lower in str(row['薬品名称']).lower() or 
            query_lower in str(row['レセプト電算処理システム用コード']).lower()):
            results.append({
                'レセプト電算処理システム用コード': row['レセプト電算処理システム用コード'],
                '薬品名称': row['薬品名称']
            })
    
    return results[:99]  # 最大99件まで表示

@app.get("/", response_class=HTMLResponse)
async def read_root():
    # データファイルの存在確認
    df = load_data()
    if df is None:
        html_content = """
        <!DOCTYPE html>
        <html lang="ja">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>薬品検索 - エラー</title>
            <style>
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                }
                .container {
                    background: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    text-align: center;
                }
                .error-icon {
                    font-size: 64px;
                    margin-bottom: 20px;
                }
                .error-title {
                    color: #dc3545;
                    font-size: 24px;
                    margin-bottom: 20px;
                }
                .error-message {
                    color: #666;
                    font-size: 16px;
                    line-height: 1.6;
                    margin-bottom: 20px;
                }
                .error-details {
                    background: #f8f9fa;
                    padding: 20px;
                    border-radius: 5px;
                    border-left: 4px solid #dc3545;
                    text-align: left;
                    margin-top: 20px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="error-icon">❌</div>
                <h1 class="error-title">データファイルが見つかりません</h1>
                <p class="error-message">
                    data.csvファイルが見つからないため、システムを起動できません。
                </p>
                <div class="error-details">
                    <h3>確認事項：</h3>
                    <ul>
                        <li>data.csvファイルが正しい場所に存在するか確認してください</li>
                        <li>ファイル名のスペルが正しいか確認してください</li>
                        <li>ファイルの読み取り権限があるか確認してください</li>
                    </ul>
                </div>
            </div>
        </body>
        </html>
        """
        return html_content
    
    html_content = """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>薬品検索</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
                text-align: center;
                margin-bottom: 30px;
            }
            .search-section {
                margin-bottom: 30px;
            }
            .search-input {
                width: 100%;
                padding: 12px;
                font-size: 16px;
                border: 2px solid #ddd;
                border-radius: 5px;
                margin-bottom: 10px;
            }
            .search-button {
                background-color: #007bff;
                color: white;
                padding: 12px 24px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
            }
            .search-button:hover {
                background-color: #0056b3;
            }
            .results {
                margin-top: 20px;
            }
            .result-item {
                background: #f8f9fa;
                padding: 15px;
                margin: 10px 0;
                border-radius: 5px;
                border-left: 4px solid #007bff;
                cursor: pointer;
                transition: background-color 0.2s;
            }
            .result-item:hover {
                background: #e9ecef;
            }
            .result-code {
                color: #666;
                font-size: 14px;
                margin-bottom: 5px;
            }
            .result-name {
                font-weight: bold;
                color: #333;
                margin-bottom: 5px;
            }
            .loading {
                text-align: center;
                color: #666;
                font-style: italic;
            }
            .detail-view {
                background: #e3f2fd;
                padding: 20px;
                margin-bottom: 20px;
                border-radius: 5px;
                border: 1px solid #2196f3;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔍 文字検索システム</h1>
            
            <div class="search-section">
                <input type="text" id="searchInput" class="search-input" 
                       placeholder="薬品コードまたは薬品名称を入力してください..." 
                       autocomplete="off">
                <button onclick="searchData()" class="search-button">検索</button>
            </div>
            
            <div id="detailView"></div>
            <div id="results" class="results"></div>
        </div>

        <script>
            let currentData = [];
            
            async function searchData() {
                const query = document.getElementById('searchInput').value.trim();
                const resultsDiv = document.getElementById('results');
                const detailView = document.getElementById('detailView');
                
                if (!query) {
                    resultsDiv.innerHTML = '<p class="loading">検索語を入力してください</p>';
                    detailView.innerHTML = '';
                    return;
                }
                
                resultsDiv.innerHTML = '<p class="loading">検索中...</p>';
                detailView.innerHTML = '';
                
                try {
                    const response = await fetch('/search', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded',
                        },
                        body: `query=${encodeURIComponent(query)}`
                    });
                    
                    const data = await response.json();
                    currentData = data;
                    displayResults(data);
                } catch (error) {
                    resultsDiv.innerHTML = '<p style="color: red;">エラーが発生しました</p>';
                }
            }
            
            function displayResults(results) {
                const resultsDiv = document.getElementById('results');
                
                if (results.length === 0) {
                    resultsDiv.innerHTML = '<p class="loading">該当する結果が見つかりませんでした</p>';
                    return;
                }
                
                let html = '<h3>検索結果 (' + results.length + '件)</h3>';
                
                results.forEach((item, index) => {
                    html += `
                        <div class="result-item" onclick="showDetail(${index})">
                            <div class="result-code">コード: ${item.レセプト電算処理システム用コード}</div>
                            <div class="result-name">${item.薬品名称}</div>
                        </div>
                    `;
                });
                
                resultsDiv.innerHTML = html;
            }
            
            function showDetail(index) {
                const item = currentData[index];
                const detailView = document.getElementById('detailView');
                
                detailView.innerHTML = `
                    <div class="detail-view">
                        <h3>詳細情報</h3>
                        <p><strong>コード:</strong> ${item.レセプト電算処理システム用コード}</p>
                        <p><strong>薬品名称:</strong> ${item.薬品名称}</p>
                    </div>
                `;
            }
            
            // Enterキーで検索
            document.getElementById('searchInput').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    searchData();
                }
            });
        </script>
    </body>
    </html>
    """
    return html_content

@app.post("/search")
async def search_endpoint(query: str = Form(...)):
    df = load_data()
    if df is None:
        return {"error": "データファイルが見つかりません。data.csvファイルの存在を確認してください。"}
    results = search_data(query, df)
    return results

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "文字検索システムが正常に動作しています"}

if __name__ == "__main__":
    print("文字検索システムを起動しています...")
    print("ブラウザで http://localhost:8000 にアクセスしてください")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
