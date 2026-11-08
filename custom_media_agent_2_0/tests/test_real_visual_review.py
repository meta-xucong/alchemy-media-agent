from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from PIL import Image

from app.config import settings
from app.repositories.memory import utc_now
from app.schemas import ImageJob, ImageOutput, ImagePromptPlan
from app.services import visual_review_agent as vision
from app.services.output_review import review_image_job


@pytest.fixture
def job(tmp_path, monkeypatch):
    monkeypatch.setattr(vision, 'settings', replace(settings, output_review_agent_enabled=True,
        llm_gateway_api_key='offline-key', llm_gateway_base_url='https://vision.invalid/v1',
        output_review_agent_model='gpt-test-vision', storage_dir=tmp_path))
    path = tmp_path / 'output.png'
    Image.new('RGB', (80, 120), 'blue').save(path)
    now = utc_now()
    output = ImageOutput(output_id='out_review', job_id='job_review', url='/api/v2/outputs/out_review/download',
                         metadata={'live': True, 'storage_path': str(path)}, created_at=now)
    return ImageJob(job_id='job_review', run_id='run_review', status='completed', provider_id='render_bridge',
                    model='image', prompt_plan=ImagePromptPlan(plan_id='plan', mode='smart_enhance',
                    prompt='A blue product photograph', negative_prompt='watermark'), outputs=[output],
                    created_at=now, updated_at=now)


def install_response(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(vision, '_http_client', lambda timeout: original(transport=httpx.MockTransport(handler), timeout=timeout))


def reply(verdict=None):
    return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(
        verdict or {'decision': 'pass', 'references_match': True, 'notes': ['Visible result meets the request.'], 'issues': []})}}]})


def test_real_pixels_one_request_reused_and_bytes_unchanged(job, monkeypatch):
    original = Path(job.outputs[0].metadata['storage_path']).read_bytes()
    job.prompt_plan.user_variables['generation_prompt'] = 'Final compiled blue product with preserved label'
    requests = []
    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        content = payload['messages'][0]['content']
        assert content[1]['image_url']['url'].startswith('data:image/png;base64,')
        assert payload['response_format'] == {'type': 'json_object'}
        assert 'watermark' in content[0]['text']
        assert job.prompt_plan.user_variables['generation_prompt'] in content[0]['text']
        return reply()
    install_response(monkeypatch, handler)
    pending = review_image_job(job)
    assert pending.outputs[0].review.analysis_mode == 'vision_pending'
    reviewed = asyncio.run(vision.review_generated_job(pending))
    assert reviewed.outputs[0].review.analysis_mode == 'vision_model'
    assert reviewed.outputs[0].review.decision == 'pass'
    assert reviewed.outputs[0].review.model == 'gpt-test-vision'
    assert reviewed.outputs[0].review.elapsed_ms >= 0
    assert asyncio.run(vision.review_generated_job(reviewed)) == reviewed
    assert review_image_job(reviewed).outputs[0].review == reviewed.outputs[0].review
    assert len(requests) == 1
    assert reviewed.outputs[0].url == job.outputs[0].url
    assert Path(job.outputs[0].metadata['storage_path']).read_bytes() == original


@pytest.mark.parametrize('failure', ['timeout', 'invalid_json', 'invalid_shape', 'refusal'])
def test_unavailable_never_hides_output_or_retries(job, monkeypatch, failure):
    calls = []
    def handler(request):
        calls.append(request)
        if failure == 'timeout':
            raise httpx.ReadTimeout('offline timeout', request=request)
        if failure == 'refusal':
            return httpx.Response(200, json={'choices': [{'message': {'refusal': 'no'}, 'finish_reason': 'stop'}]})
        if failure == 'invalid_shape':
            return httpx.Response(200, json={'choices': [None]})
        return httpx.Response(200, json={'choices': [{'message': {'content': '{}'}, 'finish_reason': 'stop'}]})
    install_response(monkeypatch, handler)
    result = asyncio.run(vision.review_generated_job(review_image_job(job)))
    assert result.status == 'completed'
    assert result.outputs[0].url == job.outputs[0].url
    assert result.outputs[0].review.analysis_mode == 'vision_unavailable'
    assert result.outputs[0].review.decision == 'needs_review'
    assert len(calls) == 1


