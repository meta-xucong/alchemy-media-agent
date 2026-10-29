"""Real V3 production entrance; network/executors are deterministic doubles."""
import asyncio
import base64
import hashlib
from dataclasses import replace
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

import render_bridge_primary as core
from render_bridge_primary.http import BridgeError
from app.providers.base import ProviderRuntimeError
from app.schemas import ImageGenerationResult
from alchemy_creative_agent_3_0.app.generation_router import ProductionImageGenerationProvider
from alchemy_creative_agent_3_0.app.generation_router import bridge_primary as adapter
from alchemy_creative_agent_3_0.app.product_api.contracts import GenerateJobRequest
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.schemas import ProviderStrategy
from alchemy_creative_agent_3_0.tests.test_v3_provider_output_production import _generation_request


class Client:
    def __init__(self):
        stream = BytesIO()
        Image.new('RGB', (73, 41), (12, 30, 50)).save(stream, format='PNG')
        self.content = stream.getvalue()
        self.calls = 0
        self.acks = []
        self.uploads = []
        self.state = 'artifacts_ready'
        self.error = None
        self.input_error = None
        self.transparent_supported = True

    async def capabilities(self):
        result = {'admission': {'accepting_new_tasks': True},
            'limits': {'max_input_bytes': 16*1024*1024, 'max_input_image_pixels': 16*1024*1024},
            'routing_availability_v1': {'profiles': [{'profile_id': 'codex-image', 'health': 'available', 'valid_until': '2099-01-01T00:00:00+00:00'}]},
            'profiles': [{'execution_profile_id': 'codex-image', 'execution_profile_revision': '1',
            'parameter_contract': {'accepted_parameters': ['width', 'height', 'image_options'], 'dimension_semantics': 'original_dimensions_recorded',
                'codex_adapter': {'values': ['codex_cli_imagegen_v1'], 'image_options_contract': {
                    'transparent_background': {'values': [True, False]}, 'references': {'max_count': 5}}}},
            'image_options_contract': {'quality': {'values': ['auto']}, 'output_format': {'values': ['png', 'jpeg']}, 'references': {'max_count': 8}},
            'limits': {'max_output_bytes': 16777216}}]}
        if not self.transparent_supported:
            del result['profiles'][0]['parameter_contract']['codex_adapter']['image_options_contract']['transparent_background']
        return result

    async def create_input(self, payload):
        return {'input_id': payload['input_key']}

    async def upload_input(self, ref_id, content, mime_type):
        self.uploads.append((ref_id, content, mime_type))
        if self.input_error:
            raise self.input_error

    async def create_task(self, payload):
        self.calls += 1
        self.payload = payload
        if self.error:
            raise self.error
        return self.task_record()

    def task_record(self):
        return {'remote_task_id': 'task_1', 'origin_key': self.payload['origin_key'], 'request': self.payload,
                'attempt_id': 'attempt_1', 'state': self.state, 'receipt_id': 'receipt_1' if self.state == 'artifacts_ready' else None}

    async def by_origin(self, origin):
        if self.error:
            raise BridgeError('not_found', status=404)
        return self.task_record()

    async def task(self, task_id):
        return self.task_record()

    async def receipt(self, rid):
        return {'receipt_id': rid, 'task_id': 'task_1', 'artifact_id': 'artifact_1', 'attempt_id': 'attempt_1',
                'execution_profile_id': 'codex-image', 'execution_profile_revision': '1', 'slot_id': 'primary',
                'original_sha256': hashlib.sha256(self.content).hexdigest(), 'size': len(self.content),
                'mime_type': 'image/png', 'dimensions': {'width': 73, 'height': 41}}

    async def artifact(self, aid, limit):
        return self.content, {}

    async def accept_registered_receipt(self, *args, **kwargs):
        self.acks.append(kwargs)

    async def close(self):
        pass


@pytest.fixture
def rig(tmp_path, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, 'openai_api_key', '')
    monkeypatch.setattr(settings, 'default_image_provider', 'openai_gpt_image')
    cfg = core.PrimarySettings(enabled=True, base_url='http://127.0.0.1:9999', token='fixture', state_dir=tmp_path / 'ledger')
    client = Client()
    transport_type = core.PrimaryTransport
    monkeypatch.setattr(core.PrimarySettings, 'from_env', classmethod(lambda cls, product: cfg))
    monkeypatch.setattr(core, 'PrimaryTransport', lambda settings: transport_type(settings, client=client))
    monkeypatch.setattr(adapter, 'POLL_BUDGET_SECONDS', 0)
    store = V3GeneratedOutputStore(tmp_path / 'outputs')
    provider = ProductionImageGenerationProvider(output_store=store)
    api_calls = []
    async def legacy(request):
        api_calls.append(request)
        return ImageGenerationResult(provider='legacy', model='synthetic', outputs=[{
            'b64_json': base64.b64encode(client.content).decode(), 'mime_type': 'image/png', 'format': 'png'}])
    monkeypatch.setattr(provider, '_app_provider', lambda name: SimpleNamespace(generate=legacy))
    request = _generation_request()
    request.metadata.update(provider_image_options={'quality': 'auto'}, veyra_user_id=7, project_id='project_7', requested_image_aspect_ratio='1:1')
    return SimpleNamespace(cfg=cfg, client=client, provider=provider, request=request, api_calls=api_calls, store=store,
                           transport_type=transport_type)


def test_bridge_enabled_new_v3_provider_job_freezes_real_image_strategy(tmp_path, monkeypatch):
    configured = core.PrimarySettings(
        enabled=True,
        base_url="http://127.0.0.1:9999",
        token="fixture",
        state_dir=tmp_path / "ledger",
    )
    monkeypatch.setattr(
        core.PrimarySettings,
        "from_env",
        classmethod(lambda cls, product: configured if product == "v3" else core.PrimarySettings()),
    )
    service = V3ProductApiService.__new__(V3ProductApiService)
    create_request = SimpleNamespace(metadata={}, uploaded_asset_ids=[])

    service._bind_bridge_primary_real_image_requirement(create_request, generation_channel="provider")

    record = SimpleNamespace(request=create_request)
    assert create_request.metadata["require_real_images"] is True
    assert service._provider_strategy_for_generate(record, GenerateJobRequest()) == ProviderStrategy.DEFAULT_IMAGE_PROVIDER


