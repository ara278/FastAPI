# main.py
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import pandas as pd
import os
import asyncio
from functools import lru_cache
import re
from typing import Dict, List, Optional
import time

app = FastAPI()

# グローバル変数でデータを保持
df = None
search_cache = {}  # 検索結果キャッシュ
last_cache_clear = time.time()

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

def clear_cache_if_needed():
    """必要に応じてキャッシュをクリア"""
    global last_cache_clear, search_cache
    current_time = time.time()
    if current_time - last_cache_clear > 300:  # 5分ごとにキャッシュクリア
        search_cache.clear()
        last_cache_clear = current_time

def fast_search(query: str) -> tuple[List[str], List[dict]]:
    """高速検索アルゴリズム - 検索文字列を含む薬品名称のみを返す"""
    global df, search_cache
    
    if df is None or len(query) < 3:
        return [], []
    
    # キャッシュチェック
    cache_key = query.lower()
    if cache_key in search_cache:
        return search_cache[cache_key]
    
    clear_cache_if_needed()
    
    query_lower = query.lower()
    
    # 検索文字列を含む薬品名称のみを検索
    def contains_query(drug_name):
        return query_lower in drug_name.lower()
    
    # フィルタリング
    filtered_df = df[df['薬品名称'].apply(contains_query)]
    
    if len(filtered_df) > 0:
        # スコアリング（検索文字列の位置でスコアを決定）
        def calculate_score(name):
            name_lower = name.lower()
            query_pos = name_lower.find(query_lower)
            if query_pos == 0:
                return 3  # 先頭に一致
            elif query_pos > 0:
                return 2  # 途中に一致
            else:
                return 1  # 部分一致
        
        filtered_df['score'] = filtered_df['薬品名称'].apply(calculate_score)
        filtered_df = filtered_df.sort_values('score', ascending=False)
        
        suggestions = filtered_df['薬品名称'].head(10).tolist()
        results = filtered_df.drop('score', axis=1).to_dict('records')
    else:
        suggestions = []
        results = []
    
    # キャッシュに保存
    search_cache[cache_key] = (suggestions, results)
    
    return suggestions, results

# 起動時にCSVファイルを読み込み
load_csv_data()

@app.get("/", response_class=HTMLResponse)
def read_root():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>薬品検索</title>
        <meta charset=\"utf-8\">
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .search-container { margin: 20px 0; padding: 20px; border: 2px solid #007bff; border-radius: 8px; }
            .search-input { width: 70%; padding: 10px; font-size: 16px; border: 1px solid #ddd; border-radius: 4px; }
            .search-button { padding: 10px 20px; font-size: 16px; background-color: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
            .search-button:hover { background-color: #0056b3; }
            .search-button:disabled { background-color: #6c757d; cursor: not-allowed; }
            .suggestions { margin-top: 10px; }
            .suggestion-item { padding: 8px; cursor: pointer; border-bottom: 1px solid #eee; }
            .suggestion-item:hover { background-color: #f8f9fa; }
            .csv-table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            .csv-table th, .csv-table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            .csv-table th { background-color: #f2f2f2; }
            .error { color: red; }
            .success { color: green; }
            .info { color: #007bff; }
            .loading { color: #ffc107; }
        </style>
        <script>
            let searchTimeout;
            let currentSearchRequest = null;
            
            function searchDrugs() {
                const searchTerm = document.getElementById('searchInput').value;
                const searchButton = document.querySelector('.search-button');
                
                if (searchTerm.length >= 3) {
                    clearTimeout(searchTimeout);
                    searchTimeout = setTimeout(() => {
                        performSearchRequest(searchTerm, true);
                    }, 200); // デバウンス時間を短縮
                } else {
                    clearSuggestions();
                    enableSearchButton();
                }
            }
            
            function performSearchRequest(searchTerm, isSuggestion = false) {
                // 前のリクエストをキャンセル
                if (currentSearchRequest) {
                    currentSearchRequest.abort();
                }
                
                const searchButton = document.querySelector('.search-button');
                searchButton.disabled = true;
                searchButton.textContent = '検索中...';
                
                const controller = new AbortController();
                currentSearchRequest = controller;
                
                fetch('/search?q=' + encodeURIComponent(searchTerm), {
                    signal: controller.signal
                })
                .then(response => response.json())
                .then(data => {
                    if (isSuggestion) {
                        displaySuggestions(data.suggestions);
                    } else {
                        displayResults(data.results);
                    }
                })
                .catch(error => {
                    if (error.name !== 'AbortError') {
                        console.error('検索エラー:', error);
                    }
                })
                .finally(() => {
                    enableSearchButton();
                    currentSearchRequest = null;
                });
            }
            
            function enableSearchButton() {
                const searchButton = document.querySelector('.search-button');
                searchButton.disabled = false;
                searchButton.textContent = '検索';
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
                    performSearchRequest(searchTerm, false);
                }
            }
            
            function displayResults(results) {
                const resultsDiv = document.getElementById('searchResults');
                if (results.length === 0) {
                    resultsDiv.innerHTML = '<p class=\"info\">検索結果が見つかりませんでした。</p>';
                    return;
                }
                
                let tableHtml = '<table class=\"csv-table\"><thead><tr><th>レセプト電算処理システム用コード</th><th>薬品名称</th></tr></thead><tbody>';
                results.forEach(row => {
                    tableHtml += `<tr><td>${row['レセプト電算処理システム用コード']}</td><td>${row['薬品名称']}</td></tr>`;
                });
                tableHtml += '</tbody></table>';
                
                resultsDiv.innerHTML = `<h3>検索結果 (${results.length}件)</h3>${tableHtml}`;
            }
            
            function clearSearch() {
                // 進行中のリクエストをキャンセル
                if (currentSearchRequest) {
                    currentSearchRequest.abort();
                    currentSearchRequest = null;
                }
                
                document.getElementById('searchInput').value = '';
                document.getElementById('searchResults').innerHTML = '';
                clearSuggestions();
                enableSearchButton();
            }
        </script>
    </head>
    <body>
        <h1>薬品検索</h1>
        
        <div class=\"search-container\">
            <h2>薬品名称検索</h2>
            <div>
                <input type=\"text\" id=\"searchInput\" class=\"search-input\" placeholder=\"薬品名称を入力してください（3文字以上）\" oninput=\"searchDrugs()\">
                <button onclick=\"performSearch()\" class=\"search-button\">検索</button>
                <button onclick=\"clearSearch()\" class=\"search-button\" style=\"background-color: #6c757d;\">クリア</button>
            </div>
            <div id=\"suggestions\" class=\"suggestions\"></div>
            <div id=\"searchResults\" ></div>
        </div>
        
        <div>
            <p><strong>CSVファイル形式:</strong></p>
            <ul>
                <li>ヘッダー: \"レセプト電算処理システム用コード\",\"薬品名称\"</li>
                <li>レセプト電算処理システム用コード: 数字9桁</li>
                <li>薬品名称: 全角64文字以内</li>
            </ul>
        </div>
    </body>
    </html>
    """

@app.get("/search")
async def search_drugs(q: str = ""):
    """高速検索エンドポイント"""
    if len(q) < 3:
        return {"suggestions": [], "results": []}
    
    # 非同期で検索を実行
    suggestions, results = await asyncio.get_event_loop().run_in_executor(None, fast_search, q)
    
    return {
        "suggestions": suggestions,
        "results": results
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}
