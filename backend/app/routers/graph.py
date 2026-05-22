from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from app.database import get_db
from app.schemas import GraphEdge, GraphNode, GraphOut

router = APIRouter()

# Mapeamento escola → layer (índice: 0=offensive, 1=defensive, 2=ai, 3=reality)
SCHOOL_LAYER = {
    "Offensive Security": 0,
    "Defensive Security": 1,
    "Security Operations": 1,
    "AI & Emerging Threats": 2,
    "Cyber Reality": 3,
    "Fundamentals": 3,
}

# Cores por layer (mesmas do frontend)
LAYER_COLORS = {
    0: "#ff008c",  # offensive
    1: "#06b6d4",  # defensive
    2: "#f97316",  # ai
    3: "#cbd5e1",  # reality
    4: "#f59e0b",  # orbital (Gerais — solitário)
}
GERAIS_COLOR = "#f59e0b"  # dourado/sol
GERAIS_LAYER = 4


@router.get("", response_model=GraphOut)
@router.get("/", response_model=GraphOut)
async def get_graph(db: AsyncSession = Depends(get_db)):
    # Busca disciplinas com contagem de posts
    result = await db.execute(
        text("""
            SELECT d.id, d.name, s.name as school_name, COUNT(p.id) as post_count
            FROM disciplines d
            LEFT JOIN schools s ON s.id = d.school_id
            INNER JOIN posts p ON p.discipline_id = d.id
            GROUP BY d.id, d.name, s.name
            ORDER BY post_count DESC
        """)
    )
    rows = result.fetchall()

    nodes = []
    disc_ids = []
    for row in rows:
        disc_id, disc_name, school_name, post_count = row
        disc_ids.append(disc_id)
        if disc_name == "Gerais":
            layer = GERAIS_LAYER
            color = GERAIS_COLOR
        else:
            layer = SCHOOL_LAYER.get(school_name or "Fundamentals", 3)
            color = LAYER_COLORS.get(layer, "#cbd5e1")
        nodes.append(
            GraphNode(
                id=disc_id,
                label=disc_name,
                posts=post_count,
                color=color,
                layer=layer,
            )
        )

    # Arestas: primeiro tenta SemanticRelation, fallback conecta disciplinas da mesma escola
    edges = []
    if len(disc_ids) >= 2:
        edge_result = await db.execute(
            text("""
                SELECT DISTINCT
                    LEAST(p1.discipline_id, p2.discipline_id) as source,
                    GREATEST(p1.discipline_id, p2.discipline_id) as target
                FROM semantic_relations sr
                JOIN posts p1 ON p1.id = sr.source_post_id
                JOIN posts p2 ON p2.id = sr.target_post_id
                WHERE p1.discipline_id != p2.discipline_id
                  AND p1.discipline_id = ANY(:ids)
                  AND p2.discipline_id = ANY(:ids)
            """),
            {"ids": disc_ids},
        )
        for row in edge_result.fetchall():
            edges.append(GraphEdge(source=row[0], target=row[1]))

    # Fallback: conecta disciplinas da mesma escola (exceto Gerais — isolado)
    if not edges:
        school_groups = {}
        for n in nodes:
            if n.layer == GERAIS_LAYER:
                continue  # Gerais orbita sozinho
            school_groups.setdefault(n.layer, []).append(n.id)
        for group in school_groups.values():
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    edges.append(GraphEdge(source=group[i], target=group[j]))

    return GraphOut(nodes=nodes, edges=edges)


@router.get("/discipline/{discipline_id}", response_model=GraphOut)
async def get_discipline_graph(discipline_id: int, db: AsyncSession = Depends(get_db)):
    # Retorna posts de uma disciplina específica como sub-nós
    result = await db.execute(
        text("""
            SELECT p.id, p.title, p.discipline_id
            FROM posts p
            WHERE p.discipline_id = :did
            ORDER BY p.id
        """),
        {"did": discipline_id},
    )
    rows = result.fetchall()

    disc_result = await db.execute(
        text("SELECT name, school_id FROM disciplines WHERE id = :did"),
        {"did": discipline_id},
    )
    disc_row = disc_result.fetchone()
    disc_name = disc_row[0] if disc_row else "Desconhecida"

    nodes = [
        GraphNode(
            id=row[0],
            label=row[1] or f"Post {row[0]}",
            posts=1,
            color=LAYER_COLORS.get(3, "#cbd5e1"),
            layer=3,
        )
        for row in rows
    ]

    post_ids = [row[0] for row in rows]
    edges = []
    if len(post_ids) >= 2:
        edge_result = await db.execute(
            text("""
                SELECT source_post_id, target_post_id
                FROM semantic_relations
                WHERE source_post_id = ANY(:ids) AND target_post_id = ANY(:ids)
            """),
            {"ids": post_ids},
        )
        for row in edge_result.fetchall():
            edges.append(GraphEdge(source=row[0], target=row[1]))

    return GraphOut(nodes=nodes, edges=edges)
