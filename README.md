# PIFAGOR — Poultry Intelligence Framework / Archive

Проект PIFAGOR.

Структура папок:
- storage/incoming_photos/ — папка для необработанных фото карточек  
- storage/archive_photos/ — папка для обработанных исходников (архив)  
- storage/error_photos/ — папка для фото, которые не удалось обработать  
- storage/results_json/ — папка для JSON-результатов обработки  

- services/ — микросервисы:
    * ingestor — скрипт/сервис, следящий за incoming_photos  
    * worker — обработчик задач (GPT-агент, OCR, карточка → JSON)  
    * api — HTTP API для приёма/отдачи задач и результатов  
    * db_writer — сервис, записывающий результаты в базу  
    * utils — утилиты (OCR-скрипты, валидация, вспомогательные функции)

- gpts/ — промты / агенты:
    * card_extractor — промт + логика обработки карточек  
    * other_agents — место для будущих агентов (enrichment, аналитика ...)

- bot/ — Telegram-бот или иной интерфейс  
    * uploads — для временных файлов от пользователя  
    * handlers — обработчики команд / загрузок

- logs/ — логи работы сервисов

