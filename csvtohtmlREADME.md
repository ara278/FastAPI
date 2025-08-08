## 📊 CSVファイル表示システム

### 機能
- CSVファイルのアップロードと表示
- レセプト電算処理システム用コード・薬品名称データの検証
- HTMLテーブルでのデータ表示

### CSVファイル形式
- ヘッダー: "レセプト電算処理システム用コード","薬品名称"
- レセプト電算処理システム用コード: 数字9桁
- 薬品名称: 全角64文字以内

### 使用方法

1. 依存関係のインストール:
```bash
pip install -r requirements.txt
```

2. FastAPIサーバーの起動:
```bash
cd FastAPI_Traning
uvicorn main:app --reload
```

3. ブラウザで http://localhost:8000 にアクセス

4. CSVファイルをアップロードして表示

### サンプルデータ
`sample_data.csv` ファイルがテスト用に用意されています。

---
