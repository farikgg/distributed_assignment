"""
При создании обмена B берёт курс у сервиса A и сохраняет его копию (pair, rate)
прямо в записи. Поэтому GET /exchanges/{id} не обращается к A и работает,
даже если A остановлен.
"""
import os
import httpx

from decimal import ROUND_HALF_UP, Decimal
from itertools import count
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

RATES_URL = os.getenv("RATES_URL", "http://127.0.0.1:5001")
RATES_TIMEOUT = httpx.Timeout(2.0)  # connect, read, write и pool — по 2 секунды
CENT = Decimal("0.01")

app = FastAPI(title="Exchanges service")


class ExchangeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rate_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)  # сумма в валюте покупки


class RateSnapshot(BaseModel):
    pair: str
    rate: Decimal


class Exchange(BaseModel):
    id: int
    rate_id: int
    pair: str
    rate: Decimal
    amount: Decimal
    total: Decimal  # amount * rate, округлено до 2 знаков


EXCHANGES: dict[int, Exchange] = {}
_ids = count(1)


async def fetch_rate(rate_id: int) -> RateSnapshot:
    try:
        async with httpx.AsyncClient(base_url=RATES_URL, timeout=RATES_TIMEOUT) as client:
            response = await client.get(f"/rates/{rate_id}")
    except httpx.TransportError as exc:  # A остановлен, таймаут, обрыв соединения
        raise HTTPException(
            status_code=503,
            detail="Сервис курсов недоступен, попробуйте позже"
        ) from exc

    if response.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail=f"Тариф с id={rate_id} не найден"
        )

    try:
        response.raise_for_status()
        return RateSnapshot.model_validate(response.json())
    except (httpx.HTTPStatusError, ValueError) as exc:  # 5xx от A или битый JSON
        raise HTTPException(
            status_code=502,
            detail="Сервис курсов валют вернул неожиданный ответ",
        ) from exc


@app.post("/exchanges", status_code=201)
async def create_exchange(payload: ExchangeCreate) -> Exchange:
    rate = await fetch_rate(payload.rate_id)
    exchange = Exchange(
        id=next(_ids),
        rate_id=payload.rate_id,
        pair=rate.pair,
        rate=rate.rate,
        amount=payload.amount,
        total=(payload.amount * rate.rate).quantize(CENT, rounding=ROUND_HALF_UP),
    )
    EXCHANGES[exchange.id] = exchange
    return exchange


@app.get("/exchanges/{exchange_id}")
async def get_exchange(exchange_id: int) -> Exchange:
    exchange = EXCHANGES.get(exchange_id)
    if exchange is None:
        raise HTTPException(
            status_code=404,
            detail=f"Биржа с id={exchange_id} не найдена"
        )
    return exchange
