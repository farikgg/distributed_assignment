#!/usr/bin/env bash
# Прогоняет три проверки из задания и пишет логи в evidence/.
# Запуск: bash demo.sh
set -u
cd "$(dirname "$0")"

PYTHON="${PYTHON:-$(command -v python3 || command -v python)}"
RATES=http://127.0.0.1:5001
EXCH=http://127.0.0.1:5002

wait_for() {  # ждём, пока порт начнёт отвечать (любой HTTP-статус годится)
  for _ in $(seq 1 50); do
    curl -s -o /dev/null "$1" && return 0
    sleep 0.2
  done
  echo "Timed out waiting for $1" >&2
  exit 1
}

req() {  # req LOG METHOD URL [JSON]
  local log=$1 method=$2 url=$3 body=${4:-}
  if [ -n "$body" ]; then
    echo "\$ curl -i -X $method $url -H 'Content-Type: application/json' -d '$body'" | tee -a "$log"
    curl -sS -i -X "$method" "$url" -H 'Content-Type: application/json' -d "$body" | tee -a "$log"
  else
    echo "\$ curl -i -X $method $url" | tee -a "$log"
    curl -sS -i -X "$method" "$url" | tee -a "$log"
  fi
  printf '\n\n' | tee -a "$log"
}

rm -f evidence/*.log
mkdir -p evidence

"$PYTHON" -m uvicorn rates.main:app --port 5001 > evidence/rates_service.log 2>&1 &
RATES_PID=$!
"$PYTHON" -m uvicorn exchanges.main:app --port 5002 > evidence/exchanges_service.log 2>&1 &
EXCH_PID=$!
trap 'kill $RATES_PID $EXCH_PID 2>/dev/null' EXIT

wait_for "$RATES/rates/0"
wait_for "$EXCH/exchanges/0"

echo "=== Проверка 1: Оба сервиса запущено ===" | tee evidence/01_both_running.log
req evidence/01_both_running.log POST "$RATES/rates" '{"pair": "USD/KZT", "rate": "495.50"}'
req evidence/01_both_running.log POST "$EXCH/exchanges" '{"rate_id": 1, "amount": "100.00"}'

echo ">>> Stopping service A (rates)"
kill "$RATES_PID"
wait "$RATES_PID" 2>/dev/null

echo "=== Проверка 2: A остановлен, создаем обмен (exchange) -> 503 ===" | tee evidence/02_a_stopped_create.log
req evidence/02_a_stopped_create.log POST "$EXCH/exchanges" '{"rate_id": 1, "amount": "50.00"}'

echo "=== Проверка 3: Операция A остановлена, считываем сохраненную переписку -> 200 ===" | tee evidence/03_a_stopped_get.log
req evidence/03_a_stopped_get.log GET "$EXCH/exchanges/1"