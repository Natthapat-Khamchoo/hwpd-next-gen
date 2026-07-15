# 3.2 FastAPI Skill & Project Templates
FastAPI framework สำหรับสร้าง REST APIs ที่รวดเร็ว พร้อม Pydantic validation

### Code Pattern
```python
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="My API", version="1.0.0")

class ItemCreate(BaseModel):
    name: str
    price: float
    description: Optional[str] = None

@app.post("/items", status_code=201)
async def create_item(item: ItemCreate, db = Depends(get_db)):
    result = await db.items.insert_one(item.dict())
    return {"id": str(result.inserted_id), **item.dict()}
```