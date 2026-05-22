#!/bin/bash
# Diagnóstico rápido — host de sync
# Uso: bash scripts/diag-host.sh
set -e

echo "=== HOST DIAG ==="
echo ""

echo "📦 Git status"
git -C "$(dirname "$0")/.." log --oneline -3 2>/dev/null || echo "  (não disponível)"
echo ""

echo "🧪 Smoke local"
bash "$(dirname "$0")/smoke.sh" localhost:8000 2>/dev/null || echo "  (api offline?)"
echo ""

echo "🌐 Push config"
grep -E 'SYNC_PUSH_URL|SYNC_PUSH_TOKEN' "$(dirname "$0")/../.env" 2>/dev/null | sed 's/=.*/=***/' || echo "  (.env não encontrado)"
echo ""

echo "🗄️  Banco local"
cd "$(dirname "$0")/.." && PYTHONPATH=backend .sync-venv/bin/python -c "
import asyncio, os
os.environ['DATABASE_URL'] = 'postgresql+asyncpg://ubb:ubb@localhost:5432/ubb'
from app.database import async_session
from sqlalchemy import text
async def main():
    async with async_session() as db:
        for t in ['raw_posts', 'posts', 'disciplines', 'schools']:
            r = await db.execute(text(f'SELECT count(*) FROM {t}'))
            print(f'  {t}: {r.fetchone()[0]}')
asyncio.run(main())
" 2>/dev/null || echo "  (banco offline)"
echo ""

echo "📡 Push POST test"
PUSH_URL=$(grep SYNC_PUSH_URL "$(dirname "$0")/../.env" 2>/dev/null | cut -d= -f2)
PUSH_TOKEN=$(grep SYNC_PUSH_TOKEN "$(dirname "$0")/../.env" 2>/dev/null | cut -d= -f2)
if [ -n "$PUSH_URL" ]; then
    echo "  POST $PUSH_URL/api/sync/raw-posts"
    HTTP=$(curl -sk -o /dev/null -w "%{http_code}" -X POST "$PUSH_URL/api/sync/raw-posts" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $PUSH_TOKEN" \
        -d '{"posts":[]}' 2>/dev/null || echo "fail")
    echo "  → HTTP $HTTP"
    echo "  GET $PUSH_URL/api/sync-info"
    HTTP2=$(curl -sk -o /dev/null -w "%{http_code}" "$PUSH_URL/api/sync-info" 2>/dev/null || echo "fail")
    echo "  → HTTP $HTTP2"
else
    echo "  SYNC_PUSH_URL não configurado"
fi
echo ""
echo "=== FIM ==="