def test_actual_entrance_preserves_original_and_replays_checkpoint(rig):
    first = rig.provider.generate(rig.request)
    second = rig.provider.generate(rig.request)
    a, b = first.candidates[0], second.candidates[0]
    assert a.candidate_id == b.candidate_id
    assert a.metadata['output_id'] == b.metadata['output_id']
    record = rig.store.get_output(a.metadata['output_id'])
    from pathlib import Path
    assert Path(record.file_path).read_bytes() == rig.client.content
    assert (record.width, record.height) == (73, 41)
    assert record.metadata['content_sha256'] == hashlib.sha256(rig.client.content).hexdigest()
    assert 'aspect_ratio_normalization' not in record.metadata
    assert len(rig.client.acks) == rig.client.calls == 1
    assert rig.api_calls == []
    assert a.metadata['runtime_mode'] == 'production_image_generation'


@pytest.mark.parametrize('optional_controls', [
    {'quality': 'medium'}, {'quality': 'high'},
    {'quality': 'auto', 'background': 'transparent'},
    {'quality': 'auto', 'output_compression': 80}, {'quality': 'auto', 'output_format': 'webp'},
    {'quality': 'auto', 'seed': 42},
])
def test_optional_controls_use_native_bridge_defaults(rig, optional_controls):
    rig.request.metadata['provider_image_options'] = optional_controls
    response = rig.provider.generate(rig.request)
    assert response.candidates[0].provider == 'render_bridge'
    assert rig.client.calls == 1 and not rig.api_calls
    params = rig.client.payload['parameters']
    assert params.get('codex_adapter') == 'codex_cli_imagegen_v1'
    assert not {'width', 'height', 'seed'} & params.keys()
    if optional_controls.get('background') == 'transparent':
        assert params['image_options'] == {'schema_version': '1', 'transparent_background': True}
    else:
        assert 'image_options' not in params
    rig.provider.generate(rig.request)
    assert rig.client.calls == 1


def test_unsupported_transparency_uses_native_default_and_keeps_bridge(rig):
    rig.client.transparent_supported = False
    rig.request.metadata['provider_image_options'] = {
        'quality': 'auto', 'transparent_background': True,
    }
    response = rig.provider.generate(rig.request)
    assert response.candidates[0].provider == 'render_bridge'
    assert rig.client.calls == 1 and not rig.api_calls
    assert rig.client.payload['parameters'] == {'codex_adapter': 'codex_cli_imagegen_v1'}


@pytest.mark.parametrize('defaultable_controls', [
    {'moderation': 'low'}, {'moderation': 'auto'}, {'count': 2},
    {'provider_hint': 'legacy-provider'}, {'strong_identity': True},
    {'input_fidelity_required': True}, {'required_reference_conditioning': True},
])
def test_codex_defaulted_controls_do_not_remain_as_hard_requirements(rig, defaultable_controls):
    rig.request.metadata['provider_image_options'] = defaultable_controls
    app_request = rig.provider._build_app_request(rig.request)[0]
    frozen = adapter.request_for(app_request)
    normalized = set(defaultable_controls)
    assert not normalized.intersection(frozen.hard_requirements)
    assert not {f'option_{key}' for key in normalized}.intersection(frozen.hard_requirements)

    result = rig.provider.generate(rig.request)
    assert result.candidates[0].provider == 'render_bridge'
    assert rig.client.calls == 1 and not rig.api_calls


def test_unsupported_requirement_exposes_safe_diagnostic_and_keeps_api_route(rig):
    rig.request.metadata['provider_image_options'] = {'unmodeled_render_control': 'private-value'}
    result = rig.provider.generate(rig.request)
    provenance = result.candidates[0].metadata[adapter.PROVENANCE]
    assert result.candidates[0].provider == 'legacy'
    assert provenance['route'] == 'api'
    assert provenance['reason'] == 'bridge_capability_unsupported'
    assert provenance['capability_rejection'] == {'code': 'hard_requirement_not_advertised'}
    assert 'private-value' not in repr(provenance)
    assert rig.client.calls == 0


@pytest.mark.parametrize('malformed', [
    {'profiles': [{'execution_profile_id': 'codex-image', 'execution_profile_revision': '1',
                   'parameter_contract': True}]},
    {'profiles': [{'execution_profile_id': 'codex-image', 'execution_profile_revision': '1',
                   'parameter_contract': {'codex_adapter': {'image_options_contract': None}}}]},
    {'profiles': [], 'admission': None},
    {'profiles': [], 'routing_availability_v1': None},
    {'profiles': [], 'routing_availability_v1': {'profiles': None}},
])
def test_malformed_nested_bridge_capabilities_use_safe_rejection(rig, malformed):
    app_request = rig.provider._build_app_request(rig.request)[0]
    request = adapter.request_for(app_request)
    assert rig.transport_type._safe_support_rejection(request, malformed, 'codex-image') == {
        'code': 'capability_contract_invalid',
    }


@pytest.mark.parametrize('malformed', [
    {'profiles': [{'execution_profile_id': 'codex-image', 'execution_profile_revision': '1',
                   'parameter_contract': True}]},
    {'profiles': [{'execution_profile_id': 'codex-image', 'execution_profile_revision': '1',
                   'parameter_contract': {'codex_adapter': {'image_options_contract': {
                       'transparent_background': True}}}}]},
])
def test_malformed_transparency_capability_uses_native_default(malformed):
    assert adapter._codex_transparency_supported(malformed, 'codex-image') is False


def test_create_loss_restart_and_unknown_never_legacy(rig):
    rig.client.error = BridgeError('bridge_unreachable')
    for _ in range(2):
        with pytest.raises(ProviderRuntimeError) as caught:
            rig.provider.generate(rig.request)
        assert caught.value.detail['transport_retry_terminal'] is True
    assert rig.client.calls == 1
    assert not rig.api_calls
    assert not rig.store.list_by_job('job_v3_prod')
    rig.client.error = None
    response = rig.provider.generate(rig.request)
    assert response.candidates and rig.client.calls == 1


