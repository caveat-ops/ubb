#!/usr/bin/env python3
"""
Sync LinkedIn posts directly from the host machine.

Opens a headed browser (your Wayland desktop), auto-logs into LinkedIn,
waits if there's a challenge (you complete it on your phone), then
scrapes posts, classifies with Ollama, and saves to Docker's PostgreSQL.

Usage:  pip install -r backend/requirements.sync.txt
        python scripts/sync_host.py

Env vars lidas do .env na raiz do projeto (LINKEDIN_EMAIL, LINKEDIN_PASSWORD, URL_TARGET).
Database e Ollama: usa localhost:5432 e localhost:11434 (portas expostas pelo Docker).
"""

import asyncio
import os
import sys
from pathlib import Path

# ── Carrega .env da raiz do projeto ───────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

# ── Garante que consegue importar os módulos do backend ────────────────────

BACKEND = PROJECT_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# ── Configuração para execução no host ─────────────────────────────────────

os.environ["DATABASE_URL"] = "postgresql+asyncpg://ubb:ubb@localhost:5432/ubb"
os.environ.setdefault("OLLAMA_HOST", "http://localhost:11434")
os.environ.setdefault("PLAYWRIGHT_HEADLESS", "false")
os.environ.setdefault("LOG_LEVEL", "info")

# ── Override no URL_TARGET se não estiver no .env ──────────────────────────

url_target = os.environ.get("URL_TARGET", "")
if not url_target:
    url_target = "https://www.linkedin.com/in/marianabsz/recent-activity/all/"

# ── Inicializa logging ─────────────────────────────────────────────────────

import logging
logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "info").upper()),
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger("sync_host")

# ── Serviços do backend ────────────────────────────────────────────────────

from app.services.linkedin_agent import LinkedInAgent
from app.services.ollama_service import OllamaService
from app.services.embedding import compute_post_embedding
from app.database import async_session, init_db
from app.models import Post, Tag, Discipline, School, post_tags
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession


async def fetch_posts_from_linkedin(agent: LinkedInAgent, url: str, max_posts: int = 20):
    """Busca posts do LinkedIn. Retorna lista de dicts."""
    return await agent.get_recent_posts(url, max_posts=max_posts)


async def save_post_to_db(db: AsyncSession, post_data: dict, ollama: OllamaService) -> Post | None:
    """Classifica e persiste um post no banco."""
    linkedin_url = post_data.get("linkedin_url", "")
    if not linkedin_url:
        return None

    # Verifica duplicata
    result = await db.execute(select(Post).where(Post.linkedin_url == linkedin_url))
    existing = result.scalar_one_or_none()
    if existing:
        logger.info("  ↳ Já existe: %s", linkedin_url[:60])
        return existing

    content = post_data.get("content", "")
    post_date = post_data.get("post_date", "")
    hashtags = post_data.get("hashtags", [])
    images = post_data.get("images", [])

    # Classificação via Ollama
    classification = await ollama.classify_content(content)
    logger.info("  Classification: %s", classification)

    school_name = classification.get("school", "")
    discipline_name = classification.get("discipline", "")

    # Resolve school
    school = None
    if school_name:
        result = await db.execute(select(School).where(School.name == school_name))
        school = result.scalar_one_or_none()
        if not school:
            school = School(name=school_name)
            db.add(school)
            await db.flush()

    # Resolve discipline
    discipline = None
    if discipline_name:
        result = await db.execute(select(Discipline).where(Discipline.name == discipline_name))
        discipline = result.scalar_one_or_none()
        if not discipline:
            discipline = Discipline(name=discipline_name)
            db.add(discipline)
            await db.flush()

    # Cria o post
    post = Post(
        linkedin_url=linkedin_url,
        linkedin_post_id=post_data.get("linkedin_post_id", ""),
        title=classification.get("title", content[:100]) if not classification.get("title") else classification["title"],
        content=content,
        post_date=post_date,
        hashtags=hashtags,
        images=images,
    )
    if school:
        post.school_id = school.id
    if discipline:
        post.discipline_id = discipline.id
    db.add(post)
    await db.flush()

    # Tags
    for tag_name in classification.get("tags", []):
        result = await db.execute(select(Tag).where(Tag.name == tag_name))
        tag = result.scalar_one_or_none()
        if not tag:
            tag = Tag(name=tag_name)
            db.add(tag)
            await db.flush()
        await db.execute(post_tags.insert().values(post_id=post.id, tag_id=tag.id))

    # Embedding
    embedding = compute_post_embedding(content)
    if embedding is not None:
        await db.execute(
            text("UPDATE posts SET embedding = :emb WHERE id = :id"),
            {"emb": embedding, "id": post.id},
        )

    logger.info("  ✓ Post #%d salvo: %s", post.id, linkedin_url[:60])
    return post


async def main():
    print("=" * 60)
    print("  SYNC HOST — LinkedIn → Ollama → PostgreSQL")
    print("=" * 60)
    print()
    print(f"  LinkedIn: {url_target}")
    print(f"  DB:       localhost:5432/ubb")
    print(f"  Ollama:   {os.environ.get('OLLAMA_HOST', 'http://localhost:11434')}")
    print()

    # Inicializa DB
    print("⟳  Conectando ao banco de dados...")
    await init_db()
    print("   ✓ Banco pronto")

    # LinkedIn
    email = os.environ.get("LINKEDIN_EMAIL", "")
    password = os.environ.get("LINKEDIN_PASSWORD", "")
    if not email or not password:
        print("✗ LINKEDIN_EMAIL / LINKEDIN_PASSWORD não configurados no .env")
        sys.exit(1)

    print("⟳  Abrindo navegador LinkedIn...")
    agent = LinkedInAgent(email=email, password=password, headless=False)
    try:
        logged_in = await agent.login()
        if not logged_in:
            print("✗ Falha no login do LinkedIn")
            return
        print("   ✓ Conectado ao LinkedIn")

        # Busca posts
        print(f"⟳  Buscando posts de: {url_target[:60]}...")
        posts_data = await fetch_posts_from_linkedin(agent, url_target, max_posts=20)
        print(f"   → {len(posts_data)} posts encontrados")

        if not posts_data:
            print("⚠  Nenhum post encontrado.")
            return

        # Ollama
        ollama = OllamaService()

        # Salva no banco
        async with async_session() as db:
            saved = 0
            for i, post_data in enumerate(posts_data):
                content = post_data.get("content", "")
                if not content:
                    continue
                print(f"\n[{i+1}/{len(posts_data)}] Classificando e salvando...")
                result = await save_post_to_db(db, post_data, ollama)
                if result:
                    saved += 1

            await db.commit()
            print(f"\n   ✓ {saved} posts salvos no banco!")

    finally:
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
