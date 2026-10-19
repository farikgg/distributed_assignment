from decimal import Decimal
from itertools import count

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(title="Rates service")


class RateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pair: str = Field(pattern=r"^[A-Z]{3}/[A-Z]{3}$")  # например, USD/KZT
    rate: Decimal = Field(gt=0, max_digits=12, decimal_places=4)


class Rate(BaseModel):
    id: int
    pair: str
    rate: Decimal


RATES: dict[int, Rate] = {}
_ids = count(1)


@app.post("/rates", status_code=201)
async def create_rate(payload: RateCreate) -> Rate:
    rate = Rate(id=next(_ids), **payload.model_dump())
    RATES[rate.id] = rate
    return rate


@app.get("/rates/{rate_id}")
async def get_rate(rate_id: int) -> Rate:
    rate = RATES.get(rate_id)
    if rate is None:
        raise HTTPException(status_code=404, detail=f"Тариф с id={rate_id} не найден")
    return rate
