#!/bin/bash
# Scheduler: executa sync.py 3x ao dia nos horários configurados
# Usa TZ do container (America/Recife) para calcular próximo horário.

set -e

SCHEDULE_TIMES="${SYNC_SCHEDULE:-08:00,14:00,20:00}"
SYNC_ARGS="${SYNC_ARGS:---headless}"
LOG_FILE="${LOG_FILE:-/dev/stdout}"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S %Z') [scheduler] $*" | tee -a "$LOG_FILE"
}

log "🕐 Scheduler iniciado — horários: $SCHEDULE_TIMES (TZ=${TZ:-America/Recife})"

while true; do
    NOW=$(date +%s)
    TODAY=$(date +%Y-%m-%d)

    # Encontra o próximo horário futuro (hoje ou amanhã)
    NEXT_TS=""
    IFS=',' read -ra TIMES <<<"$SCHEDULE_TIMES"
    for t in "${TIMES[@]}"; do
        t=$(echo "$t" | xargs)  # trim
        CANDIDATE_TS=$(date -d "$TODAY $t" +%s 2>/dev/null || true)
        if [ -n "$CANDIDATE_TS" ] && [ "$CANDIDATE_TS" -gt "$NOW" ]; then
            if [ -z "$NEXT_TS" ] || [ "$CANDIDATE_TS" -lt "$NEXT_TS" ]; then
                NEXT_TS=$CANDIDATE_TS
            fi
        fi
    done

    # Se nenhum horário hoje ainda não passou, pega o primeiro de amanhã
    if [ -z "$NEXT_TS" ]; then
        TOMORROW=$(date -d "tomorrow" +%Y-%m-%d)
        FIRST=$(echo "$SCHEDULE_TIMES" | cut -d',' -f1 | xargs)
        NEXT_TS=$(date -d "$TOMORROW $FIRST" +%s)
    fi

    SLEEP_SEC=$((NEXT_TS - NOW))
    NEXT_TIME=$(date -d "@$NEXT_TS" '+%Y-%m-%d %H:%M:%S %Z')
    log "⏳ Próxima execução: $NEXT_TIME (dormindo ${SLEEP_SEC}s)"

    sleep "$SLEEP_SEC"

    log "🚀 Executando sync.py $SYNC_ARGS ..."
    if python sync.py $SYNC_ARGS 2>&1 | while IFS= read -r line; do
        echo "$line" | tee -a "$LOG_FILE"
    done; then
        log "✅ sync.py concluído com sucesso"
    else
        log "⚠️  sync.py terminou com erro (exit code: $?)"
    fi

    # Pequena pausa pra evitar loop apertado se sync falhar instantaneamente
    sleep 10
done