def test_wait_budget_expiry_keeps_same_bridge_task_for_recovery(rig):
    rig.client.state = 'running'
    with pytest.raises(ProviderRuntimeError) as caught:
        rig.provider.generate(rig.request)
    assert caught.value.detail['transport_retry_terminal'] is True
    assert caught.value.detail['failure_code'] == 'bridge_wait_budget_exhausted'
    assert caught.value.provider_failure_retry['final_status'] == 'pending'
    assert rig.client.calls == 1 and not rig.api_calls

    from alchemy_creative_agent_3_0.app.product_api.service import (
        ProductJobStatusValue,
        V3ProductApiService,
    )

    service, blocked_record = _cancel_service(rig)
    blocked_record.status = ProductJobStatusValue.BLOCKED
    blocked_record.planning_result = SimpleNamespace()
    assert not V3ProductApiService._blocked_planning_reentry_requires_explicit_resume(
        blocked_record,
        resume_finalizing_review=False,
        resume_interrupted_mcp_materialization=False,
    )

    rig.client.state = 'artifacts_ready'
    response = rig.provider.generate(rig.request)
    assert response.candidates[0].provider == 'render_bridge'
    assert rig.client.calls == 1 and not rig.api_calls


def test_bridge_poll_and_v3_provider_finalization_fit_300_second_budget():
    assert adapter.POLL_BUDGET_SECONDS == 285.0
    assert adapter.POLL_BUDGET_SECONDS + 15.0 == 300.0


def test_queue_full_then_same_unit_api_is_single_claim(rig):
    rig.client.error = BridgeError('queue_capacity', status=429)
    rig.provider.generate(rig.request)
    rig.provider.generate(rig.request)
    assert rig.client.calls == 1 and len(rig.api_calls) == 1


def test_frozen_unit_rejects_changed_prompt_after_admission(rig):
    rig.client.state = 'running'
    with pytest.raises(ProviderRuntimeError):
        rig.provider.generate(rig.request)
    rig.request.metadata['llm_brain']['canonical_provider_prompts'][0]['prompt'] += ' changed'
    with pytest.raises(ProviderRuntimeError):
        rig.provider.generate(rig.request)
    assert rig.client.calls == 1 and not rig.api_calls


def test_unsignoff_never_enters_bridge(rig):
    rig.request.metadata.pop('llm_brain')
    with pytest.raises(ProviderRuntimeError):
        rig.provider.generate(rig.request)
    assert rig.client.calls == 0 and not rig.api_calls


def test_disabled_still_resumes_existing_bridge(rig, monkeypatch):
    # This case verifies same-task recovery after the wait budget is spent.
    # Keep the polling window empty so the unit test does not wait the full
    # production budget before checking the stable failure classification.
    monkeypatch.setattr(adapter, "POLL_BUDGET_SECONDS", 0.0)
    rig.client.state = 'execution_unknown'
    with pytest.raises(ProviderRuntimeError) as caught:
        rig.provider.generate(rig.request)
    assert caught.value.provider == 'render_bridge'
    assert caught.value.detail['failure_code'] == 'bridge_wait_budget_exhausted'
    monkeypatch.setattr(core.PrimarySettings, 'from_env', classmethod(lambda cls, product: replace(rig.cfg, enabled=False)))
    rig.client.state = 'artifacts_ready'
    response = rig.provider.generate(rig.request)
    assert response.candidates[0].provider == 'render_bridge'
    assert rig.client.calls == 1 and not rig.api_calls


def _cancel_service(rig, job_id='job_v3_prod'):
    from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService, ProductJobRecord, InMemoryProductJobStore
    from alchemy_creative_agent_3_0.app.product_api.contracts import CreateCreativeJobRequest, ProductJobStatusValue
    service = object.__new__(V3ProductApiService)
    service.job_store = InMemoryProductJobStore()
    service._build_lifecycle = lambda record: None
    record = ProductJobRecord(request=CreateCreativeJobRequest(user_input='fixture', metadata={'veyra_user_id': 7, 'project_id': 'project_7'}),
        status=ProductJobStatusValue.GENERATING, job_id_value=job_id)
    service.job_store.save(record)
    return service, record


def test_product_cancel_is_owner_scoped_and_blocks_late_pixels(rig):
    rig.client.state = 'running'
    rig.client.cancels = []
    async def cancel(task_id):
        rig.client.cancels.append(task_id)
    rig.client.cancel = cancel
    with pytest.raises(ProviderRuntimeError):
        rig.provider.generate(rig.request)
    service, record = _cancel_service(rig)
    with pytest.raises(ValueError, match='target_not_found'):
        asyncio.run(service.cancel_primary_bridge_generation('job_v3_prod', owner_user_id=8))
    assert not rig.client.cancels
    result = asyncio.run(service.cancel_primary_bridge_generation('job_v3_prod', owner_user_id=7))
    assert result['status'] == 'cancel_requested'
    assert rig.client.cancels == ['task_1']
    rig.client.state = 'artifacts_ready'
    with pytest.raises(ProviderRuntimeError):
        rig.provider.generate(rig.request)
    assert not rig.store.list_by_job('job_v3_prod')
    assert not rig.client.acks and not rig.api_calls and rig.client.calls == 1
    assert service._background_generation_attempt_is_current(record, '') is False


def test_product_cancel_does_not_cancel_api_fallback(rig):
    rig.client.error = BridgeError('queue_capacity', status=429)
    rig.provider.generate(rig.request)
    service, record = _cancel_service(rig)
    with pytest.raises(ValueError, match='target_not_found'):
        asyncio.run(service.cancel_primary_bridge_generation('job_v3_prod', owner_user_id=7))
    assert not record.request.metadata.get('render_bridge_primary_cancel_requested')


def test_checkpoint_cancel_race_never_returns_candidate(rig, monkeypatch):
    original_save = rig.store.save_base64_output
    def cancel_after_checkpoint(**kwargs):
        record = original_save(**kwargs)
        transport = core.PrimaryTransport(rig.cfg)
        app_request, _, _ = rig.provider._build_app_request(rig.request)
        request = adapter.request_for(app_request)
        rig.client.cancel = lambda task_id: asyncio.sleep(0)
        asyncio.run(transport.cancel_binding(request.product, request.owner_id, request.unit_id))
        return record
    monkeypatch.setattr(rig.store, 'save_base64_output', cancel_after_checkpoint)
    with pytest.raises(ProviderRuntimeError):
        rig.provider.generate(rig.request)
    assert not rig.client.acks and not rig.api_calls
    # Persisted original bytes are quarantined, not a candidate/review/slot result.
    assert len(rig.store.list_by_job('job_v3_prod')) == 1


def test_visual_review_new_unit_not_transport_retry(rig):
    first = rig.provider._build_app_request(rig.request)[0]
    rig.request.metadata['retry_attempt'] = 19
    transport_retry = rig.provider._build_app_request(rig.request)[0]
    assert adapter.request_for(first).unit_id == adapter.request_for(transport_retry).unit_id
    rig.request.metadata['visual_auto_retry_attempt'] = 1
    visual_retry = rig.provider._build_app_request(rig.request)[0]
    assert adapter.request_for(first).unit_id != adapter.request_for(visual_retry).unit_id


