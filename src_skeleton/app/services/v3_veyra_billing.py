from __future__ import annotations

import asyncio
import logging
from decimal import Decimal, InvalidOperation

from alchemy_creative_agent_3_0.app.product_api.account_billing import V3AccountImageBillingError
from app.services.veyra_auth import (
    VeyraAuthError,
    VeyraInsufficientBalance,
    debit_balance,
    ensure_sufficient_balance,
    load_billing_rule,
)
from app.services.veyra_usage import VeyraUsageRecord, record_veyra_usage


SOURCE = "alchemy:v3"
logger = logging.getLogger(__name__)


class V3VeyraImageBilling:
    """Connect the synchronous V3 worker to the same wallet used by V1 and LAB."""

    def prepare(self, user_id: int, requested_count: int) -> Decimal | None:
        return asyncio.run(self._prepare(user_id, requested_count))

    async def _prepare(self, user_id: int, requested_count: int) -> Decimal | None:
        try:
            rule = await load_billing_rule(SOURCE, require_versioned=True)
            if not rule.enabled:
                return None
            price = Decimal(str(rule.charge_amount))
            if not price.is_finite() or price <= 0 or price != price.quantize(Decimal("0.00000001")):
                raise V3AccountImageBillingError("wallet_unavailable")
            await ensure_sufficient_balance(user_id=user_id, amount=float(price * requested_count))
            return price
        except VeyraInsufficientBalance:
            raise V3AccountImageBillingError("insufficient_balance") from None
        except (VeyraAuthError, InvalidOperation, TypeError, ValueError):
            raise V3AccountImageBillingError("wallet_unavailable") from None

    def debit(self, user_id: int, amount: Decimal, job_id: str) -> None:
        key = f"{SOURCE}:image:{job_id}"
        try:
            receipt = asyncio.run(debit_balance(
                user_id=user_id, amount=float(amount), idempotency_key=key, source=SOURCE, reference_id=job_id,
            ))
            if (receipt.user_id != user_id or receipt.idempotency_key != key
                    or receipt.source != SOURCE or Decimal(str(receipt.amount)) != amount):
                raise V3AccountImageBillingError("wallet_unavailable")
        except VeyraInsufficientBalance:
            raise V3AccountImageBillingError("insufficient_balance") from None
        except (VeyraAuthError, InvalidOperation, TypeError, ValueError):
            raise V3AccountImageBillingError("wallet_unavailable") from None
        try:
            record_veyra_usage(VeyraUsageRecord(
                user_id=user_id, amount=receipt.amount, balance_after=receipt.balance_after,
                idempotency_key=key, reference_id=job_id, source=SOURCE, replayed=receipt.replayed,
            ), deduplicate=True)
        except OSError:
            logger.exception("V3 wallet receipt could not be copied to local usage for job %s", job_id)