def test_missing_reference_cannot_be_reported_visually_verified(job, monkeypatch):
    job.prompt_plan.user_variables['provider_input_plan'] = {'requires_image_reference': True, 'reference_image_count': 1}
    install_response(monkeypatch, lambda request: pytest.fail('missing required image must not produce a partial review'))
    result = asyncio.run(vision.review_generated_job(review_image_job(job)))
    assert result.outputs[0].review.decision == 'retry_recommended'
    assert result.outputs[0].review.analysis_mode == 'vision_unavailable'
    assert 'reference_adherence_unverified' in result.outputs[0].review.detected_risks


def test_reference_pixels_and_ownership(job, monkeypatch, tmp_path):
    from types import SimpleNamespace
    from app.services import uploaded_assets
    path = tmp_path / 'reference.png'
    Image.new('RGB', (1400, 900), 'green').save(path)
    job.prompt_plan.user_variables['provider_input_plan'] = {'requires_image_reference': True, 'reference_image_count': 1}
    job.outputs[0].metadata['input_images'] = [{'asset_id': 'asset_ref', 'role': 'product', 'reference_mode': 'preserve'}]
    monkeypatch.setattr(uploaded_assets, 'get_uploaded_asset', lambda identity: SimpleNamespace(asset_id=identity, veyra_user_id=job.veyra_user_id))
    monkeypatch.setattr(uploaded_assets, 'uploaded_asset_path', lambda identity: path)
    def handler(request):
        content = json.loads(request.content)['messages'][0]['content']
        assert len([x for x in content if x['type'] == 'image_url']) == 2
        assert content[-1]['image_url']['url'].startswith('data:image/jpeg;base64,')
        return reply()
    install_response(monkeypatch, handler)
    result = asyncio.run(vision.review_generated_job(review_image_job(job)))
    assert result.outputs[0].review.decision == 'pass'
    assert 'reference_adherence_unverified' not in result.outputs[0].review.detected_risks
    monkeypatch.setattr(uploaded_assets, 'get_uploaded_asset', lambda identity: SimpleNamespace(asset_id=identity, veyra_user_id=999))
    denied = asyncio.run(vision.review_generated_job(review_image_job(job)))
    assert denied.outputs[0].review.analysis_mode == 'vision_unavailable'


def test_source_evidence_guard_survives_model_pass(job, monkeypatch):
    job.prompt_plan.user_variables['reference_delivery'] = {'acceptance': {
        'requires_pixel_review': True, 'requires_source_text_evidence': True, 'source_text_evidence_ready': False}}
    install_response(monkeypatch, lambda request: reply())
    result = asyncio.run(vision.review_generated_job(review_image_job(job)))
    assert result.outputs[0].review.analysis_mode == 'vision_model'
    assert result.outputs[0].review.decision == 'needs_review'
    assert 'source_text_evidence_missing' in result.outputs[0].review.detected_risks


@pytest.mark.parametrize('verified,ready,expected', [(['price','date'],True,'pass'), (['price'],True,'needs_review'),
    (['price','invented'],True,'needs_review'), (['price','date'],False,'needs_review')])
def test_only_complete_explicit_source_evidence_clears_text_guard(job, monkeypatch, verified, ready, expected):
    job.prompt_plan.user_variables['reference_delivery'] = {'acceptance': {
        'requires_pixel_review': True, 'requires_source_text_evidence': True, 'source_text_evidence_ready': ready,
        'required_field_ids': ['price', 'date']}, 'source_evidence': [
        {'field_id':'price','value':'12','required':True}, {'field_id':'date','value':'Monday','required':True}]}
    install_response(monkeypatch, lambda request: reply({'decision':'pass','references_match':True,'notes':[], 'issues':[],
                                                       'verified_source_fields':verified}))
    result = asyncio.run(vision.review_generated_job(review_image_job(job)))
    assert result.outputs[0].review.decision == expected
    assert 'invented' not in result.outputs[0].review.verified_source_fields