def test_cancel_endpoint_enforces_existing_owner_guard(monkeypatch):
    from fastapi import HTTPException
    from app import main
    monkeypatch.setattr(main.settings, 'veyra_auth_enabled', True)
    monkeypatch.setattr(main, '_veyra_user_id_from_request', lambda request, authorization: 8)
    monkeypatch.setattr(main, '_v3_job_owner_id', lambda job_id: 7)
    with pytest.raises(HTTPException) as caught:
        asyncio.run(main.v3_cancel_primary_bridge_endpoint('job_v3_prod', SimpleNamespace(), ''))
    assert caught.value.status_code == 404


def test_quarantined_bridge_output_not_recovered_as_candidate(rig):
    rig.client.state = 'running'
    with pytest.raises(ProviderRuntimeError):
        rig.provider.generate(rig.request)
    service, record = _cancel_service(rig)
    service.output_store = rig.store
    record.request.metadata['render_bridge_primary_cancel_requested'] = True
    assert service._status_from_output_store('job_v3_prod') is None


def test_real_multi_output_loop_replays_first_checkpoint_and_recovers_second(rig, monkeypatch):
    """Run real Central Brain output iteration twice, with a process-style restart."""
    from copy import deepcopy
    from alchemy_creative_agent_3_0.app.creative_core.central_brain import CentralCreativeBrain
    from alchemy_creative_agent_3_0.app.generation_router import GenerationRouter
    from alchemy_creative_agent_3_0.app.schemas import ProviderStrategy

    tasks = {}
    receipts = {}
    finished = False
    async def create(payload):
        rig.client.calls += 1
        index = len(tasks) + 1
        task = {'remote_task_id': f'task_{index}', 'origin_key': payload['origin_key'], 'request': payload,
                'attempt_id': f'attempt_{index}', 'state': 'artifacts_ready' if index == 1 else 'execution_unknown',
                'receipt_id': f'receipt_{index}' if index == 1 else None}
        tasks[payload['origin_key']] = task
        receipts[f'receipt_{index}'] = index
        return task
    async def by_origin(origin):
        task = dict(tasks[origin])
        if finished:
            task['state'] = 'artifacts_ready'
            task['receipt_id'] = 'receipt_' + task['remote_task_id'].split('_')[-1]
        return task
    async def task(task_id):
        return await by_origin(next(key for key, value in tasks.items() if value['remote_task_id'] == task_id))
    async def receipt(rid):
        index = receipts[rid]
        return {'receipt_id': rid, 'task_id': f'task_{index}', 'artifact_id': f'artifact_{index}',
                'attempt_id': f'attempt_{index}', 'execution_profile_id': 'codex-image',
                'execution_profile_revision': '1', 'slot_id': 'primary',
                'original_sha256': hashlib.sha256(rig.client.content).hexdigest(), 'size': len(rig.client.content),
                'mime_type': 'image/png', 'dimensions': {'width': 73, 'height': 41}}
    rig.client.create_task = create
    rig.client.by_origin = by_origin
    rig.client.task = task
    rig.client.receipt = receipt
    metadata = deepcopy(rig.request.metadata)
    metadata.update(requested_image_count=2, template_id='general_template', scenario_id='general_creative')
    first_prompt = metadata['llm_brain']['canonical_provider_prompts'][0]
    metadata['llm_brain']['canonical_provider_prompts'] = [
        {**first_prompt, 'output_index': 1, 'prompt': 'An abstract blue mountain landscape.'},
        {**first_prompt, 'output_index': 2, 'prompt': 'An abstract orange desert landscape.'}]
    def run():
        provider = ProductionImageGenerationProvider(output_store=rig.store)
        async def no_api(request):
            raise AssertionError('No API transport allowed')
        monkeypatch.setattr(provider, '_app_provider', lambda name: SimpleNamespace(generate=no_api))
        brain = CentralCreativeBrain(generation_router=GenerationRouter(provider=provider))
        return brain.run_generation_loop('Create two independent abstract landscape images.',
            provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER, runtime_metadata=deepcopy(metadata))
    with pytest.raises(ProviderRuntimeError):
        run()
    assert len(tasks) == rig.client.calls == 2
    first_checkpoint = rig.store.list_outputs()[0]
    frozen = {key: deepcopy(value['request']) for key, value in tasks.items()}
    finished = True
    result = run()
    assert len(result.asset_pack.assets) == 2
    assert rig.client.calls == 2
    assert {key: value['request'] for key, value in tasks.items()} == frozen
    assert first_checkpoint.file_path in {item.file_path for item in result.asset_pack.assets}
    assert len(rig.store.list_outputs()) == 2


def test_materialized_identity_reference_uses_native_defaults_and_keeps_image(rig, tmp_path):
    path = tmp_path / 'reference.png'
    path.write_bytes(rig.client.content)
    request = _generation_request(path)
    request.metadata.update(provider_image_options={'quality': 'auto'}, veyra_user_id=7, project_id='project_7')
    app_request, _, _ = rig.provider._build_app_request(request)
    frozen = adapter.request_for(app_request)
    assert frozen.references
    assert 'strong_identity' not in frozen.hard_requirements
    assert 'input_fidelity_required' not in frozen.hard_requirements
    response = rig.provider.generate(request)
    assert response.candidates[0].provider == 'render_bridge'
    assert rig.client.calls == 1 and not rig.api_calls
    assert len(rig.client.uploads) == len(frozen.references)
    assert sorted(hashlib.sha256(item[1]).hexdigest() for item in rig.client.uploads) == sorted(
        hashlib.sha256(reference.content).hexdigest() for reference in frozen.references
    )
    assert response.candidates[0].metadata[adapter.PROVENANCE]['route'] == 'bridge'


