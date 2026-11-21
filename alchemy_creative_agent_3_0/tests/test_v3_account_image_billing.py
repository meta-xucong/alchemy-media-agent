import base64
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

from PIL import Image
import pytest

from alchemy_creative_agent_3_0.app.brand_memory import BrandProfileService, BrandProfileStore
from alchemy_creative_agent_3_0.app.llm_brain.providers import V3LLMBrainProvider
from alchemy_creative_agent_3_0.app.product_api.account_billing import (
    V3AccountImageBillingCheckpoint,
    V3AccountImageBillingError,
)
from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatusValue
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.service import (
    PersistentProductJobStore,
    V3ProductApiService,
)


USER_ID = 37
PRICE = Decimal("0.07")


class Wallet:
    def __init__(self, *, response_lost=False):
        self.response_lost = response_lost
        self.debit_calls = []
        self.transactions = {}
        self.before_debit = None
        self.insufficient_balance = False

    def prepare(self, user_id, requested_count):
        assert user_id == USER_ID
        if self.insufficient_balance:
            raise V3AccountImageBillingError("insufficient_balance")
        return PRICE

    def debit(self, user_id, amount, job_id):
        if self.before_debit:
            self.before_debit()
        self.debit_calls.append((user_id, amount, job_id))
        if self.insufficient_balance:
            raise V3AccountImageBillingError("insufficient_balance")
        assert self.transactions.setdefault(job_id, (user_id, amount)) == (user_id, amount)
        if self.response_lost:
            self.response_lost = False
            raise V3AccountImageBillingError("wallet_unavailable")


@pytest.fixture
def make_service(tmp_path, monkeypatch):
    monkeypatch.setattr(V3LLMBrainProvider, "available", lambda *_args, **_kwargs: False)

    def create(wallet):
        return V3ProductApiService(
            brand_profile_service=BrandProfileService(BrandProfileStore(tmp_path / "brands")),
            job_store=PersistentProductJobStore(tmp_path / "jobs"),
            output_store=V3GeneratedOutputStore(tmp_path / "outputs"),
            account_image_billing=wallet,
        )

    return create


def reviewed_job(service, review_statuses):
    created = service.create_job({"user_input": "Draw a geometric pattern."})
    record = service.job_store.get(created.job_id)
    assert record is not None and record.planning_result is not None
    record.request.metadata["veyra_user_id"] = USER_ID
    record.account_image_billing = V3AccountImageBillingCheckpoint(user_id=USER_ID, unit_price=PRICE)
    record.status = ProductJobStatusValue.FINALIZING

    png = BytesIO()
    Image.new("RGB", (24, 24), (77, 129, 194)).save(png, format="PNG")
    encoded_image = base64.b64encode(png.getvalue()).decode("ascii")
    inspections = []
    outputs = []
    for index, status in enumerate(review_statuses):
        output = service.output_store.save_base64_output(
            job_id=record.job_id,
            candidate_id=f"candidate_{index}",
            asset_id=f"asset_{index}",
            provider="fixture",
            model="fixture",
            encoded_image=encoded_image,
        )
        outputs.append(output.output_id)
        inspections.append(
            {
                "output_id": output.output_id,
                "asset_id": output.asset_id,
                "status": status,
                "mode": "vision_model",
                "verification_state": "verified",
                "evidence": {"provider_pixel_result_certified": True},
            }
        )
    result = record.planning_result.model_copy(deep=True)
    result.metadata["post_generation_review_package"] = {
        "review_evidence_receipt_status": "complete",
        "inspections": inspections,
    }
    record.generation_result = result
    service.job_store.save(record)
    return record, outputs


def test_review_only_delivery_does_not_charge(make_service):
    wallet = Wallet()
    service = make_service(wallet)
    record, _ = reviewed_job(service, ["manual_review", "fail_retryable"])

    service._finalize_reviewed_image_delivery(record)

    assert record.status == ProductJobStatusValue.GENERATED
    assert wallet.debit_calls == []


def test_insufficient_balance_blocks_before_generation(make_service, monkeypatch):
    wallet = Wallet()
    wallet.insufficient_balance = True
    service = make_service(wallet)
    job = service.create_job({"user_input": "Draw a geometric pattern.", "metadata": {"veyra_user_id": USER_ID}})
    monkeypatch.setattr(service.scenario_runtime, "generate_job", lambda *_args, **_kwargs: pytest.fail("provider called"))

    status = service.generate_asset_series(job.job_id)

    assert status.status == ProductJobStatusValue.BLOCKED
    assert status.metadata["image_billing"]["code"] == "insufficient_balance"
    assert wallet.debit_calls == []


def test_partial_delivery_charges_only_the_final_images(make_service):
    wallet = Wallet()
    service = make_service(wallet)
    record, outputs = reviewed_job(service, ["pass", "fail_retryable", "warning"])
    expected = {outputs[0], outputs[2]}

    def assert_durable_checkpoint():
        saved = make_service(wallet).job_store.get(record.job_id)
        assert saved is not None
        assert saved.status == ProductJobStatusValue.FINALIZING
        assert set(saved.account_image_billing.output_ids) == expected
        assert not saved.account_image_billing.charged
        assert service.output_store.get_job_closure(record.job_id) is None

    wallet.before_debit = assert_durable_checkpoint
    service._finalize_reviewed_image_delivery(record)

    assert record.status == ProductJobStatusValue.GENERATED
    assert wallet.debit_calls == [(USER_ID, Decimal("0.14"), record.job_id)]
    assert record.account_image_billing.charged
    assert set(record.account_image_billing.output_ids) == expected


