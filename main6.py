# main.py
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import pandas as pd
import os
import asyncio
import re
import time
import unicodedata
from typing import List, Tuple

app = FastAPI()

# グローバル変数でデータを保持
df = None
search_cache = {}  # 検索結果キャッシュ
last_cache_clear = time.time()


def normalize_text(text: str) -> str:
    if text is None:
        return ""
    # NFKCで全角→半角、記号類整形、大小統一、空白類を単一スペースへ
    normalized = unicodedata.normalize("NFKC", str(text))
    normalized = normalized.lower()
    # すべての空白（タブ、改行、全角スペース含む）を1スペースに統一し前後trim
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


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
    global df, search_cache
    try:
        csv_path = resolve_data_csv_path()
        if csv_path and os.path.exists(csv_path):
            df_local = pd.read_csv(csv_path)
            # ヘッダーの確認
            expected_headers = ["レセプト電算処理システム用コード", "薬品名称"]
            if not all(header in df_local.columns for header in expected_headers):
                print(f"警告: CSVファイルのヘッダーが正しくありません。期待されるヘッダー: {expected_headers}")
                return
            # 検索用正規化列を作成（NaN安全）
            df_local["__search_name"] = df_local["薬品名称"].astype(str).map(normalize_text)
            # 正式に反映
            df_obj = df_local.copy()
            # グローバルにセット
            globals()["df"] = df_obj
            # キャッシュはCSV更新時にクリア
            search_cache.clear()
            print(f"CSVファイル '{csv_path}' を正常に読み込みました。データ件数: {len(df_obj)} 件")
        else:
            print("警告: 'data.csv' ファイルが見つかりません。プロジェクト直下または 'FastAPI_Traning' 直下に配置してください。")
            globals()["df"] = None
    except Exception as e:
        print(f"CSVファイルの読み込み中にエラーが発生しました: {str(e)}")
        globals()["df"] = None


def clear_cache_if_needed():
    """必要に応じてキャッシュをクリア"""
    global last_cache_clear, search_cache
    current_time = time.time()
    if current_time - last_cache_clear > 300:  # 5分ごとにキャッシュクリア
        search_cache.clear()
        last_cache_clear = current_time


def fast_search(query: str, limit: int = 100) -> Tuple[List[str], List[dict]]:
    """高速・厳密検索（正規化済み列に対するベクタライズ contains）"""
    global df, search_cache

    if df is None:
        return [], []

    q_norm = normalize_text(query)
    if len(q_norm) < 3:
        return [], []

    # キャッシュ
    clear_cache_if_needed()
    cache_key = (q_norm, limit)
    if cache_key in search_cache:
        return search_cache[cache_key]

    try:
        # 正規表現のメタ文字をエスケープし、厳密な部分一致に限定
        pattern = re.escape(q_norm)
        mask = df["__search_name"].str.contains(pattern, na=False, regex=True)
        matched = df.loc[mask]

        if matched.empty:
            suggestions: List[str] = []
            results: List[dict] = []
        else:
            # 先頭一致を優先、その次に含有
            starts_with = matched[matched["__search_name"].str.startswith(q_norm)]
            contains_only = matched[~matched.index.isin(starts_with.index)]
            ordered = pd.concat([starts_with, contains_only])

            # 上限を適用
            limited = ordered.head(limit)
            suggestions = limited["薬品名称"].head(10).tolist()
            results = limited[["レセプト電算処理システム用コード", "薬品名称"]].to_dict("records")

        search_cache[cache_key] = (suggestions, results)
        return suggestions, results
    except Exception as e:
        # 予期せぬエラー時は安全に空を返す
        return [], []


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
                if (searchTerm.length >= 3) {
                    clearTimeout(searchTimeout);
                    searchTimeout = setTimeout(() => {
                        performSearchRequest(searchTerm, true);
                    }, 200);
                } else {
                    clearSuggestions();
                    enableSearchButton();
                }
            }
            
            function performSearchRequest(searchTerm, isSuggestion = false) {
                if (currentSearchRequest) {
                    currentSearchRequest.abort();
                }
                const searchButton = document.querySelector('.search-button');
                searchButton.disabled = true;
                searchButton.textContent = '検索中...';
                const controller = new AbortController();
                currentSearchRequest = controller;
                fetch('/search?q=' + encodeURIComponent(searchTerm), { signal: controller.signal })
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
    if len(normalize_text(q)) < 3:
        return {"suggestions": [], "results": []}
    suggestions, results = await asyncio.get_event_loop().run_in_executor(None, fast_search, q)
    return {"suggestions": suggestions, "results": results}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
