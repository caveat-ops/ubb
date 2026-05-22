#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────
# migrate_to_vm.sh — Exporta dados do banco dev e envia para VM
# Uso: ./scripts/migrate_to_vm.sh <user@host>
# Ex:  ./scripts/migrate_to_vm.sh root@93.188.164.128
# ─────────────────────────────────────────────────────────────

if [ $# -lt 1 ]; then
  echo "Uso: $0 <user@host>"
  echo "Ex:  $0 root@93.188.164.128"
  exit 1
fi

REMOTE="$1"
DUMP_FILE="ubb_dump_$(date +%Y%m%d_%H%M%S).sql"
REMOTE_PATH="/tmp/$DUMP_FILE"

echo "🔧 Gerando dump do banco dev..."
docker compose exec -T db pg_dump -U ubb ubb > "$DUMP_FILE"
echo "✅ Dump gerado: $DUMP_FILE ($(du -h "$DUMP_FILE" | cut -f1))"

echo "📤 Enviando para $REMOTE..."
scp "$DUMP_FILE" "$REMOTE:$REMOTE_PATH"
echo "✅ Enviado para $REMOTE:$REMOTE_PATH"

echo "📥 Restaurando na VM..."
ssh "$REMOTE" "cd /tmp && \
  docker compose -f /path/to/docker-compose.yml exec -T db pg_restore -U ubb -d ubb --clean < \"$REMOTE_PATH\" && \
  rm -f \"$REMOTE_PATH\" && \
  echo '✅ Restauração concluída'"

echo "🧹 Limpando dump local..."
rm -f "$DUMP_FILE"

echo ""
echo "═══════════════════════════════════════"
echo "  ✅ MIGRAÇÃO CONCLUÍDA"
echo "  📄 Dump: $DUMP_FILE"
echo "  🖥️  VM:  $REMOTE"
echo "═══════════════════════════════════════"