def test_prior_codex_journal_digest_matches_and_recovers_same_task(rig, tmp_path):
    from render_bridge_primary.codex_adapter import CODEX_ADAPTER_VERSION, codex_cli_adaptation

    path = tmp_path / 'reference.png'
    path.write_bytes(rig.client.content)
    request = _generation_request(path)
    request.metadata.update(provider_image_options={'quality': 'auto'}, veyra_user_id=7, project_id='project_7')
    app_request = rig.provider._build_app_request(request)[0]
    source = adapter._source_request(app_request, native_defaults=True)
    plan = app_request.prompt_plan
    options = dict(plan.variables.get('provider_image_options') or {})
    prior_params = {**options, 'background': plan.background,
                    'transparent_background': bool(plan.transparent_background or
                        options.get('transparent_background') is True or plan.background == 'transparent')}
    wire, _ = codex_cli_adaptation(prior_params, len(source.references))
    wire['codex_adapter'] = CODEX_ADAPTER_VERSION
    optional = {'quality', 'size', 'width', 'height', 'aspect_ratio', 'output_format',
                'output_compression', 'seed', 'input_fidelity', 'background',
                'transparent_background'}
    prior_requirements = {
        key: value for key, value in source.hard_requirements.items()
        if key not in optional and not (key.startswith('option_') and key[7:] in optional)
    }
    prior = replace(source, parameters=wire, hard_requirements=prior_requirements)
    assert prior.hard_requirements['strong_identity'] is True

    transport = core.PrimaryTransport(rig.cfg)
    first = asyncio.run(transport.resolve(prior))
    assert first.route == 'api' and first.reason == 'bridge_capability_unsupported'
    current = adapter.request_for(app_request, transport, capabilities=asyncio.run(rig.client.capabilities()))
    assert current.digest == prior.digest
    recovered = asyncio.run(transport.resolve(current))
    assert recovered.route == 'api' and recovered.origin_key == first.origin_key
    assert rig.client.calls == 0
    asyncio.run(transport.close())


def test_partial_product_result_can_cancel_remaining_bridge_unit(rig):
    rig.client.state = 'running'
    rig.client.cancels = []
    async def cancel(task_id):
        rig.client.cancels.append(task_id)
    rig.client.cancel = cancel
    with pytest.raises(ProviderRuntimeError):
        rig.provider.generate(rig.request)
    service, record = _cancel_service(rig)
    record.generation_result = SimpleNamespace(existing_output='preserve this completed first output')
    result = asyncio.run(service.cancel_primary_bridge_generation('job_v3_prod', owner_user_id=7))
    assert result['status'] == 'cancel_requested'
    assert record.generation_result.existing_output == 'preserve this completed first output'
    assert rig.client.cancels == ['task_1']


def test_api_fallback_ambiguous_response_is_never_repeated(rig, monkeypatch):
    rig.client.error = BridgeError('queue_capacity', status=429)
    calls = []
    async def ambiguous(request):
        calls.append(request)
        raise TimeoutError('synthetic response lost after upstream acceptance')
    monkeypatch.setattr(rig.provider, '_app_provider', lambda name: SimpleNamespace(generate=ambiguous))
    first_failure_summary = None
    for _ in range(2):
        with pytest.raises(ProviderRuntimeError) as caught:
            rig.provider.generate(rig.request)
        assert caught.value.provider == 'api'
        assert caught.value.detail['failure_code'] == 'api_execution_unknown'
        assert 'automatic retry is disabled' in str(caught.value)
        if first_failure_summary is None:
            first_failure_summary = caught.value.provider_failure_retry
    assert len(calls) == 1 and rig.client.calls == 1
    summary = first_failure_summary
    failed_attempt = summary['attempts'][-1]
    assert failed_attempt['route'] == 'api'
    assert failed_attempt['route_reason'] == 'bridge_queue_capacity'
    assert failed_attempt['api_error_type'] == 'TimeoutError'
    assert 'synthetic response lost' not in repr(summary)

    from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
    public = V3ProductApiService._public_provider_failure_retry(summary)
    assert public['final_failure_code'] == 'api_execution_unknown'
    assert public['attempts'][-1]['route'] == 'api'
    assert public['attempts'][-1]['route_reason'] == 'bridge_queue_capacity'
    assert public['attempts'][-1]['api_error_type'] == 'TimeoutError'
    warnings = V3ProductApiService._public_job_warnings(
        ['OpenAI image reference generation failed'],
        {'provider_failure_retry': summary},
    )
    assert any('API image generation stopped' in item and 'bridge_queue_capacity' in item for item in warnings)
    assert any('API error type: TimeoutError' in item for item in warnings)
    assert any('automatic retry is disabled' in item for item in warnings)


def test_api_fallback_invalid_output_is_classified_as_api_and_not_repeated(rig, monkeypatch):
    rig.client.error = BridgeError('queue_capacity', status=429)
    calls = []

    async def invalid_output(request):
        calls.append(request)
        return SimpleNamespace(outputs=[{}])

    monkeypatch.setattr(rig.provider, '_app_provider', lambda name: SimpleNamespace(generate=invalid_output))
    first_summary = None
    for attempt in range(2):
        with pytest.raises(ProviderRuntimeError) as caught:
            rig.provider.generate(rig.request)
        assert caught.value.provider == 'api'
        assert caught.value.detail['transport_outcome']['request_state'] == 'accepted_unknown'
        if attempt == 0:
            assert caught.value.detail['failure_code'] == 'api_output_contract_invalid'
            assert 'API fallback returned an unusable image response' in str(caught.value)
            first_summary = caught.value.provider_failure_retry
        else:
            assert caught.value.detail['failure_code'] == 'api_execution_unknown'
            assert 'automatic retry is disabled' in str(caught.value)
    assert len(calls) == 1 and rig.client.calls == 1
    assert first_summary['final_failure_code'] == 'api_output_contract_invalid'
    assert first_summary['attempts'][-1]['route'] == 'api'

    public = V3ProductApiService._public_provider_failure_retry(first_summary)
    assert public['final_failure_code'] == 'api_output_contract_invalid'
    warning = V3ProductApiService._safe_generation_failure_message(
        provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
        provider_failure_retry=public,
        fallback_code='provider_failure',
    )
    assert 'unusable image response' in warning
    assert 'execution outcome is unknown' in warning
    assert 'automatic retry is disabled' in warning


def test_api_fallback_cancellation_is_terminal_and_not_replayed(rig, monkeypatch):
    rig.client.error = BridgeError('queue_capacity', status=429)
    calls = []

    async def canceled(request):
        calls.append(request)
        raise asyncio.CancelledError()

    monkeypatch.setattr(rig.provider, '_app_provider', lambda name: SimpleNamespace(generate=canceled))
    with pytest.raises(ProviderRuntimeError) as caught:
        rig.provider.generate(rig.request)
    assert caught.value.provider == 'api'
    assert caught.value.detail['failure_code'] == 'api_execution_unknown'
    assert caught.value.detail['api_error_type'] == 'CancelledError'
    assert caught.value.detail['transport_retry_terminal'] is True
    assert len(calls) == 1