def test_unreadable_approved_output_does_not_charge(make_service):
    wallet = Wallet()
    service = make_service(wallet)
    record, outputs = reviewed_job(service, ["pass"])
    original = service.output_store.file_for_variant(outputs[0], "download")
    assert original is not None
    original[0].unlink()

    service._finalize_reviewed_image_delivery(record)

    assert wallet.debit_calls == []
    assert not record.account_image_billing.charged
    assert service.output_store.get_job_closure(record.job_id) is None


def test_lost_receipt_replays_the_same_debit_after_restart(make_service, monkeypatch):
    wallet = Wallet(response_lost=True)
    service = make_service(wallet)
    record, outputs = reviewed_job(service, ["pass", "manual_review"])
    job_id = record.job_id
    service._finalize_reviewed_image_delivery(record)

    restarted = make_service(wallet)
    pending = restarted.job_store.get(job_id)
    assert pending is not None
    assert pending.status == ProductJobStatusValue.FINALIZING
    assert pending.account_image_billing.output_ids == (outputs[0],)
    assert pending.account_image_billing.code == "wallet_unavailable"
    assert not pending.account_image_billing.charged
    pending.account_image_billing.retry_after = 0
    restarted.job_store.save(pending)
    assert restarted.account_image_billing_retry_owner(job_id) == USER_ID

    def unexpected_generation(*_args, **_kwargs):
        pytest.fail("wallet recovery should use the existing generated output")

    monkeypatch.setattr(restarted.scenario_runtime, "generate_job", unexpected_generation)

    assert restarted.generate_asset_series(job_id).status == ProductJobStatusValue.GENERATED
    assert restarted.generate_asset_series(job_id).status == ProductJobStatusValue.GENERATED
    assert wallet.debit_calls == [(USER_ID, PRICE, job_id), (USER_ID, PRICE, job_id)]
    assert wallet.transactions == {job_id: (USER_ID, PRICE)}


def test_settlement_uses_existing_outputs_after_top_up(make_service):
    wallet = Wallet()
    wallet.insufficient_balance = True
    service = make_service(wallet)
    record, outputs = reviewed_job(service, ["pass"])

    status = service._finalize_reviewed_image_delivery(record)

    assert status.metadata["image_billing"]["code"] == "insufficient_balance"
    assert service.account_image_delivery_is_held(record.job_id)
    assert wallet.transactions == {}
    assert service.account_image_billing_retry_owner(record.job_id) is None
    record.account_image_billing.retry_after = 0
    service.job_store.save(record)
    assert service.account_image_billing_retry_owner(record.job_id) == USER_ID

    wallet.insufficient_balance = False
    status = service.generate_asset_series(record.job_id)

    assert status.status == ProductJobStatusValue.GENERATED
    assert status.metadata["image_billing"]["amount"] == "0.07"
    assert record.account_image_billing.output_ids == (outputs[0],)
    assert wallet.transactions == {record.job_id: (USER_ID, PRICE)}


def test_wallet_adapter_uses_one_job_key_and_records_one_usage_item(tmp_path, monkeypatch):
    from app.services import v3_veyra_billing, veyra_usage
    from app.services.veyra_auth import VeyraBillingRule, VeyraDebitResult

    calls = []
    balance_checks = []

    async def load_rule(rule_key, *, require_versioned):
        assert rule_key == "alchemy:v3" and require_versioned
        return VeyraBillingRule(key=rule_key, enabled=True, charge_amount=0.07, source=rule_key)

    async def check_balance(**payload):
        balance_checks.append(payload)

    async def debit(**payload):
        calls.append(payload)
        return VeyraDebitResult(USER_ID, 0.14, 1.10, payload["idempotency_key"], payload["source"], len(calls) > 1)

    monkeypatch.setattr(v3_veyra_billing, "load_billing_rule", load_rule)
    monkeypatch.setattr(v3_veyra_billing, "ensure_sufficient_balance", check_balance)
    monkeypatch.setattr(v3_veyra_billing, "debit_balance", debit)
    monkeypatch.setattr(veyra_usage, "settings", SimpleNamespace(veyra_usage_path=tmp_path / "usage.jsonl"))
    billing = v3_veyra_billing.V3VeyraImageBilling()

    assert billing.prepare(USER_ID, 2) == PRICE
    assert balance_checks == [{"user_id": USER_ID, "amount": 0.14}]
    billing.debit(USER_ID, Decimal("0.14"), "job_fixture")
    billing.debit(USER_ID, Decimal("0.14"), "job_fixture")

    assert calls == [{
        "user_id": USER_ID, "amount": 0.14, "idempotency_key": "alchemy:v3:image:job_fixture",
        "source": "alchemy:v3", "reference_id": "job_fixture",
    }] * 2
    assert veyra_usage.list_veyra_usage(USER_ID)["total"] == 1
