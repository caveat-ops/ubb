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

from app.database import async_session, init_db
from app.models import Discipline, Post, School, SemanticRelation, Tag, post_tags
from app.services.embedding import compute_post_embedding
from app.services.linkedin_agent import LinkedInAgent
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


async def process_post(
    db,
    linkedin_data: dict,
    ollama: OllamaService,
    update_all: bool = False,
) -> Post | None:
    linkedin_url = linkedin_data["linkedin_url"]
    result = await db.execute(
        select(Post).where(Post.linkedin_url == linkedin_url)
    )
    existing = result.scalar_one_or_none()
    if existing and not update_all:
        logger.info("  Post already exists: %s", linkedin_url)
        return None
    logger.info("  Classifying post with Ollama...")
    classification = await ollama.classify_post(
        content=linkedin_data.get("content", ""),
        hashtags=linkedin_data.get("hashtags", []),
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
        "--classifier", choices=["ollama", "gemini"],
        default=os.environ.get("CLASSIFIER", "ollama"),
        help="LLM classifier to use (default: ollama, or set CLASSIFIER env var)"
    )
    parser.add_argument("--no-push", action="store_true", default=False, help="Skip push to remote VM (auto-enabled when NODE_ENV=production)")
    parser.add_argument("--firefox", action="store_true", default=False, help="Use Firefox stealth (invisible_playwright) instead of Chromium")
    parser.add_argument("--gemini-setup", action="store_true", default=False, help="Run Gemini CLI OAuth setup interactively and exit")
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

        ollama = None
        if classifier == "ollama":
            from app.services.ollama_service import OllamaService
            ollama = OllamaService()

        async with async_session() as db:
            result = await db.execute(
                text("SELECT rp.id, rp.raw_json FROM raw_posts rp LEFT JOIN posts p ON p.linkedin_url = rp.linkedin_url WHERE p.id IS NULL ORDER BY rp.id LIMIT :limit"),
                {"limit": process_count},
            )
            unprocessed = result.fetchall()
            if not unprocessed:
                logger.info("✅ Nenhum post pendente.")
            else:
                logger.info("📦 %d posts pendentes.", len(unprocessed))
                processed = 0
                for row_id, raw_json in unprocessed:
                    content = (raw_json.get("description") or raw_json.get("content") or "")[:2000]
                    linkedin_url = raw_json.get("link", "")
                    logger.info("[%d/%d] Classificando post #%d...", processed + 1, len(unprocessed), row_id)
                    if classifier == "gemini":
                        classification = await classify_discipline_gemini(content)
                    else:
                        classification = await ollama.classify_discipline(content)
                    confidence = classification["confidence"]
                    discipline_name = classification["discipline"] if confidence >= 90 else "Gerais"
                    school_name = classification.get("school", "") if discipline_name != "Gerais" else ""
                    logger.info("  ↳ disciplina=%s (confiança=%d%%), school=%s", discipline_name, confidence, school_name or "—")

                    # Cria/encontra school primeiro (disciplina depende dela)
                    school_id = None
                    if school_name:
                        sch_result = await db.execute(text("SELECT id FROM schools WHERE name = :name"), {"name": school_name})
                        sch_row = sch_result.fetchone()
                        if sch_row:
                            school_id = sch_row[0]
                        else:
                            sch_result = await db.execute(text("INSERT INTO schools (name, slug) VALUES (:name, :slug) RETURNING id"), {"name": school_name, "slug": school_name.lower().replace(" ", "-")})
                            school_id = sch_result.fetchone()[0]
                            await db.commit()

                    # Cria/encontra disciplina com school_id
                    disc_result = await db.execute(text("SELECT id, school_id FROM disciplines WHERE name = :name"), {"name": discipline_name})
                    disc_row = disc_result.fetchone()
                    if disc_row:
                        discipline_id = disc_row[0]
                        # Atualiza school_id se estiver nulo e agora temos um
                        if disc_row[1] is None and school_id is not None:
                            await db.execute(text("UPDATE disciplines SET school_id = :sid WHERE id = :did"), {"sid": school_id, "did": discipline_id})
                            await db.commit()
                    else:
                        disc_result = await db.execute(text("INSERT INTO disciplines (name, slug, school_id) VALUES (:name, :slug, :sid) RETURNING id"), {"name": discipline_name, "slug": discipline_name.lower().replace(" ", "-"), "sid": school_id})
                        discipline_id = disc_result.fetchone()[0]
                        await db.commit()
                        logger.info("  ↳ Nova disciplina: %s (id=%d)", discipline_name, discipline_id)

                    title = (content or "")[:100].split("\n")[0].strip()
                    await db.execute(text("INSERT INTO posts (linkedin_url, title, content, discipline_id, school_id, indexed_at) VALUES (:url, :title, :content, :disc_id, :sch_id, NOW())"), {"url": linkedin_url, "title": title, "content": content, "disc_id": discipline_id, "sch_id": school_id})
                    await db.commit()
                    processed += 1
                logger.info("🤖 FASE 4 completa: %d posts classificados.", processed)
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

    ollama = None
    if classifier == "ollama":
        from app.services.ollama_service import OllamaService
        ollama = OllamaService()

    async with async_session() as db:
        result = await db.execute(
            text("SELECT rp.id, rp.raw_json FROM raw_posts rp LEFT JOIN posts p ON p.linkedin_url = rp.linkedin_url WHERE p.id IS NULL ORDER BY rp.id LIMIT :limit"),
            {"limit": process_count},
        )
        unprocessed = result.fetchall()
        if not unprocessed:
            logger.info("✅ Nenhum post pendente para classificar.")
        else:
            logger.info("📦 %d posts pendentes para processar.", len(unprocessed))
            processed = 0
            for row_id, raw_json in unprocessed:
                content = (raw_json.get("description") or raw_json.get("content") or "")[:2000]
                linkedin_url = raw_json.get("link", "")
                logger.info("[%d/%d] Classificando post #%d...", processed + 1, len(unprocessed), row_id)
                if classifier == "gemini":
                    classification = await classify_discipline_gemini(content)
                else:
                    classification = await ollama.classify_discipline(content)
                confidence = classification["confidence"]
                discipline_name = classification["discipline"] if confidence >= 90 else "Gerais"
                school_name = classification.get("school", "") if discipline_name != "Gerais" else ""
                logger.info("  ↳ disciplina=%s (confiança=%d%%), school=%s", discipline_name, confidence, school_name or "—")

                # Cria/encontra school primeiro
                school_id = None
                if school_name:
                    sch_result = await db.execute(text("SELECT id FROM schools WHERE name = :name"), {"name": school_name})
                    sch_row = sch_result.fetchone()
                    if sch_row:
                        school_id = sch_row[0]
                    else:
                        sch_result = await db.execute(text("INSERT INTO schools (name, slug) VALUES (:name, :slug) RETURNING id"), {"name": school_name, "slug": school_name.lower().replace(" ", "-")})
                        school_id = sch_result.fetchone()[0]
                        await db.commit()

                disc_result = await db.execute(text("SELECT id, school_id FROM disciplines WHERE name = :name"), {"name": discipline_name})
                disc_row = disc_result.fetchone()
                if disc_row:
                    discipline_id = disc_row[0]
                    if disc_row[1] is None and school_id is not None:
                        await db.execute(text("UPDATE disciplines SET school_id = :sid WHERE id = :did"), {"sid": school_id, "did": discipline_id})
                        await db.commit()
                else:
                    disc_result = await db.execute(text("INSERT INTO disciplines (name, slug, school_id) VALUES (:name, :slug, :sid) RETURNING id"), {"name": discipline_name, "slug": discipline_name.lower().replace(" ", "-"), "sid": school_id})
                    discipline_id = disc_result.fetchone()[0]
                    await db.commit()
                    logger.info("  ↳ Nova disciplina: %s (id=%d)", discipline_name, discipline_id)

                title = (content or "")[:100].split("\n")[0].strip()
                await db.execute(text("INSERT INTO posts (linkedin_url, title, content, discipline_id, school_id, indexed_at) VALUES (:url, :title, :content, :disc_id, :sch_id, NOW())"), {"url": linkedin_url, "title": title, "content": content, "disc_id": discipline_id, "sch_id": school_id})
                await db.commit()
                processed += 1
            logger.info("🤖 FASE 4 completa: %d posts classificados.", processed)

            # Push do seed se houve classificações novas, push configurado, e não em produção
            if processed > 0 and push_url and not skip_push:
                logger.info("📤 Enviando seed para VM (%d novos posts)...", processed)
                import httpx
                async with async_session() as db2:
                    sch_rows = (await db2.execute(text("SELECT name, slug, description, color, icon FROM schools"))).fetchall()
                    schools = [{"name": r[0], "slug": r[1], "description": r[2], "color": r[3], "icon": r[4]} for r in sch_rows]
                    disc_rows = (await db2.execute(text("SELECT d.name, d.slug, d.description, d.icon, d.color, s.name FROM disciplines d LEFT JOIN schools s ON s.id = d.school_id"))).fetchall()
                    disciplines = [{"name": r[0], "slug": r[1], "description": r[2], "icon": r[3], "color": r[4], "school_name": r[5]} for r in disc_rows]
                    post_rows = (await db2.execute(text("SELECT p.linkedin_url, p.title, p.subtitle, p.summary, p.quote, p.mariana_take, p.content_type, p.difficulty, d.name, s.name FROM posts p LEFT JOIN disciplines d ON d.id = p.discipline_id LEFT JOIN schools s ON s.id = p.school_id WHERE p.discipline_id IS NOT NULL"))).fetchall()
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

    logger.info("⏹️  Parando aqui (FASE 4).")


if __name__ == "__main__":
    asyncio.run(main())
