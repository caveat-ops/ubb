from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import random
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# --- .env loading (substitui app.config.settings durante FASE 1) ---
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"
if _ENV_FILE.exists():
    for line in _ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.split("#")[0].strip()
            if k == "DATABASE_URL":
                continue  # gerenciado explicitamente abaixo (localhost local, db:5432 via Docker)
            os.environ.setdefault(k, v)

# --- DATABASE_URL: default localhost para rodar no host; respeitado se já definido (ex: Docker) ---
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://ubb:ubb@localhost:5432/ubb")

from typing import Awaitable, Callable

from app.database import async_session, init_db
from app.models import Discipline, Post, School, SemanticRelation, Tag, post_tags
from app.services.embedding import compute_post_embedding
from app.services.linkedin_agent import LinkedInAgent
from app.services.ollama_service import OllamaService
from sqlalchemy import select, text

logger = logging.getLogger("sync")


async def get_or_create_tag(db, name: str) -> Tag:
    normalized = name.lower().strip().replace(" ", "_").replace("#", "")
    result = await db.execute(
        select(Tag).where(Tag.normalized_name == normalized)
    )
    tag = result.scalar_one_or_none()
    if tag is None:
        tag = Tag(name=name.strip(), normalized_name=normalized)
        db.add(tag)
        await db.flush()
    return tag


async def get_or_create_school(db, name: str) -> School | None:
    if not name:
        return None
    slug = name.lower().strip().replace(" ", "-")
    result = await db.execute(
        select(School).where(School.slug == slug)
    )
    school = result.scalar_one_or_none()
    if school is None:
        school = School(name=name.strip(), slug=slug)
        db.add(school)
        await db.flush()
    return school


async def get_or_create_discipline(
    db, name: str, school: School | None = None
) -> Discipline | None:
    if not name:
        return None
    slug = name.lower().strip().replace(" ", "-")
    result = await db.execute(
        select(Discipline).where(Discipline.slug == slug)
    )
    discipline = result.scalar_one_or_none()
    if discipline is None:
        discipline = Discipline(
            name=name.strip(),
            slug=slug,
            school_id=school.id if school else None,
        )
        db.add(discipline)
        await db.flush()
    return discipline


def _gemini_auth_ok() -> bool:
    """Verifica se o Gemini CLI tem autenticação configurada."""
    gemini_login = os.environ.get("GEMINI_LOGIN", "key")
    if gemini_login == "oauth":
        gemini_home = Path(os.environ.get("GEMINI_HOME", Path.home() / ".gemini"))
        return (gemini_home / "settings.json").exists()
    # key (default)
    return bool(os.environ.get("GEMINI_API_KEY", ""))


def _gemini_env() -> dict:
    """Retorna o ambiente para subprocess do Gemini CLI com as vars de auth."""
    env = os.environ.copy()
    gemini_login = os.environ.get("GEMINI_LOGIN", "key")
    if gemini_login == "key":
        env["GEMINI_API_KEY"] = os.environ.get("GEMINI_API_KEY", "")
    # oauth: o Gemini CLI lê settings.json automaticamente, sem env var extra
    if os.environ.get("GEMINI_HOME"):
        env["GEMINI_HOME"] = os.environ["GEMINI_HOME"]
    return env


async def gemini_setup_oauth() -> bool:
    """Roda 'gemini' interativamente para fluxo OAuth.
    O usuário recebe um link, autoriza no navegador e cola o código.
    Retorna True se o setup foi bem-sucedido."""
    gemini_home = Path(os.environ.get("GEMINI_HOME", Path.home() / ".gemini"))
    gemini_home.mkdir(parents=True, exist_ok=True)

    logger.info("🔑 Iniciando Gemini CLI em modo OAuth interativo...")
    logger.info("   Um link será exibido. Abra no navegador, autorize e cole o código aqui.")
    logger.info("   O token será salvo em %s", gemini_home)

    env = os.environ.copy()
    if os.environ.get("GEMINI_HOME"):
        env["GEMINI_HOME"] = os.environ["GEMINI_HOME"]

    loop = asyncio.get_event_loop()
    try:
        # Sem -y e sem -p: modo interativo puro, o Gemini CLI guia o OAuth
        result = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                ["gemini"],
                env=env,
                timeout=300,  # 5 min pro usuário fazer OAuth
            ),
        )
        if result.returncode == 0 and (gemini_home / "settings.json").exists():
            logger.info("✅ OAuth concluído! Token salvo em %s", gemini_home / "settings.json")
            return True
        else:
            logger.error("❌ OAuth falhou (exit code %d)", result.returncode)
            return False
    except FileNotFoundError:
        logger.error("Gemini CLI não encontrado. Instale com: npm i -g @google/gemini-cli")
        return False
    except subprocess.TimeoutExpired:
        logger.error("Timeout (5 min) aguardando OAuth")
        return False


