"""Target revisions separate semantic edits from sibling-job bookkeeping."""
import copy
from dataclasses import asdict

import pytest

from test_render_bridge_native_planning import (
    planning_fixture, native_fixture, target_fixture, _create, _new_target, _upload_reference,
)
from test_render_bridge_native_registration import _receipt, _register
from alchemy_creative_agent_3_0.app.product_api.render_bridge_facade import BridgeNativeFacadeError, _digest
from alchemy_creative_agent_3_0.app.product_api.contracts import CreateCreativeJobRequest


def test_sibling_plan_preserves_freeze_receipt_and_interrupted_review(planning_fixture, monkeypatch):
    f = planning_fixture
    refs = [_upload_reference(f, color=color) for color in ('red', 'blue')]
    a = _new_target(f, _create(f, plan_key='first', uploaded_asset_ids=[r.asset_id for r in refs]))
    frozen = f.gateway.prepare(7, a.target)
    before = copy.deepcopy(f.jobs.get(a.target.job_id))
    assert _create(f, user_input='A green vase.', plan_key='second')['status'] == 'planned'
    assert f.jobs.get(a.target.job_id) == before
    assert f.gateway.prepare(7, a.target) == frozen
    receipt = _receipt(a, frozen)
    review = f.service._resume_finalizing_generation_review
    monkeypatch.setattr(f.service, '_resume_finalizing_generation_review', lambda *a, **kw: (_ for _ in ()).throw(RuntimeError('interrupted')))
    assert _register(a, **receipt)['status'] == 'import_unknown'
    assert _create(f, user_input='A yellow vase.', plan_key='third')['status'] == 'planned'
    monkeypatch.setattr(f.service, '_resume_finalizing_generation_review', review)
    outcome = f.gateway.registration_status(7, a.target, import_key=receipt['import_key'])
    assert outcome['status'] == 'registered'
    assert outcome['review_pending'] is False
    assert _register(a, **receipt) == outcome
    assert len(f.outputs.list_by_job(a.target.job_id)) == 1
    assert len(f.reviews) == 1
    assert f.review_only_calls == [True]
    assert f.debit.call_count == f.usage.call_count == 0
    assert len(f.planning_calls) == 3


@pytest.mark.parametrize('change', ['goal', 'mode', 'reference', 'owner', 'status', 'membership', 'cancel'])
def test_semantic_change_still_blocks_original_receipt(planning_fixture, change):
    f = planning_fixture
    a = _new_target(f, _create(f, plan_key='semantic-first'))
    receipt = _receipt(a)
    project = f.projects.get_project(a.target.project_id)
    if change == 'goal':
        project.user_goal = 'A genuinely changed project goal'
    elif change == 'mode':
        project.metadata['project_mode'] = 'professional'
    elif change == 'reference':
        _upload_reference(f, color='green')
    elif change == 'owner':
        project.metadata['veyra_user_id'] = 8
    elif change == 'status':
        project.status = 'archived'
    elif change == 'membership':
        project.job_ids.remove(a.target.job_id)
    else:
        record = f.jobs.get(a.target.job_id)
        record.request.metadata['cancel_requested'] = True
        f.jobs.save(record)
    f.projects.save_project(project)
    with pytest.raises(BridgeNativeFacadeError):
        _register(a, **receipt)
    assert not f.outputs.list_by_job(a.target.job_id)


def test_legacy_revision_and_pending_receipt_identity_stay_exact(native_fixture):
    f = native_fixture
    record = f.jobs.get(f.target.job_id)
    project = f.projects.get_project(f.target.project_id)
    assert 'render_bridge_project_binding' not in record.request.metadata
    expected = _digest({'target': asdict(f.target), 'actor': 7,
        'request': record.request.model_dump(mode='json'),
        'planning_result': record.planning_result.model_dump(mode='json'),
        'project_updated_at': project.updated_at, 'project_status': str(project.status),
        'project_owner': project.metadata['veyra_user_id'], 'project_job_ids': list(project.job_ids)})
    frozen = f.gateway.prepare(7, f.target)
    assert frozen['target_revision'] == expected
    receipt = _receipt(f, frozen)
    assert _register(f, **receipt)['status'] == 'registered'
    assert _register(f, **receipt)['status'] == 'registered'
    assert len(f.outputs.list_by_job(f.target.job_id)) == 1


def test_public_metadata_cannot_choose_revision_policy(planning_fixture):
    f = planning_fixture
    with pytest.raises(ValueError, match='server_owned|untrusted'):
        f.service.create_creative_job(CreateCreativeJobRequest(user_input='A vase.', metadata={
            'project_id': f.project.project_id, 'veyra_user_id': 7,
            'render_bridge_project_binding': 'semantic_v2'}))
    assert not f.planning_calls


