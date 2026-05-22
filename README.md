# UBB — Universal Brain Builder

> **Menção honrosa:** este projeto existe por causa da [Mariana B S](https://www.linkedin.com/in/marianabsz). Foi o conteúdo dela — prolífico e, acima de tudo, profícuo — que me fez criar isso. Mas o indexador é agnóstico: funciona com qualquer perfil do LinkedIn.

## Por que isso existe

Certo dia eu quase surtei.

Tava procurando um post antigo da Mariana e não achava. Fui scrollando, scrollando, scrollando… e percebi duas coisas: (1) tinha muito conteúdo bom que eu ainda não tinha lido, e (2) eu nunca ia dar conta de tudo aquilo.

Minha pressão — normalmente 11 por 7 — foi pra 12 por 8. Deu vontade de beber. Peguei uma Corona Cero (recomendo, é perfeita), relaxei, e decidi: vou indexar isso.

Uma pessoa prolífica já é rara. Prolífica **e** profícua, mais ainda. O conteúdo da Mariana merecia ser estruturado como um sistema neural. E se funcionasse pra ela, funcionaria pra qualquer um.

## O LAB

Além da história da cerveja, tem o motivo de sempre: eu uso qualquer ideia como desculpa pra testar IA.

Minha meta — como já falei pro meu amigo [Cesar Brod](https://www.linkedin.com/in/cesarbrod) — é escravizar a IA. Toda ideia que couber no vibe coding, eu faço. Quero ver se consigo entregar algo de qualidade.

A qualidade vocês avaliam. Pra mim, o experimento é o que conta.

## Números

| O que | Quanto |
|---|---|
| MVP inicial | < 5 minutos |
| Backend + frontend conectados | ~15 minutos |
| Ajustes finos | várias horas (dias) |
| Total | ~2 dias de trabalho (eu codando enquanto fazia outras coisas — tenho contas pra pagar) |

## Stack técnica

- **Modelo**: [DeepSeek V4 Pro](https://ollama.com/library/deepseek-v4-pro) — era esse que eu queria testar
- **TUI**: [DeepSeek TUI](https://github.com/Hmbown/DeepSeek-TUI) — descobri [neste post do Akita](https://akitaonrails.com/2026/05/04/llm-benchmarks-deepseek-unlocked-deepclaude/)
- **Frontend inicial**: [Bolt](https://universidade-beb-cyb-krm7.bolt.host) (depois refeito via vibe coding)
- **Backend**: FastAPI + SQLAlchemy + PostgreSQL + pgvector
- **Browser**: Playwright (extração do LinkedIn)
- **LLM local**: Ollama (classificação de conteúdo)
- **Infra**: Docker Compose + nginx-proxy + LetsEncrypt

## Estrutura

```
ubb/
├── frontend/          # Next.js 13 + Tailwind
├── backend/           # FastAPI
│   ├── app/
│   │   ├── routers/   # API endpoints
│   │   ├── services/  # LinkedIn agent, Ollama, embeddings
│   │   ├── models.py  # SQLAlchemy models
│   │   └── main.py    # FastAPI app
│   ├── sync.py        # Script de sync (roda no host)
│   └── requirements.*.txt
├── docker-compose.yml           # Produção
├── docker-compose.override.yml  # Dev
└── .env
```

## Rodando local (dev)

```bash
# Subir containers
docker compose up -d

# Criar venv e instalar deps do sync
python3 -m venv .sync-venv
.sync-venv/bin/pip install -r backend/requirements.sync.txt
.sync-venv/bin/playwright install chromium

# Rodar sync (modo capture = pegar tudo)
cd backend && PYTHONPATH=. ../.sync-venv/bin/python sync.py --headless

# Modo monitor (só novos posts, diário)
SYNC_MODE=monitor PYTHONPATH=. ../.sync-venv/bin/python sync.py --headless

# Só classificar (process-only, sem navegador)
SYNC_MODE=process PROCESS_COUNT=50 PYTHONPATH=. ../.sync-venv/bin/python sync.py --headless
```

## Deploy (VM com nginx-proxy)

```bash
# Na VM, junto com o nginx-proxy:
# 1. Copiar docker-compose.yml e .env
# 2. Ajustar .env:
#    USE_EXTERNAL_NET=true
#    EXTERNAL_NET=innovation
#    SYNC_PUSH_TOKEN=<token-seguro>
#    NEXT_PUBLIC_API_URL=https://seu-dominio.com
#
# 3. Subir:
docker compose up -d
```

## Sync push para VM

O sync no host empurra novos raw_posts para a VM via HTTPS com token:

```bash
# No .env do host:
SYNC_PUSH_URL=https://seu-dominio.com
SYNC_PUSH_TOKEN=<mesmo-token-da-vm>
```

O endpoint `POST /api/sync/raw-posts` na VM recebe e insere no banco.

## Cron (no host)

```bash
# Todo dia às 9h
0 9 * * * cd /home/caveat/projetos/caveat/ubb && /home/caveat/projetos/caveat/ubb/.sync-venv/bin/python backend/sync.py --headless >> /home/caveat/projetos/caveat/ubb/sync.log 2>&1
```

## API Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | /api/posts | Posts (filtro: ?discipline_id=X) |
| GET | /api/disciplines | Disciplinas com contagem |
| GET | /api/graph | Grafo de conhecimento |
| GET | /api/search?q= | Busca textual |
| GET | /api/raw-posts | Posts brutos |
| GET | /api/stats | Estatísticas |
| GET | /api/about | Info do perfil alvo |
| POST | /api/sync/raw-posts | Recebe posts do host (token) |

## Variáveis de ambiente principais

| Var | Descrição |
|-----|-----------|
| SYNC_MODE | capture, monitor, process |
| FRONTEND_PORT | Porta do frontend (default: 3000) |
| URL_TARGET | URL do perfil LinkedIn |
| URL_ABOUT | URL da página "Sobre" do alvo |
| SYNC_PUSH_URL | URL da VM para push |
| SYNC_PUSH_TOKEN | Token de autenticação |
| USE_EXTERNAL_NET | Usar rede Docker externa |
| EXTERNAL_NET | Nome da rede externa |
