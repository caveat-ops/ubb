from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Post
from app.schemas import PostDetail, PostList, PostOut

router = APIRouter()


@router.get("", response_model=PostList)
@router.get("/", response_model=PostList)
async def list_posts(
    page: int = 1,
    per_page: int = 20,
    discipline_id: int = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Post).options(selectinload(Post.tags))
    if discipline_id:
        q = q.where(Post.discipline_id == discipline_id)
    result = await db.execute(q.limit(per_page).offset((page - 1) * per_page))
    posts = result.unique().scalars().all()
    total_q = select(Post)
    if discipline_id:
        total_q = total_q.where(Post.discipline_id == discipline_id)
    total_result = await db.execute(total_q)
    total = len(total_result.scalars().all())
    return PostList(
        items=[PostOut.model_validate(p) for p in posts],
        total=total,
        page=page,
    )


@router.get("/trending", response_model=list[PostOut])
async def trending_posts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Post).order_by(Post.indexed_at.desc().nullslast()).limit(10))
    posts = result.scalars().all()
    return [PostOut.model_validate(p) for p in posts]


@router.get("/recent", response_model=list[PostOut])
async def recent_posts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Post).order_by(Post.post_date.desc().nullslast()).limit(10))
    posts = result.scalars().all()
    return [PostOut.model_validate(p) for p in posts]


@router.get("/{post_id}", response_model=PostDetail)
async def get_post(post_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if post is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Post not found")
    return PostDetail(post=PostOut.model_validate(post))
