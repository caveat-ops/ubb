from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
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
    content_type: str = None,
    q: str = None,
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if discipline_id:
        filters.append(Post.discipline_id == discipline_id)
    if content_type:
        types = [t.strip() for t in content_type.split(",") if t.strip()]
        if types:
            filters.append(Post.content_type.in_(types))
    if q:
        like = f"%{q}%"
        filters.append(
            or_(
                Post.title.ilike(like),
                Post.summary.ilike(like),
                Post.content.ilike(like),
            )
        )

    list_q = select(Post).options(selectinload(Post.tags))
    total_q = select(func.count()).select_from(Post)
    for f in filters:
        list_q = list_q.where(f)
        total_q = total_q.where(f)

    list_q = list_q.order_by(Post.post_date.desc().nullslast())
    result = await db.execute(list_q.limit(per_page).offset((page - 1) * per_page))
    posts = result.unique().scalars().all()
    total = (await db.execute(total_q)).scalar() or 0
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
