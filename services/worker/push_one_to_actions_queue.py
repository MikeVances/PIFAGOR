#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
push_one_to_actions_queue.py

Задача скрипта:
- Найти ОДНО изображение в папке storage/incoming_photos
- Если папка storage/actions_in_progress ПУСТА:
    - Переместить туда файл
    - Вернуть информацию о том, какой файл был поставлен "в работу"
- Если в storage/actions_in_progress уже есть файл:
    - НИЧЕГО не трогать, вернуть, что задача уже в работе

Скрипт может:
- использоваться как модуль (функция push_next_card())
- подниматься как Flask-сервис с эндпоинтом POST /pifagor/push_next_card
"""

import logging
import os
from typing import Dict, Any

from flask import Flask, jsonify, request, send_file

from services.worker import card_queue
from services.worker.card_queue import get_in_progress_file

# === ЛОГИРОВАНИЕ ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# === ЯДРО ЛОГИКИ: ПОСТАВИТЬ ОДНУ КАРТОЧКУ В РАБОТУ ===
def push_next_card() -> Dict[str, Any]:
    result = card_queue.push_next_card()
    logger.info("push_next_card result: %s", result)
    return result


# === HTTP-СЛОЙ (Flask) ДЛЯ ВЫЗОВА ЧЕРЕЗ POST /pifagor/push_next_card ===

app = Flask(__name__)


@app.post("/pifagor/push_next_card")
def push_next_card_endpoint():
    """
    HTTP-эндпоинт для постановки следующей карточки в работу.

    Пример ответа (JSON):

    {
        "ok": true,
        "pushed": true,
        "filename": "card_0007_АО_АГРОФИРМА_ВОСТОК.jpg",
        "reason": null
    }

    или, если уже есть задача в работе:

    {
        "ok": true,
        "pushed": false,
        "filename": null,
        "reason": "already_in_progress"
    }

    или, если нет файлов во входящей папке:

    {
        "ok": true,
        "pushed": false,
        "filename": null,
        "reason": "no_files_in_incoming"
    }
    """
    try:
        result = push_next_card()
        status_code = 200 if result.get("ok") else 500
        return jsonify(result), status_code
    except Exception as e:
        logger.exception("Ошибка при постановке карточки в очередь")
        return jsonify({
            "ok": False,
            "pushed": False,
            "filename": None,
            "reason": f"exception: {e}",
        }), 500


@app.get("/pifagor/files/<filename>")
def serve_file(filename: str):
    path = card_queue.get_file_path(filename)
    if not path:
        return jsonify({"ok": False, "reason": "file_not_found"}), 404
    return send_file(path)


@app.post("/pifagor/mark_processed")
def mark_processed_endpoint():
    payload = request.get_json(force=True) or {}
    filename = payload.get("filename")
    success = payload.get("success", True)
    if not filename:
        return jsonify({"ok": False, "reason": "filename_required"}), 400
    result = card_queue.mark_card_processed(filename, success=success)
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


if __name__ == "__main__":
    # Локальный запуск, если нужно руками поднять небольшой сервис
    host = os.getenv("PUSH_SERVICE_HOST", "0.0.0.0")
    port = int(os.getenv("PUSH_SERVICE_PORT", "8001"))

    logger.info("Запускаем push_next_card Flask-сервис на %s:%s", host, port)
    app.run(host=host, port=port)
