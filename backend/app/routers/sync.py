import asyncio
import json
import os

from fastapi import APIRouter, Request, HTTPException, Header
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from app.database import async_session
from app.main import limiter

router = APIRouter()

SYNC_PUSH_TOKEN = os.environ.get("SYNC_PUSH_TOKEN", "")


def _check_token(authorization: str = Header(None)) -> None:
    if not SYNC_PUSH_TOKEN:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token required")
    if authorization.removeprefix("Bearer ") != SYNC_PUSH_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")


@router.post("/raw-posts")
@limiter.limit("10/minute")
async def receive_raw_posts(payload: dict, authorization: str = Header(None)):
    """Recebe raw_posts do host de sync e insere no banco da VM"""
    _check_token(authorization)
    posts = payload.get("posts", [])
    if not posts:
        return {"inserted": 0}

    inserted = 0
    async with async_session() as db:
        for p in posts:
            url = p.get("link", "")
            if not url:
                continue
            result = await db.execute(text("SELECT id FROM raw_posts WHERE linkedin_url = :url"), {"url": url})
            if result.fetchone():
                continue
            await db.execute(
                text("INSERT INTO raw_posts (linkedin_url, raw_json) VALUES (:url, :json)"),
                {"url": url, "json": json.dumps(p, ensure_ascii=False)},
            )
            inserted += 1
        await db.commit()

    return {"inserted": inserted}


@router.post("/seed")
@limiter.limit("5/minute")
async def receive_seed(payload: dict, authorization: str = Header(None)):
    """Recebe dump completo do banco (schools, disciplines, posts)"""
    _check_token(authorization)

    async with async_session() as db:
        # Schools (upsert by name)
        for s in payload.get("schools", []):
            await db.execute(
                text("INSERT INTO schools (name, slug, description, color, icon) VALUES (:n, :s, :d, :c, :i) ON CONFLICT (name) DO UPDATE SET slug=:s, description=:d, color=:c, icon=:i"),
                {"n": s["name"], "s": s.get("slug", ""), "d": s.get("description"), "c": s.get("color"), "i": s.get("icon")},
            )

        # Disciplines (upsert by name)
        for d in payload.get("disciplines", []):
            await db.execute(
                text("INSERT INTO disciplines (name, slug, description, icon, color, school_id) VALUES (:n, :s, :d, :i, :c, (SELECT id FROM schools WHERE name=:sn LIMIT 1)) ON CONFLICT (name) DO UPDATE SET slug=:s, description=:d, icon=:i, color=:c, school_id=(SELECT id FROM schools WHERE name=:sn LIMIT 1)"),
                {"n": d["name"], "s": d.get("slug", ""), "d": d.get("description"), "i": d.get("icon"), "c": d.get("color"), "sn": d.get("school_name")},
            )

        # Posts (upsert by linkedin_url)
        for p in payload.get("posts", []):
            await db.execute(
                text("INSERT INTO posts (linkedin_url, title, subtitle, summary, quote, mariana_take, content_type, difficulty, discipline_id, school_id) VALUES (:l, :t, :s, :su, :q, :m, :ct, :d, (SELECT id FROM disciplines WHERE name=:dn LIMIT 1), (SELECT id FROM schools WHERE name=:sn LIMIT 1)) ON CONFLICT (linkedin_url) DO UPDATE SET title=:t, subtitle=:s, summary=:su, quote=:q, mariana_take=:m, content_type=:ct, difficulty=:d, discipline_id=(SELECT id FROM disciplines WHERE name=:dn LIMIT 1), school_id=(SELECT id FROM schools WHERE name=:sn LIMIT 1)"),
                {"l": p["linkedin_url"], "t": p.get("title", ""), "s": p.get("subtitle"), "su": p.get("summary"), "q": p.get("quote"), "m": p.get("mariana_take"), "ct": p.get("content_type", "aula"), "d": p.get("difficulty", "Iniciante"), "dn": p.get("discipline_name"), "sn": p.get("school_name")},
            )

        await db.commit()

    return {"status": "ok"}

async def trigger_sync():
    from app.services.task_manager import task_manager
    task_id = task_manager.create_task()
    task_manager.add_message(task_id, {"type": "info", "text": "Tarefa de sincronização criada"})
    asyncio.create_task(_run_sync_task(task_id))
    return {"task_id": task_id}


async def _run_sync_task(task_id: str):
    from app.services.task_manager import task_manager
    from app.services.sync_runner import run_sync
    def progress(text: str):
        task_manager.add_message(task_id, {"type": "progress", "text": text})
    try:
        import importlib
        config = importlib.import_module("app.config")
        headless = config.settings.playwright_headless
        await run_sync(progress_callback=progress, max_posts=20, max_new_posts=1, headless=headless)
        task_manager.complete(task_id, success=True)
    except Exception as e:
        task_manager.add_message(task_id, {"type": "progress", "text": f"ERRO: {str(e)}"})
        task_manager.complete(task_id, success=False, error=str(e))


@router.get("/stream/{task_id}")
async def sync_stream(task_id: str, request: Request):
    from app.services.task_manager import task_manager
    async def event_generator():
        msg_index = 0
        while True:
            if await request.is_disconnected():
                break
            messages, msg_index = task_manager.get_messages(task_id, msg_index)
            for msg in messages:
                yield f"data: {json.dumps(msg)}\n\n"
                if msg.get("type") in ("complete", "error"):
                    return
            if task_manager.get_status(task_id) in ("completed", "error"):
                if not messages:
                    status = task_manager.get_status(task_id)
                    yield f"data: {json.dumps({'type': status})}\n\n"
                break
            await asyncio.sleep(0.3)
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/{task_id}")
async def sync_status(task_id: str):
    from app.services.task_manager import task_manager
    status = task_manager.get_status(task_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Task not found")
    messages, _ = task_manager.get_messages(task_id)
    return {"task_id": task_id, "status": status, "messages": messages[-20:]}
