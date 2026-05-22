from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import Discipline, School, Post
from app.schemas import DisciplineOut, SchoolOut

router = APIRouter()


@router.get("", response_model=list[DisciplineOut])
@router.get("/", response_model=list[DisciplineOut])
async def list_disciplines(db: AsyncSession = Depends(get_db)):
    # Count posts per discipline
    result = await db.execute(
        select(
            Discipline,
            School.name.label("school_name"),
            func.count(Post.id).label("post_count"),
        )
        .outerjoin(School, School.id == Discipline.school_id)
        .outerjoin(Post, Post.discipline_id == Discipline.id)
        .group_by(Discipline.id, School.name)
        .order_by(func.count(Post.id).desc())
    )
    rows = result.all()
    out = []
    for disc, school_name, count in rows:
        dto = DisciplineOut.model_validate(disc)
        dto.post_count = count or 0
        dto.school_name = school_name
        out.append(dto)
    return out


@router.get("/schools", response_model=list[SchoolOut])
async def list_schools(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(School).options(joinedload(School.disciplines)))
    schools = result.unique().scalars().all()
    return [SchoolOut.model_validate(s) for s in schools]


@router.get("/{discipline_id}", response_model=DisciplineOut)
async def get_discipline(discipline_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            Discipline,
            School.name.label("school_name"),
            func.count(Post.id).label("post_count"),
        )
        .outerjoin(School, School.id == Discipline.school_id)
        .outerjoin(Post, Post.discipline_id == Discipline.id)
        .where(Discipline.id == discipline_id)
        .group_by(Discipline.id, School.name)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Discipline not found")
    disc, school_name, count = row
    dto = DisciplineOut.model_validate(disc)
    dto.post_count = count or 0
    dto.school_name = school_name
    return dto
