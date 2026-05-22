import logging
from typing import Optional

import numpy as np
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Post
from app.services.ollama_service import OllamaService

logger = logging.getLogger(__name__)

_ollama: Optional[OllamaService] = None


def _get_ollama() -> OllamaService:
    global _ollama
    if _ollama is None:
        _ollama = OllamaService()
    return _ollama


async def get_embedding(text: str) -> list[float]:
    ollama = _get_ollama()
    return await ollama.generate_embedding(text)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    a_arr = np.array(a, dtype=np.float32)
    b_arr = np.array(b, dtype=np.float32)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a_arr, b_arr) / (norm_a * norm_b))


async def compute_post_embedding(post_content: str) -> list[float]:
    return await get_embedding(post_content)


async def find_similar_posts(
    post_id: int, db: AsyncSession, limit: int = 5
) -> list[int]:
    result = await db.execute(
        select(Post.embedding).where(Post.id == post_id)
    )
    row = result.scalar_one_or_none()
    if row is None or row.embedding is None:
        return []

    embedding_vec = row.embedding

    stmt = text(
        """
        SELECT id, embedding <=> :embedding AS distance
        FROM posts
        WHERE id != :post_id AND embedding IS NOT NULL
        ORDER BY distance
        LIMIT :limit
        """
    )

    result = await db.execute(
        stmt,
        {
            "embedding": embedding_vec,
            "post_id": post_id,
            "limit": limit,
        },
    )
    return [row[0] for row in result.fetchall()]
