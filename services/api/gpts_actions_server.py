"""
gpts_actions_server.py

HTTP-API для взаимодействия с GPT-агентом PIFAGOR.

Текущая архитектура (версия без очереди):
- Оператор отправляет изображение карточки предприятия прямо в диалог GPTs.
- Агент PIFAGOR выполняет OCR, структурирует данные по схеме PIFAGOR
  и вызывает единственный Action: POST /pifagor/submit_card_result
  c JSON-объектом вида: {"result": { ... }}

Сервер принимает этот JSON, записывает данные в БД и возвращает статус операции.
"""

import logging

from urllib.parse import urljoin

from flask import Flask, request, jsonify, send_file

from services.db_writer.db_writer import write_company_from_json
from services.worker import card_queue

app = Flask(__name__)
app.logger.setLevel(logging.INFO)


@app.post("/pifagor/submit_card_result")
@app.post("/submit_card_result")
def submit_card_result():
    """
    Принимает структурированный результат обработки карточки от GPT-агента PIFAGOR.

    Ожидаемый формат запроса:
      POST /pifagor/submit_card_result
      Content-Type: application/json

      {
          "result": { ... }  # JSON по схеме PIFAGOR
      }

    На выходе:
      200 OK:
      {
          "status": "ok",
          "company_id": <int или null>
      }

      При ошибке формата или записи:
      {
          "status": "error",
          "error_message": "..."
      }
      с кодом 400 или 500.
    """
    app.logger.info("POST /pifagor/submit_card_result: incoming request")

    # Пробуем разобрать тело запроса как JSON
    data = request.get_json(silent=True)
    if not data:
        app.logger.warning("Request has no JSON body")
        return (
            jsonify(
                {
                    "status": "error",
                    "error_message": "Ожидается JSON-тело запроса (application/json).",
                }
            ),
            400,
        )

    filename = data.get("filename")
    result = data.get("result")

    # Обязательное поле result
    if result is None:
        app.logger.warning("Missing 'result' field: %s", data)
        return (
            jsonify(
                {
                    "status": "error",
                    "error_message": "Отсутствует обязательное поле 'result'.",
                }
            ),
            400,
        )

    # result должен быть JSON-объектом (dict)
    if not isinstance(result, dict):
        app.logger.warning("'result' is not dict: %s", type(result))
        return (
            jsonify(
                {
                    "status": "error",
                    "error_message": "Поле 'result' должно быть JSON-объектом.",
                }
            ),
            400,
        )

    try:
        # Пишем компанию в БД.
        # Функция write_company_from_json сама разбирает структуру PIFAGOR.
        company_id = write_company_from_json(result)
    except Exception as exc:
        # Логируем стек-трейс для отладки.
        app.logger.exception("Ошибка при записи компании из JSON.")
        return (
            jsonify(
                {
                    "status": "error",
                    "error_message": f"Ошибка записи в БД: {exc}",
                }
            ),
            500,
        )

    response = {"status": "ok", "company_id": company_id, "error_message": ""}
    if filename:
        queue_info = card_queue.mark_card_processed(filename, success=True)
        response["queue"] = queue_info
    app.logger.info("Response: %s", response)
    return jsonify(response)


def _build_file_url(filename: str) -> str:
    proto = request.headers.get("X-Forwarded-Proto", request.scheme)
    host = request.headers.get("Host", request.host)
    base = f"{proto}://{host}/"
    return urljoin(base, f"pifagor/files/{filename}")


@app.post("/pifagor/push_next_card")
def api_push_next_card():
    result = card_queue.push_next_card()
    filename = result.get("filename")
    if filename:
        result["file_url"] = _build_file_url(filename)
    return jsonify(result)


@app.get("/pifagor/files/<filename>")
def api_get_file(filename: str):
    path = card_queue.get_file_path(filename)
    if not path:
        return jsonify({"ok": False, "reason": "file_not_found"}), 404
    return send_file(path)


@app.post("/pifagor/mark_processed")
def api_mark_processed():
    payload = request.get_json(force=True) or {}
    filename = payload.get("filename")
    success = payload.get("success", True)
    if not filename:
        return jsonify({"ok": False, "reason": "filename_required"}), 400
    result = card_queue.mark_card_processed(filename, success=success)
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@app.get("/")
def healthcheck():
    """Простейший health-check для внешних проверок."""
    current = card_queue.get_in_progress_file()
    return jsonify({"status": "ok", "in_progress": current.name if current else None})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7001)