def test_receipt_ack_loss_keeps_original_checkpoint_and_can_retry(rig):
    attempts = []
    async def ack(*args, **kwargs):
        attempts.append(kwargs)
        if len(attempts) == 1:
            raise BridgeError('bridge_unreachable')
        rig.client.acks.append(kwargs)
    rig.client.accept_registered_receipt = ack
    first = rig.provider.generate(rig.request)
    transport = core.PrimaryTransport(rig.cfg)
    with transport._db() as db:
        assert db.execute('SELECT image FROM units').fetchone()[0] is not None
    second = rig.provider.generate(rig.request)
    with transport._db() as db:
        assert db.execute('SELECT image FROM units').fetchone()[0] is None
    assert first.candidates[0].metadata['output_id'] == second.candidates[0].metadata['output_id']
    assert len(attempts) == 2 and len(rig.client.acks) == 1
    assert len(rig.store.list_outputs()) == 1 and rig.client.calls == 1 and not rig.api_calls


@pytest.mark.parametrize('disable_after_cancel', [False, True])
def test_actual_two_output_loop_cancel_between_units_blocks_second_admission(rig, monkeypatch, disable_after_cancel):
    from copy import deepcopy
    from pathlib import Path
    from alchemy_creative_agent_3_0.app.creative_core.central_brain import CentralCreativeBrain
    from alchemy_creative_agent_3_0.app.generation_router import GenerationRouter
    from alchemy_creative_agent_3_0.app.schemas import ProviderStrategy

    metadata = deepcopy(rig.request.metadata)
    metadata.update(requested_image_count=2, template_id='general_template', scenario_id='general_creative')
    canonical = metadata['llm_brain']['canonical_provider_prompts'][0]
    metadata['llm_brain']['canonical_provider_prompts'] = [
        {**canonical, 'output_index': 1, 'prompt': 'An abstract blue mountain landscape.'},
        {**canonical, 'output_index': 2, 'prompt': 'An abstract orange desert landscape.'}]
    original_update = rig.store.update_metadata
    cancellation_results = []
    def cancel_between_units(output_id, updates):
        record = original_update(output_id, updates)
        if updates.get('render_bridge_primary_checkpoint_complete') and not cancellation_results:
            service, job = _cancel_service(rig, job_id=record.job_id)
            # At this precise barrier first output is ACKed; no second unit
            # exists yet, and the whole product batch is still GENERATING.
            assert len(rig.client.acks) == 1
            transport = core.PrimaryTransport(rig.cfg)
            assert transport.bindings_for('v3', '7:project_7', record.job_id + ':', route='bridge', active_only=True) == []
            cancellation_results.append(asyncio.run(service.cancel_primary_bridge_generation(record.job_id, owner_user_id=7)))
            assert job.request.metadata['render_bridge_primary_cancel_requested'] is True
            if disable_after_cancel:
                monkeypatch.setattr(core.PrimarySettings, 'from_env', classmethod(lambda cls, product: replace(rig.cfg, enabled=False)))
        return record
    monkeypatch.setattr(rig.store, 'update_metadata', cancel_between_units)
    brain = CentralCreativeBrain(generation_router=GenerationRouter(provider=rig.provider))
    with pytest.raises(ProviderRuntimeError) as caught:
        brain.run_generation_loop('Create two independent abstract landscape images.',
            provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER, runtime_metadata=metadata)
    assert caught.value.detail['failure_code'] == 'bridge_batch_cancel_requested'
    assert cancellation_results[0]['status'] == 'cancel_requested'
    assert cancellation_results[0]['unit_states'] == []
    assert rig.client.calls == 1 and not rig.api_calls
    originals = rig.store.list_outputs()
    assert len(originals) == 1 and Path(originals[0].file_path).read_bytes() == rig.client.content


def test_batch_cancel_serializes_with_inflight_unit_admission(rig):
    rig.client.state = 'running'
    service, _ = _cancel_service(rig)
    entered = asyncio.Event()
    release = asyncio.Event()
    original_capabilities = rig.client.capabilities
    async def capabilities():
        entered.set()
        await release.wait()
        return await original_capabilities()
    rig.client.capabilities = capabilities
    rig.client.cancels = []
    async def cancel(task_id):
        rig.client.cancels.append(task_id)
    rig.client.cancel = cancel
    app_request, _, _ = rig.provider._build_app_request(rig.request)
    async def no_api(request):
        raise AssertionError('Cancellation must never create an API fallback')
    async def run():
        generation = asyncio.create_task(adapter.generate(app_request, no_api, rig.store))
        await entered.wait()
        cancellation = asyncio.create_task(service.cancel_primary_bridge_generation('job_v3_prod', owner_user_id=7))
        await asyncio.sleep(0.01)
        assert not cancellation.done()
        release.set()
        outcome, canceled = await asyncio.gather(generation, cancellation, return_exceptions=True)
        assert isinstance(outcome, ProviderRuntimeError)
        assert canceled['status'] == 'cancel_requested'
        following = app_request.model_copy(deep=True)
        following.prompt_plan.variables[adapter.CONTEXT]['unit_id'] += ':next'
        with pytest.raises(ProviderRuntimeError, match='existing image execution'):
            await adapter.generate(following, no_api, rig.store)
    asyncio.run(run())
    assert rig.client.calls == 1 and rig.client.cancels == ['task_1']


def test_new_native_normalization_does_not_mutate_api_fallback(rig):
    app_request = rig.provider._build_app_request(rig.request)[0]
    plan = app_request.prompt_plan
    plan.quality = 'high'
    plan.size = '1536x1024'
    plan.output_format = 'webp'
    plan.output_compression = 73
    plan.variables['provider_image_options'] = {'seed': 42, 'aspect_ratio': '3:2', 'input_fidelity': 'high'}
    before = app_request.model_dump(mode='json')
    rig.client.error = BridgeError('queue_capacity', status=429)
    seen = []
    async def legacy(actual):
        seen.append(actual)
        return ImageGenerationResult(provider='legacy', model='fixture', outputs=[{'b64_json': base64.b64encode(rig.client.content).decode()}])
    asyncio.run(adapter.generate(app_request, legacy, rig.store))
    assert seen == [app_request] and seen[0] is app_request
    assert app_request.model_dump(mode='json') == before
    assert rig.client.payload['parameters'] == {'codex_adapter': 'codex_cli_imagegen_v1'}


