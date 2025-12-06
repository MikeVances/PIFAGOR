#!/usr/bin/env bash

# ===============================
#  PIFAGOR starter
#  Запускает ключевые сервисы пайплайна:
#  1) API для GPTs (Flask, порт 7001)
#  2) Worker, следящий за storage/results_json
# ===============================

set -e  # если любая команда упадёт — завершаем скрипт

# --- Переходим в корень проекта ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[PIFAGOR] Работаем из каталога: $SCRIPT_DIR"

# --- Обеспечиваем каталог для логов ---
mkdir -p logs

# --- Настраиваем интерпретатор ---
PY_BIN_DEFAULT="python3"
PY_BIN_SYSTEM="/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"

if command -v "$PY_BIN_SYSTEM" >/dev/null 2>&1; then
    PY_BIN="$PY_BIN_SYSTEM"
    echo "[PIFAGOR] Используем системный Python 3.11: $PY_BIN"
elif command -v pyenv >/dev/null 2>&1; then
    export PYENV_VERSION=3.10.0
    PY_BIN="$PY_BIN_DEFAULT"
    echo "[PIFAGOR] Используем pyenv Python: $PY_BIN ($PYENV_VERSION)"
elif command -v "$PY_BIN_DEFAULT" >/dev/null 2>&1; then
    PY_BIN="$PY_BIN_DEFAULT"
    echo "[PIFAGOR] Используем доступный $PY_BIN_DEFAULT"
else
    echo "[PIFAGOR] ❌ python3 не найден"
    exit 1
fi

export PYTHONPATH="$SCRIPT_DIR"

# --- Глушим старые процессы, если остались ---
# Осторожно: ищем именно наши скрипты
pkill -f "services/api/gpts_actions_server.py" 2>/dev/null || true
pkill -f "services/worker/worker.py" 2>/dev/null || true

# Небольшая пауза, чтобы порты освободились
sleep 1

# --- Запуск Flask API (порт 7001) ---

echo "[PIFAGOR] Запускаю Flask API на порту 7001..."
"$PY_BIN" -m services.api.gpts_actions_server \
  > logs/api_pifagor.log 2>&1 &
API_PID=$!
echo "[PIFAGOR] Flask API PID: $API_PID (логи: logs/api_pifagor.log)"

# --- Запуск воркера результатов ---

echo "[PIFAGOR] Запускаю воркер обработки results_json..."
"$PY_BIN" -m services.worker.worker \
  > logs/worker_pifagor.log 2>&1 &
WORKER_PID=$!
echo "[PIFAGOR] Worker PID: $WORKER_PID (логи: logs/worker_pifagor.log)"

# --- Итог ---

echo "[PIFAGOR] Всё поднято. Проверяй:"
echo "  API:   http://127.0.0.1:7001/pifagor/submit_card_result (POST)"
echo "  Worker следит за storage/results_json"
echo "[PIFAGOR] Чтобы остановить — используй pkill или перезагрузи терминал."
