from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import Discipline, Post, School
from app.schemas import StatsOut

router = APIRouter()


@router.get("", response_model=StatsOut)
@router.get("/", response_model=StatsOut)
async def get_stats(db: AsyncSession = Depends(get_db)):
    total_posts = (await db.execute(select(func.count(Post.id)))).scalar() or 0
    total_disciplines = (await db.execute(select(func.count(Discipline.id)))).scalar() or 0
    total_schools = (await db.execute(select(func.count(School.id)))).scalar() or 0
    total_labs = (await db.execute(
        select(func.count(Post.id)).where(Post.content_type.in_(["lab", "hands_on"]))
    )).scalar() or 0
    return StatsOut(
        total_posts=total_posts,
        total_disciplines=total_disciplines,
        total_schools=total_schools,
        total_labs=total_labs,
    )
