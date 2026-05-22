import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session, init_db
from app.models import Discipline, School, Tag


async def get_or_create_tag(session: AsyncSession, name: str) -> Tag:
    normalized = name.strip().lower()
    result = await session.execute(
        select(Tag).where(Tag.normalized_name == normalized)
    )
    tag = result.scalar_one_or_none()
    if tag is None:
        tag = Tag(name=name.strip(), normalized_name=normalized)
        session.add(tag)
    return tag


async def seed():
    await init_db()

    async with async_session() as session:
        existing = await session.execute(select(School).limit(1))
        if existing.scalar_one_or_none() is not None:
            print("Database already seeded. Skipping.")
            return

        schools_data = [
            {
                "name": "Offensive Security",
                "slug": "offensive",
                "color": "#ff008c",
                "icon": "crosshair",
                "description": "Tudo sobre ataques, invasões e exploração de vulnerabilidades — o lado ofensivo da segurança digital.",
                "disciplines": [
                    {
                        "name": "OSINT",
                        "slug": "osint",
                        "description": "Open Source Intelligence — coleta e análise de dados públicos para investigação e reconhecimento.",
                        "icon": "search",
                        "color": "#ff008c",
                        "tags": ["osint", "inteligência", "reconhecimento", "dados públicos"],
                    },
                    {
                        "name": "Google Dorking",
                        "slug": "google-dorking",
                        "description": "Técnicas avançadas de busca no Google para encontrar informações expostas e falhas de segurança.",
                        "icon": "globe",
                        "color": "#ff008c",
                        "tags": ["google", "dork", "buscas", "reconhecimento"],
                    },
                    {
                        "name": "Recon",
                        "slug": "recon",
                        "description": "Reconhecimento ativo e passivo de alvos — mapeamento de superfície de ataque.",
                        "icon": "radar",
                        "color": "#ff008c",
                        "tags": ["recon", "footprinting", "enumeração", "mapeamento"],
                    },
                    {
                        "name": "Web Security",
                        "slug": "web-security",
                        "description": "Segurança de aplicações web — SQLi, XSS, SSRF, e outras vulnerabilidades comuns.",
                        "icon": "code",
                        "color": "#ff008c",
                        "tags": ["web", "aplicação", "sql injection", "xss"],
                    },
                    {
                        "name": "Engenharia Social",
                        "slug": "engenharia-social",
                        "description": "Ataques psicológicos — phishing, pretexting, baiting e manipulação humana.",
                        "icon": "users",
                        "color": "#ff008c",
                        "tags": ["engenharia social", "phishing", "manipulação"],
                    },
                ],
            },
            {
                "name": "Defensive Security",
                "slug": "defensive",
                "color": "#8b5cf6",
                "icon": "shield",
                "description": "Estratégias de defesa, monitoramento e proteção contínua de infraestruturas digitais.",
                "disciplines": [
                    {
                        "name": "Security Automation",
                        "slug": "security-automation",
                        "description": "Automação de tarefas de segurança — scripts, playbooks e integrações para resposta ágil.",
                        "icon": "zap",
                        "color": "#8b5cf6",
                        "tags": ["automação", "scripts", "playbooks", "soc"],
                    },
                    {
                        "name": "SIEM & SOAR",
                        "slug": "siem-soar",
                        "description": "Correlação de eventos, alertas e orquestração de resposta a incidentes.",
                        "icon": "activity",
                        "color": "#8b5cf6",
                        "tags": ["siem", "soar", "splunk", "elastic", "incidentes"],
                    },
                    {
                        "name": "Hardening & Infraestrutura",
                        "slug": "hardening-infraestrutura",
                        "description": "Endurecimento de servidores, redes e endpoints — boas práticas de configuração segura.",
                        "icon": "lock",
                        "color": "#8b5cf6",
                        "tags": ["hardening", "infraestrutura", "server", "rede"],
                    },
                    {
                        "name": "Threat Hunting",
                        "slug": "threat-hunting",
                        "description": "Busca ativa por ameaças ocultas na rede antes que causem danos.",
                        "icon": "compass",
                        "color": "#8b5cf6",
                        "tags": ["threat hunting", "ameaças", "forense"],
                    },
                ],
            },
            {
                "name": "AI & Emerging Threats",
                "slug": "ai-threats",
                "color": "#f97316",
                "icon": "brain",
                "description": "Inteligência Artificial aplicada à segurança e as novas ameaças emergentes do mundo digital.",
                "disciplines": [
                    {
                        "name": "Deepfake",
                        "slug": "deepfake",
                        "description": "Detecção e análise de deepfakes — áudio, vídeo e imagem gerados por IA.",
                        "icon": "eye",
                        "color": "#f97316",
                        "tags": ["deepfake", "ia", "detecção", "mídia sintética"],
                    },
                    {
                        "name": "AI Security",
                        "slug": "ai-security",
                        "description": "Segurança em sistemas de IA — ataques adversariais, envenenamento de dados e privacidade de modelos.",
                        "icon": "cpu",
                        "color": "#f97316",
                        "tags": ["ai security", "ia", "adversarial", "segurança"],
                    },
                ],
            },
            {
                "name": "Cyber Reality",
                "slug": "cyber-reality",
                "color": "#ff66c4",
                "icon": "globe",
                "description": "O lado real e humano da segurança cibernética — cultura, caos, infraestrutura e conscientização.",
                "disciplines": [
                    {
                        "name": "Cultura Hacker",
                        "slug": "cultura-hacker",
                        "description": "A filosofia, ética e história da cultura hacker e seu impacto na segurança.",
                        "icon": "book",
                        "color": "#ff66c4",
                        "tags": ["cultura", "hacker", "ética", "história"],
                    },
                    {
                        "name": "Caos Corporativo",
                        "slug": "caos-corporativo",
                        "description": "Os desafios reais do dia a dia em segurança corporativa — política, burocracia e falhas reais.",
                        "icon": "building",
                        "color": "#ff66c4",
                        "tags": ["corporativo", "caos", "política", "burocracia"],
                    },
                    {
                        "name": "Infraestrutura Real",
                        "slug": "infraestrutura-real",
                        "description": "Casos reais de falhas, breaches e lições aprendidas em infraestrutura de TI.",
                        "icon": "server",
                        "color": "#ff66c4",
                        "tags": ["infraestrutura", "casos reais", "breaches"],
                    },
                    {
                        "name": "Awareness",
                        "slug": "awareness",
                        "description": "Conscientização e treinamento de usuários — a camada humana da segurança.",
                        "icon": "bell",
                        "color": "#ff66c4",
                        "tags": ["awareness", "conscientização", "treinamento"],
                    },
                ],
            },
        ]

        for school_data in schools_data:
            school = School(
                name=school_data["name"],
                slug=school_data["slug"],
                color=school_data["color"],
                icon=school_data["icon"],
                description=school_data.get("description"),
            )
            session.add(school)
            await session.flush()

            for disc_data in school_data["disciplines"]:
                discipline = Discipline(
                    name=disc_data["name"],
                    slug=disc_data["slug"],
                    description=disc_data.get("description"),
                    icon=disc_data.get("icon"),
                    color=disc_data.get("color"),
                    school_id=school.id,
                )
                session.add(discipline)
                await session.flush()

                for tag_name in disc_data.get("tags", []):
                    tag = await get_or_create_tag(session, tag_name)
                    if tag.id is None:
                        await session.flush()

        await session.commit()
        print("Database seeded successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
