from typing import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models import Discipline, Post, School, Tag, post_tags
from app.services.embedding import compute_post_embedding
from app.services.linkedin_agent import LinkedInAgent
from app.services.ollama_service import OllamaService


async def run_sync(
    progress_callback: Callable[[str], None] = print,
    max_posts: int = 20,
    max_new_posts: int = 1,
    headless: bool = True,
):
    """
    Main sync pipeline:
    1. Login to LinkedIn
    2. Fetch recent posts from URL_TARGET
    3. For each new post: classify with Ollama, save to DB
    4. Generate semantic relations
    """
    progress_callback("Iniciando sincronização...")
    
    if not settings.linkedin_email or not settings.linkedin_password:
        progress_callback("ERRO: LINKEDIN_EMAIL e LINKEDIN_PASSWORD não configurados no .env")
        return
    
    if not settings.url_target:
        progress_callback("ERRO: URL_TARGET não configurada no .env")
        return
    
    # Step 1: Login to LinkedIn and fetch posts
    progress_callback("Conectando ao LinkedIn...")
    agent = LinkedInAgent(
        email=settings.linkedin_email,
        password=settings.linkedin_password,
        headless=headless,
    )
    
    try:
        logged_in = await agent.login()
        if not logged_in:
            progress_callback("ERRO: Falha ao autenticar no LinkedIn")
            return
        progress_callback("✅ Conectado ao LinkedIn")
        
        progress_callback(f"Buscando posts de: {settings.url_target}")
        posts_data = await agent.get_recent_posts(settings.url_target, max_posts=max_posts)
        
        if not posts_data:
            progress_callback("Nenhum post encontrado")
            return
        
        progress_callback(f"✅ Encontrados {len(posts_data)} posts")
    finally:
        await agent.close()
    
    # Step 2: Process each post
    ollama = OllamaService()
    new_count = 0
    existing_count = 0
    
    async with async_session() as db:
        for i, post_data in enumerate(posts_data):
            linkedin_url = post_data.get("linkedin_url", "")
            if not linkedin_url:
                continue
            
            # Check if post already exists
            result = await db.execute(select(Post).where(Post.linkedin_url == linkedin_url))
            existing = result.scalar_one_or_none()
            
            if existing:
                existing_count += 1
                progress_callback(f"  ⏭️  [{i+1}/{len(posts_data)}] Post já existe: {post_data.get('content', '')[:60]}...")
                continue
            
            new_count += 1
            content = post_data.get("content", "")
            hashtags = post_data.get("hashtags", [])
            preview = content[:60].replace("\n", " ") if content else "sem conteúdo"
            progress_callback(f"  🔄 [{i+1}/{len(posts_data)}] Processando: {preview}...")
            
            # Classify with Ollama
            progress_callback(f"    Classificando com IA ({settings.ollama_model})...")
            try:
                classification = await ollama.classify_post(content, hashtags)
            except Exception as e:
                progress_callback(f"    ⚠️  Erro na classificação: {e}. Usando valores padrão.")
                classification = {
                    "title": content.split("\n")[0][:100] if content else "Post sem título",
                    "subtitle": "",
                    "summary": "",
                    "quote": "",
                    "mariana_take": "",
                    "content_type": "lesson",
                    "skill_type": "técnico",
                    "difficulty": "todos os níveis",
                    "discipline": "",
                    "school": "",
                    "tags": hashtags[:5],
                }
            
            # Find or create School
            school_name = classification.get("school", "")
            school = None
            if school_name:
                result = await db.execute(select(School).where(School.name.ilike(f"%{school_name}%")))
                school = result.scalar_one_or_none()
                if not school:
                    school = School(name=school_name, slug=school_name.lower().replace(" ", "-"))
                    db.add(school)
                    await db.flush()
            
            # Find or create Discipline
            discipline_name = classification.get("discipline", "")
            discipline = None
            if discipline_name:
                q = select(Discipline).where(Discipline.name.ilike(f"%{discipline_name}%"))
                result = await db.execute(q)
                discipline = result.scalar_one_or_none()
                if not discipline:
                    discipline = Discipline(
                        name=discipline_name,
                        slug=discipline_name.lower().replace(" ", "-"),
                        school_id=school.id if school else None,
                    )
                    db.add(discipline)
                    await db.flush()
            
            # Generate embedding
            progress_callback(f"    Gerando embedding vetorial...")
            try:
                embedding_vector = await compute_post_embedding(content)
            except Exception as e:
                progress_callback(f"    ⚠️  Erro no embedding: {e}")
                embedding_vector = None
            
            # Create Post
            post = Post(
                linkedin_url=linkedin_url,
                linkedin_post_id=post_data.get("linkedin_post_id", ""),
                title=classification.get("title", "")[:300],
                subtitle=classification.get("subtitle", "")[:500],
                content=content,
                summary=classification.get("summary", ""),
                quote=classification.get("quote", ""),
                mariana_take=classification.get("mariana_take", ""),
                school_id=school.id if school else None,
                discipline_id=discipline.id if discipline else None,
                content_type=classification.get("content_type", "lesson")[:50],
                skill_type=classification.get("skill_type", "técnico")[:50],
                difficulty=classification.get("difficulty", "todos os níveis")[:50],
                post_date=post_data.get("post_date"),
                embedding=embedding_vector,
                raw_json=post_data,
            )
            db.add(post)
            await db.flush()
            
            # Create/associate tags
            for tag_name in classification.get("tags", []):
                if not tag_name:
                    continue
                normalized = tag_name.strip().lower()
                result = await db.execute(select(Tag).where(Tag.normalized_name == normalized))
                tag = result.scalar_one_or_none()
                if not tag:
                    tag = Tag(name=tag_name.strip(), normalized_name=normalized)
                    db.add(tag)
                    await db.flush()
                await db.execute(post_tags.insert().values(post_id=post.id, tag_id=tag.id))
            
            progress_callback(f"    ✅ Salvo: {classification.get('title', '')[:60]}")
            
            if new_count >= max_new_posts:
                progress_callback(f"  ⏹️  Limite de {max_new_posts} novo(s) post(s) atingido.")
                break
        
        # Generate semantic relations
        if new_count > 0:
            progress_callback("Gerando relações semânticas entre posts...")
            try:
                all_posts_result = await db.execute(select(Post))
                all_posts = all_posts_result.scalars().all()
                posts_for_relations = [
                    {"id": p.id, "content": p.content or "", "title": p.title or ""}
                    for p in all_posts
                ]
                relations = await ollama.generate_relations(posts_for_relations)
                
                from app.models import SemanticRelation
                for rel in relations:
                    sr = SemanticRelation(
                        source_post_id=rel.get("source_id"),
                        target_post_id=rel.get("target_id"),
                        similarity_score=rel.get("similarity_score", 0.0),
                        relation_type=rel.get("relation_type", "semantic"),
                    )
                    db.add(sr)
                
                progress_callback(f"✅ Geradas {len(relations)} relações semânticas")
            except Exception as e:
                progress_callback(f"⚠️  Erro ao gerar relações: {e}")
        
        await db.commit()
    
    summary = f"""
═══════════════════════════════════════
  ✅ SINCRONIZAÇÃO CONCLUÍDA
  📊 Total de posts encontrados: {len(posts_data)}
  🆕 Novos posts processados: {new_count}
  ⏭️  Posts já existentes: {existing_count}
═══════════════════════════════════════
"""
    progress_callback(summary)
