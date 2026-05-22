# Universidade Bebê (UBB)

Curadoria de cybersegurança — conteúdo do LinkedIn da Mariana estruturado como um sistema neural.

## Stack

- **Frontend**: Next.js 13 + Tailwind
- **Backend**: FastAPI + SQLAlchemy (async) + PostgreSQL + pgvector
- **Sync**: Playwright (LinkedIn) + Ollama (classificação)
- **Infra**: Docker Compose + nginx-proxy + LetsEncrypt

## Estrutura

```
ubb/
├── frontend/          # Next.js app
├── backend/           # FastAPI
│   ├── app/
│   │   ├── routers/   # API endpoints
│   │   ├── services/  # LinkedIn agent, Ollama, embeddings
│   │   ├── models.py  # SQLAlchemy models
│   │   └── main.py    # FastAPI app
│   ├── sync.py        # Script de sync (roda no host)
│   └── requirements.*.txt
├── docker-compose.yml           # Produção
├── docker-compose.override.yml  # Dev (portas expostas, hot reload)
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
#
# 3. Subir:
docker compose up -d
```

## Sync push para VM

O sync no host empurra novos raw_posts para a VM via HTTPS com token:

```bash
# No .env do host:
SYNC_PUSH_URL=https://ubb.eugeniomarques.com
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
| POST | /api/sync/raw-posts | Recebe posts do host (token) |

## Variáveis de ambiente principais

| Var | Descrição |
|-----|-----------|
| SYNC_MODE | capture, monitor, process |
| URL_TARGET | URL do perfil LinkedIn |
| URL_ABOUT | URL da página "Sobre" do alvo |
| SYNC_PUSH_URL | URL da VM para push |
| SYNC_PUSH_TOKEN | Token de autenticação |
| USE_EXTERNAL_NET | Usar rede Docker externa |
| EXTERNAL_NET | Nome da rede externa |