async def classify_discipline_gemini(content: str) -> dict:
    """Classifica um post usando Gemini CLI (subprocess).
    Retorna {'discipline': str, 'confidence': int, 'school': str}"""
    # Pré-verificação de auth
    if not _gemini_auth_ok():
        gemini_login = os.environ.get("GEMINI_LOGIN", "key")
        if gemini_login == "oauth":
            logger.error(
                "Gemini CLI: OAuth não configurado. Rode primeiro:\n"
                "  docker compose run --rm sync --gemini-setup"
            )
        else:
            logger.error(
                "Gemini CLI: GEMINI_API_KEY não definida no .env.\n"
                "  Obtenha em: https://aistudio.google.com/apikey\n"
                "  Ou use GEMINI_LOGIN=oauth + --gemini-setup"
            )
        return {"discipline": "Gerais", "confidence": 0, "school": ""}

    persona_path = Path(__file__).resolve().parent / "persona.md"
    try:
        persona = persona_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        persona = "You are Mariana, a cybersecurity expert."

    system_msg = (
        f"{persona}\n\n"
        "You are classifying a LinkedIn post into a cybersecurity discipline "
        "for the 'Universidade Bebê' (UBB) platform.\n"
        "Return ONLY a JSON object with these fields:\n"
        '- "discipline": the best-matching cybersecurity discipline name '
        "(e.g., OSINT, Threat Hunting, SIEM, Red Team, Blue Team, "
        "Digital Forensics, Incident Response, Cloud Security, "
        "Application Security, Network Security, Social Engineering, "
        "Governance, Cryptography, Malware Analysis, Security Awareness, "
        "Gerais)\n"
        '- "confidence": integer 0-100 indicating how sure you are '
        "about the discipline match\n"
        '- "school": the school this belongs to '
        "(e.g., 'Offensive Security', 'Defensive Security', "
        "'Security Operations', 'Cyber Reality', 'Fundamentals')\n\n"
        "If the post does not clearly fit any cybersecurity discipline, "
        'set discipline to "Gerais" and confidence to 50 or less.\n'
        "Respond with ONLY valid JSON, no markdown, no code fences."
    )

    user_msg = (
        f"Classify this LinkedIn post into a cybersecurity discipline:\n\n"
        f"{content[:2000]}\n\n"
        "Return the JSON object."
    )

    full_prompt = f"{system_msg}\n\n{user_msg}"

    gemini_model = os.environ.get("GEMINI_MODEL", "")
    cmd = ["gemini", "--skip-trust", "-y", "-p", full_prompt]
    if gemini_model:
        cmd.extend(["-m", gemini_model])

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=180,
                env=_gemini_env(),
            ),
        )
    except FileNotFoundError:
        logger.error("Gemini CLI não encontrado. Instale com: npm i -g @google/gemini-cli")
        return {"discipline": "Gerais", "confidence": 0, "school": ""}
    except subprocess.TimeoutExpired:
        logger.error("Gemini CLI timeout (180s)")
        return {"discipline": "Gerais", "confidence": 0, "school": ""}

    raw = result.stdout.strip()
    if not raw and result.stderr:
        if "Auth method" in result.stderr or "GEMINI_API_KEY" in result.stderr:
            logger.error(
                "Gemini CLI: autenticação falhou. Verifique GEMINI_API_KEY ou "
                "rode --gemini-setup para OAuth."
            )
        else:
            logger.error("Gemini CLI stderr: %s", result.stderr[:500])
        return {"discipline": "Gerais", "confidence": 0, "school": ""}

    # Tenta extrair JSON de code fences ou resposta crua
    json_match = re.search(r'\{[^{}]*"discipline"[^{}]*\}', raw, re.DOTALL)
    if json_match:
        raw = json_match.group(0)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Failed to parse Gemini response as JSON. Raw: %s", raw[:300])
        return {"discipline": "Gerais", "confidence": 0, "school": ""}

    return {
        "discipline": parsed.get("discipline", "Gerais"),
        "confidence": int(parsed.get("confidence", 0)),
        "school": parsed.get("school", ""),
    }


AGY_CLASSIFY_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "subtitle": {"type": "string"},
        "summary": {"type": "string"},
        "quote": {"type": "string"},
        "mariana_take": {"type": "string"},
        "content_type": {
            "type": "string",
            "enum": ["lesson", "lab", "awareness", "challenge", "storytelling",
                     "threat_analysis", "architecture", "hands_on", "fundamentals"],
        },
        "skill_type": {
            "type": "string",
            "enum": ["técnico", "operacional", "mindset", "awareness", "arquitetura", "carreira"],
        },
        "difficulty": {
            "type": "string",
            "enum": ["iniciante", "intermediário", "avançado", "todos os níveis"],
        },
        "discipline": {"type": "string"},
        "school": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "content_type", "discipline"],
})


def _agy_env() -> dict:
    """Ambiente para o subprocess do agy. AGY_HOME sobrescreve $HOME (onde o
    agy guarda auth/config em .gemini); sem AGY_HOME usa o $HOME do container
    (o volume gemini-config já é montado em /root/.gemini)."""
    env = os.environ.copy()
    agy_home = os.environ.get("AGY_HOME", "")
    if agy_home:
        env["HOME"] = agy_home
    return env


async def agy_setup_auth() -> bool:
    """Roda 'agy' interativamente para autenticar (o CLI guia o fluxo de
    login). O estado de auth persiste em $HOME/.gemini (AGY_HOME, se
    definido) — o mesmo volume já usado pelo Gemini CLI."""
    logger.info("🔑 Iniciando Antigravity CLI (agy) em modo interativo...")
    logger.info("   Siga as instruções na tela para autenticar.")
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                ["script", "-qec", "stty cols 200 2>/dev/null; agy", "/dev/null"],
                env=_agy_env(),
                timeout=300,
            ),
        )
        if result.returncode == 0:
            logger.info("✅ agy autenticado com sucesso.")
            return True
        logger.error("❌ Falha na autenticação do agy (exit code %d)", result.returncode)
        return False
    except FileNotFoundError:
        logger.error("agy CLI não encontrado. Instale: curl -fsSL https://antigravity.google/cli/install.sh | bash")
        return False
    except subprocess.TimeoutExpired:
        logger.error("Timeout (5 min) aguardando autenticação do agy")
        return False


