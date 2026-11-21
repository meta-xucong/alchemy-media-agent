from __future__ import annotations

from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, Field


BillingErrorCode = Literal["insufficient_balance", "wallet_unavailable", "delivery_unavailable"]


class V3AccountImageBillingError(RuntimeError):
    def __init__(self, code: BillingErrorCode) -> None:
        self.code = code
        super().__init__(code)


class V3AccountImageBilling(Protocol):
    def prepare(self, user_id: int, requested_count: int) -> Decimal | None: ...

    def debit(self, user_id: int, amount: Decimal, job_id: str) -> None: ...


class V3AccountImageBillingCheckpoint(BaseModel):
    user_id: int = Field(gt=0)
    unit_price: Decimal | None = Field(default=None, gt=0)
    output_ids: tuple[str, ...] = ()
    charged: bool = False
    code: BillingErrorCode | None = None
    retry_after: float = 0

    @property
    def amount(self) -> Decimal:
        return (self.unit_price or Decimal("0")) * len(self.output_ids)