@pytest.mark.parametrize('lose_claim', [False, True])
def test_pending_projection_lock_free_review_and_checkpoint_recovery(job, monkeypatch, tmp_path, lose_claim):
    from app.repositories import repository
    from app.schemas import CreativeRun
    from app.services import generation, task_queue, image_history
    monkeypatch.setattr(image_history, 'settings', replace(settings, image_history_path=tmp_path / 'history/image_history.jsonl'))
    monkeypatch.setattr(task_queue, 'settings', replace(settings, task_queue_db_path=tmp_path / 'queue.sqlite3'))
    task_queue.initialize_task_queue()
    repository.reset()
    pending = review_image_job(job)
    running = job.model_copy(update={'status': 'running', 'outputs': []})
    run = CreativeRun(run_id=job.run_id, status='generating', mode='smart_enhance', intent_summary='test',
                      trace_id='trace', generation_jobs=[running], created_at=utc_now(), updated_at=utc_now())
    task_queue.enqueue_creative_task(kind='creative_run', request_payload={'user_prompt': 'test'}, queued_run=run)
    claim = task_queue.claim_next_task('review-worker')
    calls = []
    def handler(request):
        calls.append(request)
        # This write would fail if the HTTP callback still held BEGIN IMMEDIATE.
        with task_queue._connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            connection.rollback()
        snapshot = task_queue.get_run_snapshot(job.run_id)
        assert snapshot.status == 'reviewing'
        assert snapshot.generation_jobs[0].outputs[0].url == job.outputs[0].url
        if lose_claim:
            with task_queue._connect() as connection:
                connection.execute("UPDATE v2_tasks SET claim_token = 'replacement' WHERE run_id = ?", (job.run_id,))
        return reply()
    install_response(monkeypatch, handler)
    with task_queue.claimed_task(claim):
        task_queue.persist_claimed_operation(lambda: repository.save_image_job(pending), on_persisted=task_queue.checkpoint_completed_generation)
        checkpoint = task_queue.get_success_checkpoint()
        restored = task_queue.restore_success_checkpoint(checkpoint)
        if lose_claim:
            with pytest.raises(task_queue.StaleTaskClaim):
                asyncio.run(generation.finish_run_reviews(restored))
            assert repository.get_image_job(job.job_id).outputs[0].review.analysis_mode == 'vision_pending'
            assert len(calls) == 1
            return
        finished = asyncio.run(generation.finish_run_reviews(restored))
        assert finished.generation_jobs[0].outputs[0].review.analysis_mode == 'vision_model'
        checkpoint = task_queue.get_success_checkpoint()
        assert checkpoint.generation_jobs[0].outputs[0].review.analysis_mode == 'vision_model'
        again = asyncio.run(generation.finish_run_reviews(task_queue.restore_success_checkpoint(checkpoint)))
        assert again.generation_jobs[0].outputs[0].review == finished.generation_jobs[0].outputs[0].review
        assert task_queue.get_run_snapshot(job.run_id).status == 'completed'
    assert len(calls) == 1


def test_batch_reviews_overlap_with_limit_two_and_preserve_order(job, monkeypatch):
    job = job.model_copy(update={'outputs': [job.outputs[0].model_copy(update={'output_id': f'out_{n}'}) for n in range(3)]})
    active = peak = calls = 0
    async def handler(request):
        nonlocal active, peak, calls
        active += 1
        calls += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return reply()
    install_response(monkeypatch, handler)
    result = asyncio.run(vision.review_generated_job(review_image_job(job)))
    assert peak == 2 and calls == 3
    assert [x.output_id for x in result.outputs] == ['out_0', 'out_1', 'out_2']
    assert all(x.review.analysis_mode == 'vision_model' for x in result.outputs)


def test_anthropic_route_sends_actual_images_once(job, monkeypatch):
    monkeypatch.setattr(vision, 'settings', replace(vision.settings, output_review_agent_model='claude-test'))
    def handler(request):
        assert request.url.path == '/v1/messages'
        content = json.loads(request.content)['messages'][0]['content']
        assert content[1]['source']['media_type'] == 'image/png'
        return httpx.Response(200, json={'stop_reason':'end_turn','content':[{'type':'text','text':json.dumps({
            'decision':'pass','references_match':True,'notes':[],'issues':[]})}]})
    install_response(monkeypatch, handler)
    assert asyncio.run(vision.review_generated_job(review_image_job(job))).outputs[0].review.analysis_mode == 'vision_model'