async def classify_post_agy(content: str, hashtags: list[str]) -> dict:
    """Classificação completa de um post usando o Antigravity CLI (agy).
    Equivalente a OllamaService.classify_post(), mas via subprocess."""
    persona_path = Path(__file__).resolve().parent / "persona.md"
    try:
        persona = persona_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        persona = "You are Mariana, a cybersecurity expert."

    system_msg = (
        f"{persona}\n\n"
        "You are helping classify a LinkedIn post for the "
        "'Universidade Bebê' platform. Analyze the post content and "
        "produce: title (catchy), subtitle (short), summary (1-2 "
        "sentences), quote (an impactful quote from the post), "
        "mariana_take (Mariana's commentary, written as if you are "
        "Mariana), content_type, skill_type, difficulty, discipline "
        "(the cybersecurity discipline, e.g. OSINT, Red Team, Blue "
        "Team), school (e.g. Offensive Security, Defensive Security), "
        "and tags (relevant keywords)."
    )
    user_msg = (
        f"Classify this LinkedIn post:\n\nContent: {content}\n\n"
        f"Hashtags: {', '.join(hashtags)}\n\n"
        "Return the classification as structured output."
    )
    full_prompt = f"{system_msg}\n\n{user_msg}"

    agy_model = os.environ.get("AGY_MODEL", "")
    cmd = [
        "agy", "-p", full_prompt,
        "--output-format", "json",
        "--json-schema", AGY_CLASSIFY_SCHEMA,
        "--dangerously-skip-permissions",
    ]
    if agy_model:
        cmd.extend(["--model", agy_model])

    timeout_s = int(os.environ.get("AGY_TIMEOUT", "180"))
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout_s, env=_agy_env(),
            ),
        )
    except FileNotFoundError:
        logger.error("agy CLI não encontrado. Instale: curl -fsSL https://antigravity.google/cli/install.sh | bash")
        return {}
    except subprocess.TimeoutExpired:
        logger.error("agy timeout (%ds)", timeout_s)
        return {}

    raw = result.stdout.strip()
    combined = f"{raw}\n{result.stderr}"
    if "authentication required" in combined.lower() or "not authenticated" in combined.lower():
        logger.error(
            "agy requer autenticação. Rode:\n"
            "  docker compose run --rm -it sync python sync.py --agy-setup"
        )
        return {}

    if not raw:
        logger.error("agy stderr: %s", result.stderr[:500])
        return {}

    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Failed to parse agy envelope as JSON. Raw: %s", raw[:300])
        return {}

    if envelope.get("status") != "SUCCESS":
        logger.error("agy status=%s: %s", envelope.get("status"), raw[:300])
        return {}

    parsed = envelope.get("structured_output") or {}
    if not parsed:
        # fallback: tenta extrair JSON solto da resposta em texto livre
        response_text = envelope.get("response", "")
        json_match = re.search(r'\{.*"content_type".*\}', response_text, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
            except json.JSONDecodeError:
                parsed = {}

    return {
        "title": parsed.get("title", ""),
        "subtitle": parsed.get("subtitle", ""),
        "summary": parsed.get("summary", ""),
        "quote": parsed.get("quote", ""),
        "mariana_take": parsed.get("mariana_take", ""),
        "content_type": parsed.get("content_type", ""),
        "skill_type": parsed.get("skill_type", ""),
        "difficulty": parsed.get("difficulty", ""),
        "discipline": parsed.get("discipline", ""),
        "school": parsed.get("school", ""),
        "tags": parsed.get("tags", []),
    }


async def process_post(
    db,
    linkedin_data: dict,
    classify: Callable[[str, list[str]], Awaitable[dict]],
    update_all: bool = False,
) -> Post | None:
    linkedin_url = linkedin_data["linkedin_url"]
    result = await db.execute(
        select(Post).where(Post.linkedin_url == linkedin_url)
    )
    existing = result.scalar_one_or_none()
    if existing and existing.content_type and not update_all:
        logger.info("  Post already classified: %s", linkedin_url)
        return None
    logger.info("  Classifying post...")
    classification = await classify(
        linkedin_data.get("content", ""),
        linkedin_data.get("hashtags", []),
    )
    if existing:
        post = existing
        logger.info("  Updating post: %s", linkedin_url)
    else:
        post = Post(linkedin_url=linkedin_url)
        db.add(post)
        await db.flush()
    post.linkedin_post_id = linkedin_data.get("linkedin_post_id")
    post.content = linkedin_data.get("content", "")
    post_date_str = linkedin_data.get("post_date", "")
    if post_date_str:
        try:
            post.post_date = datetime.fromisoformat(post_date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    post.title = classification.get("title", "")
    post.subtitle = classification.get("subtitle", "")
    post.summary = classification.get("summary", "")
    post.quote = classification.get("quote", "")
    post.mariana_take = classification.get("mariana_take", "")
    post.content_type = classification.get("content_type", "")
    post.skill_type = classification.get("skill_type", "")
    post.difficulty = classification.get("difficulty", "")
    post.indexed_at = datetime.utcnow()
    school = await get_or_create_school(db, classification.get("school", ""))
    if school:
        post.school_id = school.id
    discipline = await get_or_create_discipline(db, classification.get("discipline", ""), school)
    if discipline:
        post.discipline_id = discipline.id
    tag_names = list(classification.get("tags", []))
    for h in linkedin_data.get("hashtags", []):
        if h not in tag_names:
            tag_names.append(h)
    if existing:
        post.tags.clear()
    for tag_name in tag_names:
        tag = await get_or_create_tag(db, tag_name)
        post.tags.append(tag)
    post.raw_json = {"linkedin": linkedin_data, "classification": classification}
    await db.flush()
    logger.info("  Generating embedding...")
    try:
        embed_text = " ".join(filter(None, [post.title, post.subtitle, post.summary, post.content]))
        embedding = await compute_post_embedding(embed_text)
        post.embedding = embedding
    except Exception as e:
        logger.warning("  Embedding generation failed: %s", e)
    await db.flush()
    logger.info("  Post ID %d processed successfully", post.id)
    return post


async def classify_pending_posts(
    process_count: int,
    classifier: str,
    update_all: bool,
    push_url: str,
    push_token: str,
    skip_push: bool,
) -> int:
    """FASE 4: classifica com IA os posts capturados que ainda não têm
    content_type (ou todos, se update_all). Ollama e agy usam o
    classificador profundo (preenche title/subtitle/summary/quote/
    mariana_take/content_type/skill_type/difficulty/tags/embedding).
    Gemini ainda não tem um classificador profundo equivalente — nesse
    caso mantém a classificação leve de disciplina/escola.
    """
    where_clause = (
        "1=1" if update_all
        else "p.id IS NULL OR p.content_type IS NULL OR p.content_type = ''"
    )
    deep_classify: Callable[[str, list[str]], Awaitable[dict]] | None = None
    if classifier == "ollama":
        deep_classify = OllamaService().classify_post
    elif classifier == "agy":
        deep_classify = classify_post_agy
    processed = 0

    async with async_session() as db:
        result = await db.execute(
            text(
                f"SELECT rp.id, rp.raw_json FROM raw_posts rp "
                f"LEFT JOIN posts p ON p.linkedin_url = rp.linkedin_url "
                f"WHERE {where_clause} ORDER BY rp.id LIMIT :limit"
            ),
            {"limit": process_count},
        )
        pending = result.fetchall()
        if not pending:
            logger.info("✅ Nenhum post pendente para classificar.")
            return 0

        logger.info("📦 %d posts pendentes para processar.", len(pending))
        for row_id, raw_json in pending:
            linkedin_url = raw_json.get("link", "")
            content = (raw_json.get("description") or raw_json.get("content") or "")[:2000]
            if not linkedin_url:
                continue
            logger.info("[%d/%d] Classificando post #%d...", processed + 1, len(pending), row_id)

            if classifier == "gemini":
                classification = await classify_discipline_gemini(content)
                confidence = classification["confidence"]
                discipline_name = classification["discipline"] if confidence >= 90 else "Gerais"
                school_name = classification.get("school", "") if discipline_name != "Gerais" else ""
                logger.info("  ↳ disciplina=%s (confiança=%d%%), school=%s", discipline_name, confidence, school_name or "—")
                school = await get_or_create_school(db, school_name)
                discipline = await get_or_create_discipline(db, discipline_name, school)
                result = await db.execute(select(Post).where(Post.linkedin_url == linkedin_url))
                existing = result.scalar_one_or_none()
                if existing:
                    if discipline:
                        existing.discipline_id = discipline.id
                    if school:
                        existing.school_id = school.id
                else:
                    db.add(Post(
                        linkedin_url=linkedin_url,
                        title=content.split("\n")[0][:100].strip(),
                        content=content,
                        discipline_id=discipline.id if discipline else None,
                        school_id=school.id if school else None,
                        indexed_at=datetime.utcnow(),
                    ))
                await db.commit()
            else:
                linkedin_data = {
                    "linkedin_url": linkedin_url,
                    "linkedin_post_id": raw_json.get("linkedin_post_id", ""),
                    "content": content,
                    "hashtags": raw_json.get("hashtags", []),
                    "post_date": raw_json.get("date", ""),
                }
                await process_post(db, linkedin_data, deep_classify, update_all=update_all)
                await db.commit()

            processed += 1

        logger.info("🤖 FASE 4 completa: %d posts classificados.", processed)

    if processed > 0 and push_url and not skip_push:
        logger.info("📤 Enviando seed para VM (%d posts classificados)...", processed)
        import httpx
        async with async_session() as db2:
            sch_rows = (await db2.execute(text("SELECT name, slug, description, color, icon FROM schools"))).fetchall()
            schools = [{"name": r[0], "slug": r[1], "description": r[2], "color": r[3], "icon": r[4]} for r in sch_rows]
            disc_rows = (await db2.execute(text("SELECT d.name, d.slug, d.description, d.icon, d.color, s.name FROM disciplines d LEFT JOIN schools s ON s.id = d.school_id"))).fetchall()
            disciplines = [{"name": r[0], "slug": r[1], "description": r[2], "icon": r[3], "color": r[4], "school_name": r[5]} for r in disc_rows]
            post_rows = (await db2.execute(text(
                "SELECT p.linkedin_url, p.title, p.subtitle, p.summary, p.quote, p.mariana_take, p.content_type, p.difficulty, d.name, s.name "
                "FROM posts p LEFT JOIN disciplines d ON d.id = p.discipline_id LEFT JOIN schools s ON s.id = p.school_id "
                "WHERE p.discipline_id IS NOT NULL"
            ))).fetchall()
            posts = [{"linkedin_url": r[0], "title": r[1], "subtitle": r[2], "summary": r[3], "quote": r[4], "mariana_take": r[5], "content_type": r[6], "difficulty": r[7], "discipline_name": r[8], "school_name": r[9]} for r in post_rows]
        seed = {"schools": schools, "disciplines": disciplines, "posts": posts}
        try:
            r = httpx.post(f"{push_url.rstrip('/')}/api/sync/seed", json=seed, headers={"Authorization": f"Bearer {push_token}"} if push_token else {}, timeout=60, verify=False)
            if r.status_code == 200:
                logger.info("📤 Seed enviado: %d schools, %d disciplines, %d posts", len(schools), len(disciplines), len(posts))
            else:
                logger.warning("⚠️  Seed falhou: HTTP %d", r.status_code)
        except Exception as e:
            logger.warning("⚠️  Seed falhou: %s", e)

    return processed


async def generate_relations(db, ollama: OllamaService):
    logger.info("Generating semantic relations...")
    result = await db.execute(select(Post).where(Post.title.isnot(None), Post.summary.isnot(None)))
    all_posts = result.scalars().all()
    if len(all_posts) < 2:
        logger.info("  Not enough posts for relations (need >= 2)")
        return
    posts_data = []
    for p in all_posts:
        posts_data.append({
            "id": p.id, "title": p.title or "", "summary": p.summary or "",
            "discipline": p.discipline.name if p.discipline else "",
            "tags": [t.name for t in p.tags] if p.tags else [],
        })
    relations = await ollama.generate_relations(posts_data)
    await db.execute(SemanticRelation.__table__.delete())
    count = 0
    for rel in relations:
        source_id = rel.get("source_id")
        target_id = rel.get("target_id")
        score = rel.get("similarity_score", 0.0)
        rel_type = rel.get("relation_type", "")
        if not source_id or not target_id:
            continue
        relation = SemanticRelation(source_post_id=source_id, target_post_id=target_id, similarity_score=score, relation_type=rel_type)
        db.add(relation)
        count += 1
    await db.flush()
    logger.info("  Created %d semantic relations", count)


async def main():
    parser = argparse.ArgumentParser(description="Sync LinkedIn posts to Universidade Bebê")
    parser.add_argument("--headless", action="store_true", default=None, help="Run browser in headless mode")
    parser.add_argument("--no-headless", action="store_false", dest="headless", help="Run browser with visible UI")
    parser.add_argument("--max-posts", type=int, default=20, help="Maximum number of posts to sync")
    parser.add_argument("--update-all", action="store_true", default=False, help="Re-process existing posts")
    parser.add_argument("--push-all", action="store_true", default=False, help="Push all existing raw_posts to VM")
    parser.add_argument(
        "--classifier", choices=["ollama", "gemini", "agy"],
        default=os.environ.get("CLASSIFIER", "ollama"),
        help="LLM classifier to use (default: ollama, or set CLASSIFIER env var)"
    )
    parser.add_argument("--no-push", action="store_true", default=False, help="Skip push to remote VM (auto-enabled when NODE_ENV=production)")
    parser.add_argument("--firefox", action="store_true", default=False, help="Use Firefox stealth (invisible_playwright) instead of Chromium")
    parser.add_argument("--gemini-setup", action="store_true", default=False, help="Run Gemini CLI OAuth setup interactively and exit")
    parser.add_argument("--agy-setup", action="store_true", default=False, help="Run Antigravity CLI (agy) auth setup interactively and exit")
    parser.set_defaults(headless=None)
    args = parser.parse_args()

    # ── Gemini OAuth setup (interativo, sai depois) ──
    if args.gemini_setup:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        ok = await gemini_setup_oauth()
        if ok:
            logger.info("✅ Gemini OAuth configurado. Agora pode rodar o sync normalmente.")
        else:
            logger.error("❌ Falha no setup OAuth. Tente novamente ou use GEMINI_LOGIN=key.")
        sys.exit(0 if ok else 1)

    # ── agy auth setup (interativo, sai depois) ──
    if args.agy_setup:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        ok = await agy_setup_auth()
        if ok:
            logger.info("✅ agy configurado. Agora pode rodar o sync com --classifier agy (ou CLASSIFIER=agy).")
        else:
            logger.error("❌ Falha no setup do agy. Tente novamente.")
        sys.exit(0 if ok else 1)

    headless = os.environ.get("PLAYWRIGHT_HEADLESS", "false").lower() == "true" if args.headless is None else args.headless

    log_level = os.environ.get("LOG_LEVEL", "info")
    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO), format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # Em produção nunca faz push (já está no banco certo)
    is_production = os.environ.get("NODE_ENV", "").lower() == "production"
    skip_push = args.no_push or is_production
    if is_production and not args.no_push:
        logger.info("🏭 NODE_ENV=production — push para VM desativado automaticamente")

    url_target = os.environ.get("URL_TARGET", "")
    linkedin_email = os.environ.get("LINKEDIN_EMAIL", "")
    linkedin_password = os.environ.get("LINKEDIN_PASSWORD", "")

    # --- Config do modo de operação ---
    sync_mode = os.environ.get("SYNC_MODE", "monitor")
    max_scrolls = int(os.environ.get("MAX_SCROLLS", "40"))
    dupes_to_stop = int(os.environ.get("CONSECUTIVE_DUPES_TO_STOP", "5"))
    scroll_delay_min = int(os.environ.get("SCROLL_DELAY_MIN", "3"))
    scroll_delay_max = int(os.environ.get("SCROLL_DELAY_MAX", "8"))

    if args.push_all:
        # --- MODO PUSH-ALL: envia todos os raw_posts existentes pra VM ---
        push_url = os.environ.get("SYNC_PUSH_URL", "")
        push_token = os.environ.get("SYNC_PUSH_TOKEN", "")
        if not push_url:
            logger.error("SYNC_PUSH_URL não configurado no .env")
            sys.exit(1)
        logger.info("📤 Push-all: enviando todos os raw_posts para %s ...", push_url)
        import httpx
        headers = {"Authorization": f"Bearer {push_token}"} if push_token else {}
        endpoint = f"{push_url.rstrip('/')}/api/sync/raw-posts"

        # Pre-flight: confirma que o endpoint está respondendo antes de começar
        for attempt in range(1, 11):
            try:
                r = httpx.get(endpoint.replace("/raw-posts", "-info"), headers=headers, timeout=10, verify=False)
                if r.status_code == 200:
                    logger.info("📡 VM respondeu ao pre-flight (tentativa %d)", attempt)
                    break
            except Exception as e:
                logger.warning("⚠️  Pre-flight tentativa %d: %s", attempt, e)
            logger.info("⏳ Aguardando VM... (%d/10)", attempt)
            time.sleep(3)
        else:
            logger.error("❌ VM não respondeu após 10 tentativas. Abortando.")
            return

        async with async_session() as db:
            result = await db.execute(text("SELECT raw_json FROM raw_posts ORDER BY id"))
            all_posts = [row[0] for row in result.fetchall()]
        batch_size = 100
        total_inserted = 0
        total_batches = (len(all_posts) + batch_size - 1) // batch_size
        for i in range(0, len(all_posts), batch_size):
            batch = all_posts[i:i + batch_size]
            batch_num = i // batch_size + 1
            r = httpx.post(endpoint, json={"posts": batch}, headers=headers, timeout=60, verify=False)
            if r.status_code != 200:
                logger.error("❌ Lote %d/%d: HTTP %d — resposta: %s", batch_num, total_batches, r.status_code, r.text[:200])
                logger.error("❌ Abortando push. Corrija o problema na VM e rode novamente.")
                return
            result = r.json()
            inserted = result.get("inserted", 0)
            total_inserted += inserted
            logger.info("📤 Lote %d/%d: %d inseridos", batch_num, total_batches, inserted)
            if i + batch_size < len(all_posts):
                time.sleep(0.5)  # pacing: evita sobrecarregar o nginx
        logger.info("📤 Push-all: raw_posts completo (%d enviados)", total_inserted)

        # Fase 2: enviar dados classificados (schools, disciplines, posts)
        logger.info("📤 Push-all: enviando dados classificados (seed)...")
        async with async_session() as db:
            # Schools
            sch_rows = (await db.execute(text("SELECT name, slug, description, color, icon FROM schools"))).fetchall()
            schools = [{"name": r[0], "slug": r[1], "description": r[2], "color": r[3], "icon": r[4]} for r in sch_rows]
            # Disciplines
            disc_rows = (await db.execute(text("SELECT d.name, d.slug, d.description, d.icon, d.color, s.name as school_name FROM disciplines d LEFT JOIN schools s ON s.id = d.school_id"))).fetchall()
            disciplines = [{"name": r[0], "slug": r[1], "description": r[2], "icon": r[3], "color": r[4], "school_name": r[5]} for r in disc_rows]
            # Posts (classified)
            post_rows = (await db.execute(text("SELECT p.linkedin_url, p.title, p.subtitle, p.summary, p.quote, p.mariana_take, p.content_type, p.difficulty, d.name as disc_name, s.name as school_name FROM posts p LEFT JOIN disciplines d ON d.id = p.discipline_id LEFT JOIN schools s ON s.id = p.school_id WHERE p.discipline_id IS NOT NULL"))).fetchall()
            posts = [{"linkedin_url": r[0], "title": r[1], "subtitle": r[2], "summary": r[3], "quote": r[4], "mariana_take": r[5], "content_type": r[6], "difficulty": r[7], "discipline_name": r[8], "school_name": r[9]} for r in post_rows]

        seed_payload = {"schools": schools, "disciplines": disciplines, "posts": posts}
        seed_endpoint = f"{push_url.rstrip('/')}/api/sync/seed"
        r = httpx.post(seed_endpoint, json=seed_payload, headers=headers, timeout=60, verify=False)
        if r.status_code == 200:
            logger.info("📤 Seed completo: %d schools, %d disciplines, %d posts", len(schools), len(disciplines), len(posts))
        else:
            logger.error("❌ Seed falhou: HTTP %d — %s", r.status_code, r.text[:200])
        return

    if sync_mode == "process":
        # --- MODO PROCESS-ONLY: pula extração, vai direto pra FASE 4 ---
        logger.info("⚙️  Modo process-only — iniciando classificação...")
        logger.info("Initializing database...")
        await init_db()
        async with async_session() as db:
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS raw_posts (
                    id SERIAL PRIMARY KEY, linkedin_url TEXT UNIQUE NOT NULL,
                    raw_json JSONB NOT NULL, created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            await db.commit()
        logger.info("✅ Banco pronto")

        process_count = int(os.environ.get("PROCESS_COUNT", "10"))
        classifier = args.classifier
        classifier_label = "Gemini CLI" if classifier == "gemini" else f"Ollama ({os.environ.get('OLLAMA_MODEL', '')})"
        logger.info("🤖 FASE 4: Classificando até %d posts com %s...", process_count, classifier_label)

        push_url = os.environ.get("SYNC_PUSH_URL", "")
        push_token = os.environ.get("SYNC_PUSH_TOKEN", "")
        await classify_pending_posts(
            process_count=process_count,
            classifier=classifier,
            update_all=args.update_all,
            push_url=push_url,
            push_token=push_token,
            skip_push=skip_push,
        )
        logger.info("⏹️  Parando (process-only).")
        return

    # Delay inicial
    if sync_mode == "capture":
        delay = random.randint(120, 240)
    else:
        delay = random.randint(0, 30)
    logger.info("⏳ Modo %s — aguardando %d segundos (%d min)...", sync_mode, delay, delay // 60)
    await asyncio.sleep(delay)
    logger.info("Starting sync — mode=%s, target=%s", sync_mode, url_target)
    logger.info("Max posts: %d | Headless: %s | Scrolls: %d | Dupes-stop: %d", args.max_posts, headless, max_scrolls, dupes_to_stop)

    if not url_target:
        logger.error("URL_TARGET not configured")
        sys.exit(1)
    if not linkedin_email or not linkedin_password:
        logger.error("LinkedIn credentials not configured")
        sys.exit(1)

    logger.info("Initializing database...")
    await init_db()
    async with async_session() as db:
        await db.execute(text("""
            CREATE TABLE IF NOT EXISTS raw_posts (
                id SERIAL PRIMARY KEY, linkedin_url TEXT UNIQUE NOT NULL,
                raw_json JSONB NOT NULL, created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        await db.commit()
    logger.info("✅ Banco pronto")

    async with LinkedInAgent(email=linkedin_email, password=linkedin_password, headless=headless, use_firefox=args.firefox) as agent:
        logged_in = await agent.login()
        if not logged_in:
            logger.error("LinkedIn login failed")
            sys.exit(1)
        logger.info("✅ Login bem-sucedido!")
        logger.info("🌐 Navegando para URL_TARGET: %s", url_target)

        # Firefox/invisible_playwright pode crashar com erro de frame tracking
        # ao navegar direto pós-login. Navegar primeiro para about:blank limpa
        # o estado de frames e evita o crash.
        try:
            await agent.page.goto("about:blank", wait_until="commit", timeout=10000)
            await agent.page.wait_for_timeout(1000)
        except Exception:
            pass  # about:blank pode falhar se conexão já caiu, mas tentamos o target mesmo assim

        try:
            await agent.page.goto(url_target, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            logger.error("❌ Falha ao navegar para URL_TARGET: %s", e)
            return

        await agent.page.wait_for_timeout(3000)
        logger.info("📄 Página carregada: %s", (await agent.page.title())[:100])
        logger.info("📍 URL atual: %s", agent.page.url[:100])

        total_saved = 0
        new_posts_for_push = []
        seen_urls = set()

        # Firefox com invisible_playwright respeita CSP e bloqueia page.evaluate().
        # Usamos métodos alternativos via locator API (sem eval) nesse caso.
        no_eval = args.firefox

        async with async_session() as db:
            if sync_mode == "capture":
                stale_infinite = 0
                for scroll_n in range(max_scrolls):
                    if no_eval:
                        raw = await agent.extract_feed_posts_no_eval()
                    else:
                        raw = await agent.page.evaluate(
                            """() => {
                            const containers = document.querySelectorAll('.feed-shared-update-v2');
                            const results = [];
                            for (const c of containers) {
                                const linkEl = c.querySelector('a[href*="/posts/"], a[href*="activity-"], a[href*="/feed/update/"]');
                                const link = linkEl ? (linkEl.href || '') : '';
                                const activityMatch = link.match(/activity[-:](\\d+)/) || (c.getAttribute('data-urn') || '').match(/activity:(\\d+)/);
                                const activityId = activityMatch ? activityMatch[1] : '';
                                const postUrl = link || (activityId ? 'https://www.linkedin.com/feed/update/urn:li:activity:' + activityId : '');
                                const textEl = c.querySelector('.feed-shared-text, .feed-shared-text__text-visual, .feed-shared-update-v2__description, .update-components-text, .feed-shared-inline-show-more-text');
                                const text = textEl ? textEl.innerText.trim() : '';
                                const timeEl = c.querySelector('time');
                                const date = timeEl ? (timeEl.getAttribute('datetime') || timeEl.innerText) : '';
                                const hashtags = [...text.matchAll(/#(\\w+)/g)].map(m => m[1]);
                                if (postUrl && text) results.push({link: postUrl, content: text, date: date, hashtags: hashtags});
                            }
                            return results;
                        }"""
                        )
                    consecutive_dupes = 0
                    scroll_saved = 0
                    for p in raw:
                        link = p.get("link") or ""
                        if link in seen_urls: continue
                        seen_urls.add(link)
                        post_json = {"title": (p.get("content") or "")[:100].split("\n")[0].strip(), "link": link, "description": p.get("content") or "", "post_date": p.get("date") or "", "hashtags": p.get("hashtags") or []}
                        result = await db.execute(text("SELECT id FROM raw_posts WHERE linkedin_url = :url"), {"url": link})
                        if result.scalar_one_or_none():
                            consecutive_dupes += 1
                        else:
                            consecutive_dupes = 0
                            await db.execute(text("INSERT INTO raw_posts (linkedin_url, raw_json) VALUES (:url, :json)"), {"url": link, "json": json.dumps(post_json, ensure_ascii=False)})
                            await db.commit()
                            new_posts_for_push.append(post_json)
                            scroll_saved += 1
                    total_saved += scroll_saved
                    logger.info("📊 Scroll %d/%d: %d visíveis, %d novos (dup: %d)", scroll_n + 1, max_scrolls, len(raw), scroll_saved, consecutive_dupes)
                    if consecutive_dupes >= dupes_to_stop and scroll_n >= 3:
                        logger.info("⏹️  %d dups consecutivas — fim.", consecutive_dupes)
                        break

                    # Hybrid scroll with anti-detection + jump-to-oldest
                    if scroll_n < max_scrolls - 1:
                        d = random.randint(scroll_delay_min, scroll_delay_max)
                        if scroll_saved == 0 and scroll_n > 0:
                            stale_infinite += 1
                        else:
                            stale_infinite = 0

                        # Simula mouse humano entre scrolls (anti-detecção)
                        if scroll_n % 3 == 0:
                            vp = agent.page.viewport_size or {"width": 1280, "height": 720}
                            mx = random.randint(vp["width"] // 4, vp["width"] * 3 // 4)
                            my = random.randint(vp["height"] // 4, vp["height"] * 3 // 4)
                            await agent.page.mouse.move(mx, my)

                        if stale_infinite >= 5:
                            # Salta pro último post visível no DOM pra forçar carregamento de mais antigos
                            last_post = agent.page.locator('.feed-shared-update-v2').last
                            if await last_post.count():
                                await last_post.scroll_into_view_if_needed()
                            mode = "jump-oldest"
                            stale_infinite = 0
                        elif stale_infinite >= 3 and scroll_n % 8 == 0:
                            await agent.page.keyboard.press("End")
                            mode = "infinite"
                        elif stale_infinite >= 2:
                            step = random.randint(200, 600)  # variável como humano
                            await agent.page.mouse.wheel(0, step)
                            mode = f"incremental({step}px)"
                        else:
                            await agent.page.keyboard.press("End")
                            mode = "infinite"
                        logger.info("⏳ Scroll %d→%d (%s, delay %ds)", scroll_n + 1, scroll_n + 2, mode, d)
                        await agent.page.wait_for_timeout(d * 1000)
            else:
                if no_eval:
                    raw = await agent.extract_feed_posts_no_eval()
                else:
                    raw = await agent.page.evaluate(
                        """() => {
                        const containers = document.querySelectorAll('.feed-shared-update-v2');
                        const results = [];
                        for (const c of containers) {
                            const linkEl = c.querySelector('a[href*="/posts/"], a[href*="activity-"], a[href*="/feed/update/"]');
                            const link = linkEl ? (linkEl.href || '') : '';
                            const activityMatch = link.match(/activity[-:](\\d+)/) || (c.getAttribute('data-urn') || '').match(/activity:(\\d+)/);
                            const activityId = activityMatch ? activityMatch[1] : '';
                            const postUrl = link || (activityId ? 'https://www.linkedin.com/feed/update/urn:li:activity:' + activityId : '');
                            const textEl = c.querySelector('.feed-shared-text, .feed-shared-text__text-visual, .feed-shared-update-v2__description, .update-components-text, .feed-shared-inline-show-more-text');
                            const text = textEl ? textEl.innerText.trim() : '';
                            const timeEl = c.querySelector('time');
                            const date = timeEl ? (timeEl.getAttribute('datetime') || timeEl.innerText) : '';
                            const hashtags = [...text.matchAll(/#(\\w+)/g)].map(m => m[1]);
                            if (postUrl && text) results.push({link: postUrl, content: text, date: date, hashtags: hashtags});
                        }
                        return results;
                    }"""
                    )
                for p in raw:
                    link = p.get("link") or ""
                    if link in seen_urls: continue
                    seen_urls.add(link)
                    post_json = {"title": (p.get("content") or "")[:100].split("\n")[0].strip(), "link": link, "description": p.get("content") or "", "post_date": p.get("date") or "", "hashtags": p.get("hashtags") or []}
                    result = await db.execute(text("SELECT id FROM raw_posts WHERE linkedin_url = :url"), {"url": link})
                    if result.scalar_one_or_none():
                        logger.info("⏹️  Primeiro dupe — parando (monitor).")
                        break
                    await db.execute(text("INSERT INTO raw_posts (linkedin_url, raw_json) VALUES (:url, :json)"), {"url": link, "json": json.dumps(post_json, ensure_ascii=False)})
                    await db.commit()
                    new_posts_for_push.append(post_json)
                    total_saved += 1
        logger.info("📊 Total salvo: %d posts", total_saved)

    # --- Push para VM (se configurado e não em produção) ---
    push_url = os.environ.get("SYNC_PUSH_URL", "")
    push_token = os.environ.get("SYNC_PUSH_TOKEN", "")
    if push_url and total_saved > 0 and not skip_push:
        try:
            import httpx
            headers = {"Authorization": f"Bearer {push_token}"} if push_token else {}
            r = httpx.post(f"{push_url.rstrip('/')}/api/sync/raw-posts", json={"posts": new_posts_for_push}, headers=headers, timeout=30, verify=False)
            result = r.json()
            logger.info("📤 Push para VM: %d inseridos (de %d enviados)", result.get("inserted", 0), len(new_posts_for_push))
        except Exception as e:
            logger.warning("⚠️  Push para VM falhou: %s", e)

    # --- FASE 4: classificar posts ---
    process_count = int(os.environ.get("PROCESS_COUNT", "10"))
    classifier = args.classifier
    classifier_label = "Gemini CLI" if classifier == "gemini" else f"Ollama ({os.environ.get('OLLAMA_MODEL', '')})"
    logger.info("🤖 FASE 4: Classificando até %d posts com %s...", process_count, classifier_label)
    logger.info("⏳ Isso pode levar vários minutos...")

    await classify_pending_posts(
        process_count=process_count,
        classifier=classifier,
        update_all=args.update_all,
        push_url=push_url,
        push_token=push_token,
        skip_push=skip_push,
    )

    logger.info("⏹️  Parando aqui (FASE 4).")


if __name__ == "__main__":
    asyncio.run(main())