def test_store_busy_reference_staging_fails_v3_without_api_or_polling(rig, tmp_path):
    import time
    app_request = rig.provider._build_app_request(rig.request)[0]
    reference = tmp_path / 'reference.png'
    reference.write_bytes(rig.client.content)
    app_request.asset_plan = {'assets': [{'provider_input_mode': 'reference_image',
                                          'storage_path': str(reference)}]}
    rig.client.input_error = BridgeError('store_busy', status=503, retry_not_before=time.time() - 1)

    async def forbidden_api(_request):
        raise AssertionError('Persistent Bridge input contention must not call the API provider')

    with pytest.raises(ProviderRuntimeError, match='no remote image task was created') as caught:
        asyncio.run(adapter.generate(app_request, forbidden_api, rig.store))
    assert caught.value.detail['transport_outcome'] == {
        'request_state': 'not_submitted', 'retryability': 'safe_to_retry',
    }
    assert caught.value.detail[adapter.PROVENANCE]['reason'] == 'bridge_store_busy'
    assert len(rig.client.uploads) == 2
    assert rig.client.calls == 0 and rig.api_calls == []


@pytest.mark.parametrize('operation', ['mask', 'deterministic_postprocess', 'unknown_operation'])
def test_essential_and_unknown_operations_never_bridge(rig, tmp_path, operation):
    app_request = rig.provider._build_app_request(rig.request)[0]
    if operation == 'mask':
        path = tmp_path / 'mask.png'
        path.write_bytes(rig.client.content)
        app_request.prompt_plan.variables['identity_repair_mask_path'] = str(path)
    else:
        app_request.prompt_plan.variables['provider_image_options'][operation] = True
    async def legacy(actual):
        return ImageGenerationResult(provider='legacy', model='fixture', outputs=[{'b64_json': base64.b64encode(rig.client.content).decode()}])
    result = asyncio.run(adapter.generate(app_request, legacy, rig.store))
    assert result.provider == 'legacy' and rig.client.calls == 0


@pytest.mark.parametrize('route', ['bridge', 'api'])
@pytest.mark.parametrize('disabled', [False, True])
def test_legacy_journal_exact_digest_recovery_and_checkpoint(rig, monkeypatch, route, disabled):
    app_request = rig.provider._build_app_request(rig.request)[0]
    if route == 'api':
        app_request.prompt_plan.quality = 'high'
    legacy = adapter._source_request(app_request)
    transport = core.PrimaryTransport(rig.cfg)
    result = asyncio.run(transport.resolve(legacy))
    assert result.route == route
    assert adapter.request_for(app_request, transport).digest == legacy.digest
    if disabled:
        monkeypatch.setattr(core.PrimarySettings, 'from_env', classmethod(lambda cls, product: replace(rig.cfg, enabled=False)))
    calls = []
    async def api(actual):
        calls.append(actual)
        return ImageGenerationResult(provider='legacy', model='fixture', outputs=[{'b64_json': base64.b64encode(rig.client.content).decode()}])
    recovered = asyncio.run(adapter.generate(app_request, api, rig.store))
    assert recovered.provider == ('render_bridge' if route == 'bridge' else 'legacy')
    provenance = recovered.outputs[0][adapter.PROVENANCE]
    record = SimpleNamespace(metadata={adapter.PROVENANCE: provenance}, output_id='fixture-output')
    asyncio.run(adapter.checkpoint(app_request, record))
    assert adapter.request_for(app_request, transport).digest == legacy.digest
    assert len(calls) == (route == 'api')
    assert rig.client.calls == (route == 'bridge')
    assert bool(rig.client.acks) == (route == 'bridge')


@pytest.mark.parametrize('count', [5, 6])
def test_reference_limit_preserves_order_and_never_truncates(rig, tmp_path, count):
    app_request = rig.provider._build_app_request(rig.request)[0]
    paths = []
    for index in range(count):
        path = tmp_path / f'{index}.png'
        path.write_bytes(rig.client.content + bytes([index]))
        paths.append(path)
    app_request.asset_plan = {'assets': [
        {'provider_input_mode': 'reference_image', 'storage_path': str(path)} for path in paths]}
    native = adapter.request_for(app_request)
    assert [ref.content for ref in native.references] == [path.read_bytes() for path in paths]
    async def api(actual):
        return ImageGenerationResult(provider='legacy', model='fixture', outputs=[{'b64_json': base64.b64encode(rig.client.content).decode()}])
    result = asyncio.run(adapter.generate(app_request, api, rig.store))
    assert result.provider == ('render_bridge' if count == 5 else 'legacy')
    assert rig.client.calls == (count == 5)
    assert [item[1] for item in rig.client.uploads] == ([path.read_bytes() for path in paths] if count == 5 else [])


def test_legacy_cancel_keeps_frozen_payload_and_blocks_recovery(rig):
    app_request = rig.provider._build_app_request(rig.request)[0]
    legacy = adapter._source_request(app_request)
    rig.client.state = 'running'
    transport = core.PrimaryTransport(rig.cfg)
    asyncio.run(transport.resolve(legacy))
    original = dict(rig.client.payload)
    rig.client.cancel = lambda task_id: asyncio.sleep(0)
    service, _ = _cancel_service(rig)
    asyncio.run(service.cancel_primary_bridge_generation('job_v3_prod', owner_user_id=7))
    assert adapter.request_for(app_request, transport).digest == legacy.digest
    with pytest.raises(ProviderRuntimeError):
        rig.provider.generate(rig.request)
    assert rig.client.calls == 1 and not rig.api_calls
    assert rig.client.payload == original


@pytest.mark.parametrize('mode', ['postprocess_only', 'mask_edit_source'])
def test_asset_plan_essential_operations_do_not_become_reference_hints(rig, mode):
    app_request = rig.provider._build_app_request(rig.request)[0]
    app_request.asset_plan = {'assets': [{'provider_input_mode': mode}]}
    async def api(actual):
        return ImageGenerationResult(provider='legacy', model='fixture', outputs=[{'b64_json': base64.b64encode(rig.client.content).decode()}])
    result = asyncio.run(adapter.generate(app_request, api, rig.store))
    assert result.provider == 'legacy' and rig.client.calls == 0


