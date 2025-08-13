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
import logging

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# グローバル変数でデータを保持
df = None
search_cache = {}  # 検索結果キャッシュ
last_cache_clear = time.time()


def normalize_text(text: str) -> str:
    """テキストの正規化（シンプル版）"""
    try:
        if text is None or pd.isna(text):
            return ""
        # 基本的な正規化のみ
        normalized = str(text).strip()
        normalized = normalized.lower()
        # 全角スペースを半角スペースに変換
        normalized = normalized.replace('　', ' ')
        # 連続するスペースを単一スペースに
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized
    except Exception as e:
        logger.error(f"テキスト正規化エラー: {e}")
        return ""


def resolve_data_csv_path() -> str | None:
    """data.csv の候補パスを順に確認し、存在する最初のパスを返す"""
    try:
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
    except Exception as e:
        logger.error(f"パス解決エラー: {e}")
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
                logger.warning(f"CSVファイルのヘッダーが正しくありません。期待されるヘッダー: {expected_headers}")
                return
            
            # データの基本検証
            if len(df_local) == 0:
                logger.warning("CSVファイルが空です")
                return
            
            # 検索用正規化列を作成（エラーハンドリング付き）
            try:
                df_local["__search_name"] = df_local["薬品名称"].fillna("").astype(str).apply(normalize_text)
                # 空の検索名を除外
                df_local = df_local[df_local["__search_name"] != ""]
                
                if len(df_local) == 0:
                    logger.warning("正規化後のデータが空です")
                    return
                
                # グローバルにセット
                globals()["df"] = df_local.copy()
                # キャッシュクリア
                search_cache.clear()
                logger.info(f"CSVファイル '{csv_path}' を正常に読み込みました。データ件数: {len(df_local)} 件")
                
            except Exception as e:
                logger.error(f"データ正規化エラー: {e}")
                return
                
        else:
            logger.warning("'data.csv' ファイルが見つかりません")
            globals()["df"] = None
            
    except Exception as e:
        logger.error(f"CSVファイルの読み込み中にエラーが発生しました: {e}")
        globals()["df"] = None


def clear_cache_if_needed():
    """必要に応じてキャッシュをクリア"""
    global last_cache_clear, search_cache
    try:
        current_time = time.time()
        if current_time - last_cache_clear > 300:  # 5分ごとにキャッシュクリア
            search_cache.clear()
            last_cache_clear = current_time
    except Exception as e:
        logger.error(f"キャッシュクリアエラー: {e}")


