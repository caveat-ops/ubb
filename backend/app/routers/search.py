from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.database import get_db
from app.schemas import SearchOut, SearchResult

router = APIRouter()


@router.get("/", response_model=SearchOut)
async def search(
    q: str = Query("", min_length=1),
    db: AsyncSession = Depends(get_db),
):
    # Busca em posts classificados
    post_result = await db.execute(
        text("""
            SELECT title, subtitle, linkedin_url FROM posts
            WHERE title ILIKE :q OR content ILIKE :q OR subtitle ILIKE :q
            LIMIT 30
        """),
        {"q": f"%{q}%"},
    )
    post_rows = post_result.fetchall()

    # Busca em raw_posts (não classificados)
    raw_result = await db.execute(
        text("""
            SELECT raw_json->>'title' as title, raw_json->>'description' as description, linkedin_url
            FROM raw_posts
            WHERE raw_json->>'title' ILIKE :q OR raw_json->>'description' ILIKE :q
            LIMIT 30
        """),
        {"q": f"%{q}%"},
    )
    raw_rows = raw_result.fetchall()

    seen_urls = set()
    results = []

    for title, subtitle, url in post_rows:
        if url not in seen_urls:
            seen_urls.add(url)
            results.append(SearchResult(type="post", title=title or "", subtitle=subtitle, url=url or ""))

    for title, description, url in raw_rows:
        if url not in seen_urls:
            seen_urls.add(url)
            results.append(SearchResult(type="post", title=title or "", subtitle=description[:120] if description else "", url=url or ""))

    return SearchOut(results=results[:30], total=len(results))
