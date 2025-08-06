from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

# FastAPIアプリケーションのインスタンスを作成
app = FastAPI(
    title="FastAPI テストページ",
    description="FastAPIを使ったシンプルなテストAPIです。",
    version="1.0.0"
)

# データモデルの定義
class Item(BaseModel):
    id: int
    name: str
    description: str | None = None
    price: float

# ダミーデータのリスト
items: List[Item] = [
    Item(id=1, name="Item 1", description="これはテストアイテム1です", price=100.0),
    Item(id=2, name="Item 2", description="これはテストアイテム2です", price=200.0)
]

# ルートエンドポイント
@app.get("/")
async def root():
    return {"message": "FastAPIテストページへようこそ！ /docs でAPIを試してください"}

# 全アイテムを取得
@app.get("/items/", response_model=List[Item])
async def get_items():
    return items

# IDで特定のアイテムを取得
@app.get("/items/{item_id}", response_model=Item)
async def get_item(item_id: int):
    for item in items:
        if item.id == item_id:
            return item
    raise HTTPException(status_code=404, detail="アイテムが見つかりません")

# 新しいアイテムを追加
@app.post("/items/", response_model=Item)
async def create_item(item: Item):
    if any(existing_item.id == item.id for existing_item in items):
        raise HTTPException(status_code=400, detail="このIDのアイテムはすでに存在します")
    items.append(item)
    return item

# アイテムを更新
@app.put("/items/{item_id}", response_model=Item)
async def update_item(item_id: int, updated_item: Item):
    for index, item in enumerate(items):
        if item.id == item_id:
            items[index] = updated_item
            return updated_item
    raise HTTPException(status_code=404, detail="アイテムが見つかりません")

# アイテムを削除
@app.delete("/items/{item_id}")
async def delete_item(item_id: int):
    for index, item in enumerate(items):
        if item.id == item_id:
            items.pop(index)
            return {"message": f"アイテム {item_id} を削除しました"}
    raise HTTPException(status_code=404, detail="アイテムが見つかりません")