def test_sibling_plan_preserves_cloud_output_checkpoint_recovery(planning_fixture, monkeypatch):
    import base64
    from types import SimpleNamespace
    from unittest.mock import Mock
    from test_render_bridge_native_registration import _png_bytes
    from alchemy_creative_agent_3_0.app.generation_router.providers import ProductionImageGenerationProvider
    f = planning_fixture
    a = _new_target(f, _create(f, plan_key='cloud-first'))
    frozen = f.gateway.prepare(7, a.target)
    monkeypatch.setattr(ProductionImageGenerationProvider, '_select_provider', lambda self, refs: 'openai_gpt_image')
    transport = Mock(return_value=SimpleNamespace(provider='openai_gpt_image', model='configured-image-model',
        outputs=[{'b64_json': base64.b64encode(_png_bytes()).decode(), 'mime_type': 'image/png',
                  'format': 'png', 'width': 1024, 'height': 1024}], raw_response_summary={}))
    monkeypatch.setattr(ProductionImageGenerationProvider, '_run_app_provider_with_timeout_retry', transport)
    assert _create(f, user_input='A green vase.', plan_key='cloud-second')['status'] == 'planned'
    args = {'frozen_request_id': frozen['frozen_request_id'], 'execution_key': 'cloud-sibling'}
    assert f.gateway.cloud_admission(7, a.target, frozen_request_id=args['frozen_request_id'])['status'] == 'ready'
    projection = f.service._project_frozen_provider_candidate
    monkeypatch.setattr(f.service, '_project_frozen_provider_candidate', Mock(side_effect=RuntimeError('checkpoint interrupted')))
    assert f.gateway.cloud_execute(7, a.target, **args)['status'] == 'cloud_unknown'
    assert _create(f, user_input='A yellow vase.', plan_key='cloud-third')['status'] == 'planned'
    monkeypatch.setattr(f.service, '_project_frozen_provider_candidate', projection)
    assert f.gateway.cloud_status(7, a.target, **args)['status'] == 'registered'
    assert f.gateway.cloud_execute(7, a.target, **args)['status'] == 'registered'
    assert transport.call_count == 1
    assert len(f.outputs.list_by_job(a.target.job_id)) == 1
    assert f.review_only_calls == [True]


@pytest.mark.parametrize('state', ['queued', 'running', 'plan_unknown', 'import_unknown', 'review_pending', 'registered', 'registered_blocked', 'registered_pending'])
def test_legacy_pending_blocks_new_intent_but_preserves_exact_replay(tmp_path, state):
    import asyncio
    from test_render_bridge_native_coordinator import make_service, request
    from app.integrations.render_bridge.client import BridgeError
    async def case():
        svc, gateway, bridge = make_service(tmp_path)
        try:
            old = await svc.create('101', request())
            outcomes = {'registered': {'review_status': 'finalizing'},
                        'registered_blocked': {'review_status': 'blocked'},
                        'registered_pending': {'review_pending': True}}
            legacy = await svc.local(svc.store.patch, old['id'], {
                'project_binding_version': None,
                'state': 'registered' if state.startswith('registered') else state,
                'native_outcome': outcomes.get(state)})
            assert await svc.create('101', request()) == legacy
            with pytest.raises(BridgeError) as error:
                await svc.create('101', request(client_request_id='another', user_input='Different requested image'))
            assert error.value.code == 'legacy_native_project_tasks_pending'
            assert error.value.status == 409
            assert gateway.create_calls == 0 and not bridge.calls
            assert len(await svc.local(svc.store.list, '101', 'project_1')) == 1
            await svc.local(svc.store.patch, old['id'], {'state': 'registered', 'native_outcome': {'review_pending': False}})
            new = await svc.create('101', request(client_request_id='another', user_input='Different requested image'))
            assert new['project_binding_version'] == 'semantic_v2'
        finally:
            await svc.close()
    asyncio.run(case())


def test_v2_new_intents_are_not_single_inflight_limited(tmp_path):
    import asyncio
    from test_render_bridge_native_coordinator import make_service, request
    async def case():
        svc, gateway, bridge = make_service(tmp_path)
        try:
            records = await asyncio.gather(*(svc.create('101', request(client_request_id=f'v2-{i}')) for i in range(3)))
            assert len({r['id'] for r in records}) == 3
            assert all(r['project_binding_version'] == 'semantic_v2' for r in records)
        finally:
            await svc.close()
    asyncio.run(case())
