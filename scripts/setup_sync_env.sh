#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$PROJECT_ROOT/.sync-venv"

echo "========================================"
echo "  Setup sync environment"
echo "========================================"
echo ""
echo "  Venv:  $VENV_DIR"
echo "  Python: $(python3 --version)"
echo ""

# ── Cria venv ────────────────────────────────────────────────────────────────

if [ -d "$VENV_DIR" ]; then
    echo "⟳  Venv já existe em $VENV_DIR"
else
    echo "⟳  Criando virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo "   ✓ Venv criado"
fi

# ── Ativa venv e instala dependências ────────────────────────────────────────

source "$VENV_DIR/bin/activate"

echo "⟳  Instalando dependências (requirements.host.txt)..."
pip install --quiet --upgrade pip
pip install --quiet -r "$PROJECT_ROOT/backend/requirements.host.txt"

echo "⟳  Instalando playwright chromium..."
playwright install chromium 2>&1 | tail -5

echo ""
echo "========================================"
echo "  ✅ Ambiente pronto!"
echo "========================================"
echo ""
echo "  Para rodar o sync:"
echo "    source .sync-venv/bin/activate"
echo "    python scripts/sync_host.py"
echo ""
echo "  Ou direto:"
echo "    .sync-venv/bin/python scripts/sync_host.py"
echo ""