def test_missing_reference_is_not_silently_removed(rig, monkeypatch):
    app_request = rig.provider._build_app_request(rig.request)[0]
    app_request.asset_plan = {'assets': [{'provider_input_mode': 'reference_image'}]}
    monkeypatch.setattr(adapter, 'reference_image_paths', lambda *args, **kwargs: [])
    with pytest.raises(ProviderRuntimeError) as caught:
        adapter.request_for(app_request)
    assert caught.value.detail['failure_code'] == 'bridge_reference_materialization_missing'
    assert not rig.api_calls and rig.client.calls == 0


def test_missing_native_contract_never_assumes_outer_legacy_contract(rig):
    original = rig.client.capabilities
    async def old_caps():
        caps = await original()
        del caps['profiles'][0]['parameter_contract']['codex_adapter']
        return caps
    rig.client.capabilities = old_caps
    result = rig.provider.generate(rig.request)
    assert result.candidates[0].provider == 'legacy'
    assert rig.client.calls == 0 and len(rig.api_calls) == 1


def test_optional_non_numeric_size_uses_native_defaults(rig):
    app_request = rig.provider._build_app_request(rig.request)[0]
    app_request.prompt_plan.size = 'auto'
    app_request.prompt_plan.variables['provider_image_options'] = {
        'seed': 42, 'aspect_ratio': '3:2', 'width': 1536, 'height': 1024,
        'input_fidelity': 'high', 'size': 'auto', 'output_compression': 80}
    async def no_api(actual):
        raise AssertionError('Optional controls must not force fallback')
    result = asyncio.run(adapter.generate(app_request, no_api, rig.store))
    assert result.provider == 'render_bridge'
    assert rig.client.payload['parameters'] == {'codex_adapter': 'codex_cli_imagegen_v1'}
    transport = core.PrimaryTransport(rig.cfg)
    assert adapter.request_for(app_request, transport).parameters == rig.client.payload['parameters']


def test_complete_native_checkpoint_retires_duplicate_and_replays(rig):
    import json
    from pathlib import Path
    first = rig.provider.generate(rig.request)
    record = rig.store.get_output(first.candidates[0].metadata['output_id'])
    transport = core.PrimaryTransport(rig.cfg)
    with transport._db() as db:
        row = db.execute('SELECT state,data,image FROM units').fetchone()
    assert row['state'] == 'acked' and row['image'] is None
    assert json.loads(row['data'])['cache_retired'] is True
    assert Path(record.file_path).read_bytes() == rig.client.content
    again = rig.provider.generate(rig.request)
    assert again.candidates[0].candidate_id == first.candidates[0].candidate_id
    assert rig.client.calls == 1 and not rig.api_calls


@pytest.mark.parametrize('damage', ['missing', 'corrupt', 'incomplete'])
def test_retired_checkpoint_invalid_native_original_never_regenerates(rig, damage):
    from pathlib import Path
    first = rig.provider.generate(rig.request)
    record = rig.store.get_output(first.candidates[0].metadata['output_id'])
    if damage == 'missing':
        Path(record.file_path).unlink()
    elif damage == 'corrupt':
        Path(record.file_path).write_bytes(b'not the original')
    else:
        rig.store.update_metadata(record.output_id, {'render_bridge_primary_checkpoint_complete': False})
    with pytest.raises(ProviderRuntimeError):
        rig.provider.generate(rig.request)
    assert rig.client.calls == 1 and not rig.api_calls


def test_retirement_refuses_incomplete_native_checkpoint(rig):
    app_request = rig.provider._build_app_request(rig.request)[0]
    async def no_api(request):
        raise AssertionError('no provider fallback')
    result = asyncio.run(adapter.generate(app_request, no_api, rig.store))
    provenance = result.outputs[0][adapter.PROVENANCE]
    record = rig.store.save_base64_output(job_id='job_v3_prod', candidate_id='candidate_test', asset_id='asset_test',
        provider='render_bridge', model='codex-image', encoded_image=result.outputs[0]['b64_json'],
        output_id=adapter.output_id(provenance), preserve_original_bytes=True,
        metadata={adapter.PROVENANCE: provenance, 'render_bridge_primary_checkpoint_complete': False})
    asyncio.run(adapter.checkpoint(app_request, record))
    assert asyncio.run(adapter.retire_checkpoint(app_request, record)) is False
    transport = core.PrimaryTransport(rig.cfg)
    with transport._db() as db:
        assert db.execute('SELECT image FROM units').fetchone()[0] is not None


@pytest.mark.parametrize('state', ['cancel_requested', 'canceled', 'failed', 'expired'])
def test_retired_native_checkpoint_cannot_override_terminal_or_cancel_state(rig, state):
    import json
    rig.provider.generate(rig.request)
    transport = core.PrimaryTransport(rig.cfg)
    with transport._db() as db:
        row = db.execute('SELECT key,data FROM units').fetchone()
        data = json.loads(row['data'])
        data['state'] = state
        if state == 'cancel_requested':
            data['cancel_requested'] = True
        db.execute('UPDATE units SET state=?,data=? WHERE key=?', (state, json.dumps(data), row['key']))
    app_request = rig.provider._build_app_request(rig.request)[0]
    async def no_api(request):
        raise AssertionError('terminal task cannot switch provider')
    with pytest.raises(ProviderRuntimeError):
        asyncio.run(adapter.generate(app_request, no_api, rig.store))
    with pytest.raises(ProviderRuntimeError):
        asyncio.run(adapter.assert_bridge_checkpoint_current(app_request, rig.store))
    assert rig.client.calls == 1 and not rig.api_calls


def test_ack_maintenance_retires_only_explicit_completed_checkpoint_without_resume(rig):
    original = rig.client.accept_registered_receipt
    async def lost(*args, **kwargs):
        raise BridgeError('bridge_unreachable')
    rig.client.accept_registered_receipt = lost
    first = rig.provider.generate(rig.request)
    record = rig.store.get_output(first.candidates[0].metadata['output_id'])
    assert record.metadata['render_bridge_primary_checkpoint_complete'] is True
    transport = core.PrimaryTransport(rig.cfg)
    with transport._db() as db:
        assert db.execute('SELECT image FROM units').fetchone()[0] is not None
    rig.client.accept_registered_receipt = original
    asyncio.run(transport.reconcile_pending())
    with transport._db() as db:
        row = db.execute('SELECT state,image FROM units').fetchone()
    assert row['state'] == 'acked' and row['image'] is None
    assert rig.client.calls == 1 and not rig.api_calls
    again = rig.provider.generate(rig.request)
    assert again.candidates[0].metadata['output_id'] == record.output_id
