import json
import logging
from pathlib import Path
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

PERSONA_PATH = Path(__file__).resolve().parent.parent.parent / "persona.md"


class OllamaService:
    def __init__(self, host: Optional[str] = None, model: Optional[str] = None):
        self.host = (host or settings.ollama_host).rstrip("/")
        self.model = model or settings.ollama_model
        self._persona: Optional[str] = None

    def _load_persona(self) -> str:
        if self._persona is None:
            try:
                self._persona = PERSONA_PATH.read_text(encoding="utf-8")
            except FileNotFoundError:
                logger.warning("persona.md not found at %s", PERSONA_PATH)
                self._persona = "You are Mariana, a cybersecurity expert."
        return self._persona

    async def classify_post(
        self, content: str, hashtags: list[str]
    ) -> dict:
        persona = self._load_persona()

        system_msg = (
            f"{persona}\n\n"
            "You are helping classify a LinkedIn post for the "
            "'Universidade Bebê' platform. "
            "Analyze the post content and return a JSON object with "
            "the following fields:\n"
            "- title: a catchy title for the post\n"
            "- subtitle: a short subtitle\n"
            "- summary: a 1-2 sentence summary\n"
            "- quote: an impactful quote from the post\n"
            "- mariana_take: Mariana's commentary on the post "
            "(write as if you are Mariana)\n"
            "- content_type: one of: lesson, lab, awareness, challenge, "
            "storytelling, threat_analysis, architecture, hands_on, "
            "fundamentals\n"
            "- skill_type: one of: técnico, operacional, mindset, "
            "awareness, arquitetura, carreira\n"
            "- difficulty: one of: iniciante, intermediário, avançado, "
            "todos os níveis\n"
            "- discipline: the cybersecurity discipline "
            "(e.g., OSINT, Red Team, Blue Team)\n"
            "- school: the school name "
            "(e.g., Offensive Security, Defensive Security)\n"
            "- tags: list of relevant tags (keywords)\n\n"
            "Respond with ONLY valid JSON, no markdown formatting."
        )

        user_msg = (
            f"Classify this LinkedIn post:\n\n"
            f"Content: {content}\n\n"
            f"Hashtags: {', '.join(hashtags)}\n\n"
            "Return the JSON object with the classification."
        )

        async with httpx.AsyncClient(
            base_url=self.host, timeout=120.0
        ) as client:
            response = await client.post(
                "/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_msg},
                    ],
                    "format": "json",
                    "stream": False,
                },
            )
            response.raise_for_status()
            result = response.json()

        raw = result.get("message", {}).get("content", "{}")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.error(
                "Failed to parse Ollama response as JSON: %s", raw
            )
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

    async def classify_discipline(self, content: str) -> dict:
        """Retorna {'discipline': str, 'confidence': int, 'school': str}"""
        persona = self._load_persona()

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
            "Respond with ONLY valid JSON."
        )

        user_msg = (
            f"Classify this LinkedIn post into a cybersecurity discipline:\n\n"
            f"{content[:2000]}\n\n"
            "Return the JSON object."
        )

        async with httpx.AsyncClient(base_url=self.host, timeout=120.0) as client:
            response = await client.post(
                "/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_msg},
                    ],
                    "format": "json",
                    "stream": False,
                },
            )
            response.raise_for_status()
            result = response.json()

        raw = result.get("message", {}).get("content", "{}")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("Failed to parse classify_discipline JSON: %s", raw)
            return {"discipline": "Gerais", "confidence": 0, "school": ""}

        return {
            "discipline": parsed.get("discipline", "Gerais"),
            "confidence": int(parsed.get("confidence", 0)),
            "school": parsed.get("school", ""),
        }

    async def generate_embedding(self, text: str) -> list[float]:
        async with httpx.AsyncClient(
            base_url=self.host, timeout=60.0
        ) as client:
            response = await client.post(
                "/api/embed",
                json={
                    "model": self.model,
                    "input": text,
                },
            )
            response.raise_for_status()
            result = response.json()

        embeddings = result.get("embeddings", [])
        return embeddings[0] if embeddings else []

    async def generate_relations(
        self, all_posts: list[dict]
    ) -> list[dict]:
        if len(all_posts) < 2:
            return []

        persona = self._load_persona()

        posts_summary = []
        for post in all_posts:
            posts_summary.append(
                {
                    "id": post.get("id"),
                    "title": post.get("title", ""),
                    "summary": post.get("summary", ""),
                    "discipline": post.get("discipline", ""),
                    "tags": post.get("tags", []),
                }
            )

        system_msg = (
            f"{persona}\n\n"
            "You are identifying semantic relations between "
            "cybersecurity posts. "
            "Given a list of posts, identify meaningful connections "
            "between them. "
            "Return a JSON array of relations, where each relation has:\n"
            "- source_id: the ID of the source post\n"
            "- target_id: the ID of the target post\n"
            "- similarity_score: a float from 0.0 to 1.0\n"
            "- relation_type: one of: continues, complements, "
            "contrasts, prerequisite, example_of, generalizes\n\n"
            "Only return relations where posts are meaningfully "
            "connected (score > 0.5). "
            "Respond with ONLY valid JSON array."
        )

        user_msg = (
            "Analyze these posts and find semantic relations:\n\n"
            f"{json.dumps(posts_summary, ensure_ascii=False, indent=2)}"
            "\n\nReturn the JSON array of relations."
        )

        async with httpx.AsyncClient(
            base_url=self.host, timeout=120.0
        ) as client:
            try:
                response = await client.post(
                    "/api/chat",
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_msg},
                            {"role": "user", "content": user_msg},
                        ],
                        "format": "json",
                        "stream": False,
                    },
                )
                response.raise_for_status()
                result = response.json()

                raw = result.get("message", {}).get("content", "[]")
                relations = json.loads(raw)
                if not isinstance(relations, list):
                    relations = []
            except Exception as e:
                logger.error("Failed to generate relations: %s", e)
                relations = []

        return relations
