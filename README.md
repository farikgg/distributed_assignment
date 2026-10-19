# Два сервиса: курсы валют и обмен валюты

Два FastAPI-сервиса в отдельных процессах, данные хранятся в памяти.

- **A — Rates** (порт 5001): справочник курсов валют.
- **B — Exchanges** (порт 5002): обмен валюты. При создании обмена B запрашивает курс у A по HTTP (таймаут 2 с), считает итоговую сумму и сохраняет у себя копию курса.

Соответствие терминам задания:

| В задании | Здесь |
|---|---|
| Catalog / product (name, price) | Rates / rate (`pair`, `rate`) |
| Orders / order | Exchanges / exchange |
| `product_id`, `quantity` | `rate_id`, `amount` |
| total | `total` = `amount` × `rate`, округление до 2 знаков |

Денежные поля передаются и возвращаются строками (`"495.50"`), внутри используется `Decimal`: так нет ошибок округления float.

## Запуск

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

В двух отдельных терминалах из корня репозитория:

```bash
uvicorn rates.main:app --port 5001
uvicorn exchanges.main:app --port 5002
```

Адрес A по умолчанию `http://127.0.0.1:5001`, меняется переменной окружения `RATES_URL`.

## Эндпоинты

**A, порт 5001**
- `POST /rates` — тело `{"pair": "USD/KZT", "rate": "495.50"}`, ответ `201`.
- `GET /rates/{id}` — `200` или `404`.

**B, порт 5002**
- `POST /exchanges` — тело `{"rate_id": 1, "amount": "100.00"}`, ответ `201`.
- `GET /exchanges/{id}` — `200` или `404`. К A не обращается.

Ошибки B при создании обмена:

| Ситуация | Код |
|---|---|
| A остановлен или не ответил за 2 с | `503` |
| A ответил `404` (нет такого курса) | `404` |
| A вернул 5xx или не-JSON | `502` |
| некорректное тело запроса | `422` |

## Три проверки

Вручную:

```bash
# 1. Оба сервиса работают
curl -i -X POST localhost:5001/rates -H 'Content-Type: application/json' -d '{"pair": "USD/KZT", "rate": "495.50"}'
curl -i -X POST localhost:5002/exchanges -H 'Content-Type: application/json' -d '{"rate_id": 1, "amount": "100.00"}'

# 2. Остановить A (Ctrl+C в его терминале), создать ещё один обмен -> 503
curl -i -X POST localhost:5002/exchanges -H 'Content-Type: application/json' -d '{"rate_id": 1, "amount": "50.00"}'

# 3. A всё ещё остановлен, читаем сохранённый обмен -> 200
curl -i localhost:5002/exchanges/1
```

Автоматически: `bash demo.sh` (нужны bash и curl, на Windows — Git Bash). Скрипт поднимает оба сервиса, выполняет три проверки, останавливает A посреди прогона и пишет логи в `evidence/`.

## Подтверждения

В `evidence/`:
- `01_both_running.log`, `02_a_stopped_create.log`, `03_a_stopped_get.log` — запросы и ответы трёх проверок;
- `exchanges_service.log` — лог B: `201`, затем `503` при остановленном A, затем `200`. Сервис B продолжает работать.