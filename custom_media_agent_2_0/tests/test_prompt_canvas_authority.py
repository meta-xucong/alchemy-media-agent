import pytest
from pathlib import Path

from app.services.prompting import compose_prompt_plan


def plan(prompt, output=None):
    output = output or {'size': '1024x1536', 'aspect_ratio': '2:3', 'width': 1024, 'height': 1536}
    return compose_prompt_plan(mode='smart_enhance', user_prompt=prompt, cases=[], output=output, requested_output=output)


@pytest.mark.parametrize('prompt', ['Create a 16:9 image', 'Create a 16:9 portrait of a person', 'Output width1536 height864'])
def test_prompt_canvas_overrides_all_old_dimensions(prompt):
    result = plan(prompt)
    assert result.provider_parameters['size'] == '1536x864'
    assert not {'aspect_ratio', 'width', 'height'} & result.provider_parameters.keys()
    assert result.user_variables['aspect_lock']['aspect_ratio'] == '16:9'
    assert 'Required output aspect ratio: 2:3.' not in result.prompt
    assert prompt in result.prompt


@pytest.mark.parametrize('prompt', [
    'Do not use a 16:9 image', 'Reference image is 16:9',
    'A box with width1536 height864', 'A bottle size 1536x864 mm',
    'A source says "output 16:9"', 'Output 16:9 or 2:3',
    'Create a cinematic food poster',
])
def test_no_explicit_canvas_keeps_structured_control(prompt):
    assert plan(prompt, {'size': '1024x1536'}).provider_parameters['size'] == '1024x1536'


def test_unsupported_pixel_size_remains_original_for_provider_negotiation():
    result = plan('Output image 1920x1080 pixels')
    assert result.provider_parameters['size'] == '1920x1080'
    assert result.user_variables['aspect_lock']['aspect_ratio'] == '16:9'


def test_unsupported_ratio_keeps_requested_hint_not_a_default_ratio():
    from app.providers.images.openai_gpt_image_2 import _openai_image_kwargs
    result = plan('Output image ratio 4:1')
    assert 'size' not in _openai_image_kwargs(result)
    assert 'Required output aspect ratio: 4:1.' in result.prompt
    assert 'Required output aspect ratio: 2:3.' not in result.prompt


def test_brain_contract_agrees_with_prompt_canvas_authority():
    text = (Path(__file__).resolve().parents[1] / 'app/services/claude_orchestrator.py').read_text(encoding='utf-8')
    assert '当前用户提示词明确要求的输出画布尺寸/比例优先于 context.request.output' in text
    assert '若含非 auto/default 的 size/aspect_ratio，即手动画幅锁' not in text


@pytest.mark.parametrize('prompt', [
    'Generate an image with aspect ratio "16:9"', '输出比例为“16:9”',
    'Generate an image with canvas size "1536x864"', '画布尺寸为“1536x864”',
])
def test_labeled_quoted_canvas_actual_composition(prompt):
    result = plan(prompt)
    assert result.provider_parameters['size'] == '1536x864'
    assert 'aspect_ratio' not in result.provider_parameters
    assert 'Required output aspect ratio: 2:3.' not in result.prompt
    assert prompt in result.prompt


@pytest.mark.parametrize('prompt', [
    'An image titled "16:9"', 'Draw visible text "1536x864"',
    '图片标题为“16:9”', '图中文字“1536x864”',
    'Source image aspect ratio "16:9"', 'Source canvas size "1536x864"',
    '参考画布尺寸为“1536x864”', 'Reference says "Output 16:9"',
])
def test_quoted_non_canvas_content_keeps_existing_control(prompt):
    assert plan(prompt, {'size': '1024x1536'}).provider_parameters['size'] == '1024x1536'


def test_old_canvas_policy_cannot_hit_new_exact_or_semantic_cache(monkeypatch):
    from app.services import claude_orchestrator as brain
    from app.schemas import CreateCreativeRunRequest, CaseRetrievalPlan
    from app.config import settings
    request = CreateCreativeRunRequest(user_prompt='Generate a 16:9 image', output={'size': '1024x1536'})
    args = dict(request=request, fallback_mode='smart_enhance', candidate_cases=[])
    key_args = dict(**args, fallback_retrieval_plan=CaseRetrievalPlan(query_text='image'))
    new_schema = brain._CLAUDE_DECISION_CACHE_SCHEMA
    assert new_schema == 'claude_decision_v13_prompt_canvas_authority'
    monkeypatch.setattr(brain, '_CLAUDE_DECISION_CACHE_SCHEMA', 'claude_decision_v12_template_visual_grammar')
    old_key, old_metadata = brain._cache_key(**key_args), brain._cache_metadata(**args)
    monkeypatch.setattr(brain, '_CLAUDE_DECISION_CACHE_SCHEMA', new_schema)
    new_key, new_metadata = brain._cache_key(**key_args), brain._cache_metadata(**args)
    assert old_key != new_key
    old_entry = {'metadata': old_metadata, 'decision': {'final_prompt': 'Old 2:3 instruction'}}
    monkeypatch.setattr(brain, '_read_cache_store', lambda: {old_key: old_entry})
    from dataclasses import replace
    monkeypatch.setattr(brain, 'settings', replace(settings, claude_orchestrator_cache_enabled=True, claude_orchestrator_semantic_cache_enabled=True))
    assert brain._read_cached_decision(new_key) is None
    assert brain._read_semantic_cached_decision(new_metadata) is None
    assert old_entry['decision']['final_prompt'] == 'Old 2:3 instruction'
