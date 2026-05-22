from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter()


@router.get("")
@router.get("/")
async def list_raw_posts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("SELECT id, linkedin_url, raw_json, created_at FROM raw_posts ORDER BY id DESC")
    )
    rows = result.fetchall()
    return [
        {
            "id": row[0],
            "linkedin_url": row[1],
            "raw_json": row[2],
            "created_at": str(row[3]) if row[3] else None,
        }
        for row in rows
    ]


@router.get("/{post_id}")
async def get_raw_post(post_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("SELECT id, linkedin_url, raw_json, created_at FROM raw_posts WHERE id = :id"),
        {"id": post_id},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Raw post not found")
    return {
        "id": row[0],
        "linkedin_url": row[1],
        "raw_json": row[2],
        "created_at": str(row[3]) if row[3] else None,
    }