def simple_search(query: str, limit: int = 50) -> Tuple[List[str], List[dict]]:
    """シンプルで安定した検索アルゴリズム"""
    global df, search_cache
    
    try:
        if df is None or df.empty:
            logger.warning("データが読み込まれていません")
            return [], []
        
        q_norm = normalize_text(query)
        if len(q_norm) < 3:
            return [], []
        
        # キャッシュチェック
        clear_cache_if_needed()
        cache_key = (q_norm, limit)
        if cache_key in search_cache:
            return search_cache[cache_key]
        
        # シンプルな文字列検索
        results_list = []
        suggestions_list = []
        
        try:
            # 基本的な文字列検索
            for idx, row in df.iterrows():
                try:
                    search_name = row.get("__search_name", "")
                    if search_name and q_norm in search_name:
                        results_list.append({
                            "レセプト電算処理システム用コード": row["レセプト電算処理システム用コード"],
                            "薬品名称": row["薬品名称"]
                        })
                        
                        # 候補リスト（最大10件）
                        if len(suggestions_list) < 10:
                            suggestions_list.append(row["薬品名称"])
                        
                        # 結果リスト（最大limit件）
                        if len(results_list) >= limit:
                            break
                            
                except Exception as e:
                    logger.warning(f"行処理エラー (行{idx}): {e}")
                    continue
            
            # 結果をスコアリング（先頭一致を優先）
            def score_result(result):
                name_lower = normalize_text(result["薬品名称"])
                if name_lower.startswith(q_norm):
                    return 2
                return 1
            
            # スコアでソート
            results_list.sort(key=score_result, reverse=True)
            
            # キャッシュに保存
            search_cache[cache_key] = (suggestions_list, results_list)
            
            logger.info(f"検索完了: '{query}' -> {len(results_list)}件")
            return suggestions_list, results_list
            
        except Exception as e:
            logger.error(f"検索処理エラー: {e}")
            return [], []
            
    except Exception as e:
        logger.error(f"検索全体エラー: {e}")
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
            let searchInProgress = false;
            
            function searchDrugs() {
                const searchTerm = document.getElementById('searchInput').value;
                if (searchTerm.length >= 3 && !searchInProgress) {
                    clearTimeout(searchTimeout);
                    searchTimeout = setTimeout(() => {
                        performSearchRequest(searchTerm, true);
                    }, 400); // デバウンス時間をさらに延長
                } else if (searchTerm.length < 3) {
                    clearSuggestions();
                    enableSearchButton();
                }
            }
            
            function performSearchRequest(searchTerm, isSuggestion = false) {
                if (searchInProgress) {
                    console.log('検索進行中、スキップ');
                    return;
                }
                
                if (currentSearchRequest) {
                    currentSearchRequest.abort();
                }
                
                searchInProgress = true;
                const searchButton = document.querySelector('.search-button');
                searchButton.disabled = true;
                searchButton.textContent = '検索中...';
                
                const controller = new AbortController();
                currentSearchRequest = controller;
                
                // タイムアウト設定（短縮）
                const timeoutId = setTimeout(() => {
                    if (currentSearchRequest === controller) {
                        controller.abort();
                        console.log('検索タイムアウト');
                        enableSearchButton();
                        searchInProgress = false;
                        displayError('検索がタイムアウトしました。');
                    }
                }, 3000); // 3秒タイムアウト
                
                fetch('/search?q=' + encodeURIComponent(searchTerm), { 
                    signal: controller.signal 
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    return response.json();
                })
                .then(data => {
                    clearTimeout(timeoutId);
                    if (isSuggestion) {
                        displaySuggestions(data.suggestions);
                    } else {
                        displayResults(data.results);
                    }
                })
                .catch(error => {
                    clearTimeout(timeoutId);
                    if (error.name !== 'AbortError') {
                        console.error('検索エラー:', error);
                        displayError('検索中にエラーが発生しました。');
                    }
                })
                .finally(() => {
                    enableSearchButton();
                    currentSearchRequest = null;
                    searchInProgress = false;
                });
            }
            
            function enableSearchButton() {
                const searchButton = document.querySelector('.search-button');
                searchButton.disabled = false;
                searchButton.textContent = '検索';
            }
            
            function displayError(message) {
                const resultsDiv = document.getElementById('searchResults');
                resultsDiv.innerHTML = `<p class=\"error\">${message}</p>`;
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
                if (searchTerm.trim() !== '' && !searchInProgress) {
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
                searchInProgress = false;
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
    """安定した検索エンドポイント"""
    try:
        if len(normalize_text(q)) < 3:
            return {"suggestions": [], "results": []}
        
        # 同期的に検索を実行（非同期処理による複雑性を排除）
        suggestions, results = simple_search(q, 50)
        
        return {"suggestions": suggestions, "results": results}
        
    except Exception as e:
        logger.error(f"検索エンドポイントエラー: {e}")
        return {"suggestions": [], "results": []}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/debug")
def debug_info():
    """デバッグ情報表示"""
    global df, search_cache
    try:
        return {
            "data_loaded": df is not None,
            "data_length": len(df) if df is not None else 0,
            "cache_size": len(search_cache),
            "last_cache_clear": last_cache_clear
        }
    except Exception as e:
        return {"error": str(e)}
