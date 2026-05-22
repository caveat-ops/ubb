#!/bin/bash
# Smoke test — roda após cada deploy na VM
# Uso: bash scripts/smoke.sh [domínio]
set -e

DOMAIN="${1:-localhost}"
BASE="https://$DOMAIN"
OK=0
FAIL=0

check() {
    local method="$1" url="$2" expected="$3"
    local code
    code=$(curl -sk -o /dev/null -w "%{http_code}" -X "$method" "$BASE$url" 2>/dev/null)
    if [ "$code" = "$expected" ]; then
        echo "  ✅ $method $url → $code"
        OK=$((OK + 1))
    else
        echo "  ❌ $method $url → $code (esperado $expected)"
        FAIL=$((FAIL + 1))
    fi
}

echo "🧪 Smoke test — $BASE"
echo ""

echo "📄 Frontend"
check GET "/" 200
echo ""

echo "🔌 API — leitura"
check GET "/api/about" 200
check GET "/api/stats" 200
check GET "/api/disciplines" 200
check GET "/api/graph" 200
check GET "/api/search?q=test" 200
echo ""

echo "📡 API — sync"
check GET "/api/sync-info" 200
check POST "/api/sync/raw-posts" 200
echo ""

echo "🛡️ Security headers"
HEADERS=$(curl -skI "$BASE" 2>/dev/null)
for h in "content-security-policy" "x-frame-options" "strict-transport-security"; do
    if echo "$HEADERS" | grep -qi "$h"; then
        echo "  ✅ $h presente"
        OK=$((OK + 1))
    else
        echo "  ❌ $h ausente"
        FAIL=$((FAIL + 1))
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Resultado: $OK ok, $FAIL falhas"
[ "$FAIL" -eq 0 ] && echo "✅ Deploy saudável" || echo "❌ Problemas detectados"
