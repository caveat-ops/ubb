# UBB — Universidade Bebê (nome original)
ou
# UBB - Universal Brain Builder (coisas da IA)

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
| Total | ~2 dias de trabalho (a IA codando enquanto eu fazia outras coisas — tenho contas pra pagar) |
| Debug do nginx-proxy | várias horas (o DeepSeek V4 Pro demorou pra perceber que expor a API num subdomínio próprio resolvia o roteamento) |

## Stack técnica

- **Modelo**: [DeepSeek V4 Pro](https://ollama.com/library/deepseek-v4-pro) — era esse que eu queria testar
- **TUI**: [DeepSeek TUI](https://github.com/Hmbown/DeepSeek-TUI) — descobri [neste post do Akita](https://akitaonrails.com/2026/05/04/llm-benchmarks-deepseek-unlocked-deepclaude/)
- **Frontend inicial**: [Bolt](https://universidade-beb-cyb-krm7.bolt.host) (depois refeito via vibe coding)
- **Backend**: FastAPI + SQLAlchemy + PostgreSQL + pgvector
- **Browser**: Playwright (extração do LinkedIn)
- **LLM local**: Ollama (classificação de conteúdo)
- **Modelo local**: qwen3:8b-32k
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

Antes de mais nada você precisa ter o override, pois eu não mando pro repo pois às vezes preciso colocar dados sensíveis ou expor portas que em prod não precisa expor:
```docker-compose.override.yml
services:
  frontend:
    user: root
    ports:
      - "3001:3000"
    volumes:
      - ./frontend:/app
      - /app/node_modules
      - /app/.next
    environment:
      - NODE_ENV=development
      - NEXT_TELEMETRY_DISABLED=1
      - WATCHPACK_POLLING=true
    command: npm run dev

  api:
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
      - /app/__pycache__
    environment:
      - LOG_LEVEL=debug
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  db:
    ports:
      - "5432:5432"
    volumes:
      - pgdata_dev:/var/lib/postgresql/data

volumes:
  pgdata_dev:
```

```bash
# Subir containers
docker compose up -d

# Criar venv e instalar deps do sync
python3 -m venv .sync-venv
.sync-venv/bin/pip install -r backend/requirements.sync.txt
.sync-venv/bin/playwright install chromium
# Para Firefox stealth (opcional):
.sync-venv/bin/playwright install firefox
```

## Sync — referência completa

O script `backend/sync.py` extrai posts do LinkedIn, classifica com LLM e faz push para a VM. Roda no **host** (não no container), acessando o banco local e o Ollama/Gemini CLI.

### Comando base

```bash
PYTHONPATH=backend .sync-venv/bin/python backend/sync.py [flags]
```

### Flags

| Flag | Padrão | Descrição |
|------|--------|-----------|
| `--headless` | — | Força modo headless (navegador invisível) |
| `--no-headless` | — | Força modo visível (útil pra debug/OAuth) |
| `--firefox` | `false` | Usa Firefox stealth (`invisible_playwright`) em vez de Chromium |
| `--classifier {ollama,gemini}` | `ollama` | LLM para classificação de posts |
| `--max-posts N` | `20` | Máximo de posts a extrair por execução |
| `--update-all` | `false` | Reprocessa posts já existentes no banco |
| `--push-all` | `false` | Envia TODOS os raw_posts e dados classificados pra VM (modo bulk) |
| `--no-push` | `false` | Pula push para VM remota (auto em produção) |

### Modos de operação (`SYNC_MODE`)

| Modo | Descrição | Usa navegador? |
|------|-----------|----------------|
| `monitor` ★ | Extrai só posts novos, para no primeiro duplicado | Sim |
| `capture` | Scrolla o feed inteiro, varredura completa | Sim |
| `process` | Só classifica posts pendentes no banco | **Não** |

★ `monitor` é o padrão. Ideal pra cron diário.

### Exemplos de execução

```bash
# ── Modo monitor (diário) ──────────────────────────────

# Chromium + Ollama (padrão)
PYTHONPATH=backend .sync-venv/bin/python backend/sync.py --no-headless

# Firefox + Ollama (stealth, evita detecção)
PYTHONPATH=backend .sync-venv/bin/python backend/sync.py --no-headless --firefox

# Chromium + Gemini CLI (classificação mais rápida)
PYTHONPATH=backend .sync-venv/bin/python backend/sync.py --no-headless --classifier gemini

# Firefox + Gemini (stealth + classificação rápida)
PYTHONPATH=backend .sync-venv/bin/python backend/sync.py --no-headless --firefox --classifier gemini

# Headless (pra cron)
PYTHONPATH=backend .sync-venv/bin/python backend/sync.py --headless

# ── Modo capture (varredura completa) ───────────────────

SYNC_MODE=capture MAX_SCROLLS=80 PYTHONPATH=backend .sync-venv/bin/python backend/sync.py --no-headless

# ── Modo process-only (sem navegador) ───────────────────

# Classificar 50 posts pendentes com Ollama
SYNC_MODE=process PROCESS_COUNT=50 PYTHONPATH=backend .sync-venv/bin/python backend/sync.py

# Classificar com Gemini
SYNC_MODE=process PROCESS_COUNT=50 PYTHONPATH=backend .sync-venv/bin/python backend/sync.py --classifier gemini

# ── Push-all (bulk para VM) ─────────────────────────────

PYTHONPATH=backend .sync-venv/bin/python backend/sync.py --push-all

# ── Reprocessar existentes ──────────────────────────────

PYTHONPATH=backend .sync-venv/bin/python backend/sync.py --update-all --classifier gemini
```

### Combinações testadas

Todas as 4 combinações browser × classificador funcionam:

| Browser | Classificador | Comando |
|---------|---------------|---------|
| Chromium | Ollama | `--no-headless` |
| Chromium | Gemini | `--no-headless --classifier gemini` |
| Firefox | Ollama | `--no-headless --firefox` |
| Firefox | Gemini | `--no-headless --firefox --classifier gemini` |

### Variáveis de ambiente do sync

| Var | Padrão | Descrição |
|-----|--------|-----------|
| `SYNC_MODE` | `monitor` | Modo: `capture`, `monitor`, `process` |
| `URL_TARGET` | — | URL do perfil/recent-activity no LinkedIn |
| `LINKEDIN_EMAIL` | — | Email da conta LinkedIn |
| `LINKEDIN_PASSWORD` | — | Senha da conta LinkedIn |
| `PLAYWRIGHT_HEADLESS` | `false` | Headless mode (quando não usa flag explícita) |
| `CLASSIFIER` | `ollama` | Classificador padrão: `ollama` ou `gemini` |
| `MAX_SCROLLS` | `40` | Scrolls máximos no modo capture |
| `CONSECUTIVE_DUPES_TO_STOP` | `5` | Dups consecutivas antes de parar |
| `SCROLL_DELAY_MIN` | `3` | Delay mínimo entre scrolls (segundos) |
| `SCROLL_DELAY_MAX` | `8` | Delay máximo entre scrolls (segundos) |
| `PROCESS_COUNT` | `10` | Posts a classificar por execução |
| `OLLAMA_HOST` | `http://localhost:11434` | Endereço do Ollama |
| `OLLAMA_MODEL` | — | Modelo Ollama (ex: `qwen3:8b-32k`) |
| `SYNC_PUSH_URL` | — | URL da VM para push |
| `SYNC_PUSH_TOKEN` | — | Token de autenticação do push |

## Deploy (VM com nginx-proxy)

```bash
# Na VM, junto com o nginx-proxy:
# 1. Copiar docker-compose.yml e .env
# 2. Ajustar .env:
#    USE_EXTERNAL_NET=true
#    EXTERNAL_NET=external-name
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
0 9 * * * cd /ubb && .sync-venv/bin/python backend/sync.py --headless >> sync.log 2>&1
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
