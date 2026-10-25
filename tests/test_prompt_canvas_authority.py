from pathlib import Path

import pytest

from app.services.canvas_intent import resolve_prompt_canvas
from app.services.prompting import build_prompt_plan


@pytest.mark.parametrize('prompt,expected', [
    ('A 16:9 image with a bottle', '16:9'),
    ('Create a 16:9 image, not square', '16:9'),
    ('A cat, 16:9', '16:9'),
    ('Generate a cat at 1536x864', '1536x864'),
    ('not 16:9/use 2:3', '2:3'),
    ('reference image 16:9 output 1:1', '1:1'),
    ('A physical object 72x58mm', None),
    ('Output 2.35:1', '47:20'), ('Output 2.39:1', '239:100'),
    ('Output 1.5:1', '3:2'), ('Output -16:9', None),
    ('Time 16:09', None), ('Version 16:9', None),
    ('2026-10-25T16:09:00', None),
])
def test_numeric_mentions_bind_to_local_output_owner(prompt, expected):
    assert resolve_prompt_canvas(prompt) == expected


@pytest.mark.parametrize('adjective', ['landscape', 'beautiful wide landscape', 'product', 'cinematic portrait'])
@pytest.mark.parametrize('prefix', ['Reference', 'The source', 'Do not create a'])
def test_source_and_negation_scope_survives_adjectives(prefix, adjective):
    assert resolve_prompt_canvas(f'{prefix} {adjective} image is 16:9') is None
    assert resolve_prompt_canvas(f'{prefix} {adjective} image is 16:9; output 1:1') == '1:1'


@pytest.mark.parametrize('prompt', [
    'Generate an image with aspect ratio "16:9"', '输出比例为“16:9”',
    'Generate an image with canvas size "1536x864"', '画布尺寸为“1536x864”',
])
def test_labeled_quoted_canvas_beats_old_ui(prompt):
    assert build_prompt_plan(prompt=prompt, size='1024x1536').size == '1536x864'


@pytest.mark.parametrize('prompt', [
    'An image titled "16:9"', 'Draw visible text "1536x864"',
    '图片标题为“16:9”', '图中文字“1536x864”',
    'Source image aspect ratio "16:9"', 'Source canvas size "1536x864"',
    '参考画布尺寸为“1536x864”', 'Reference says "Output 16:9"',
])
def test_quoted_content_and_source_are_not_canvas(prompt):
    assert resolve_prompt_canvas(prompt) is None


@pytest.mark.parametrize('entry', ['revise_image_job', 'submit_revise_image_job'])
@pytest.mark.parametrize('old_prompt,feedback,expected', [
    ('Original portrait image', '改成16:9', '1536x864'),
    ('Original image 16:9', 'Change the lighting', '1024x1536'),
    ('Original image 16:9', 'Output 2:3', '1024x1536'),
    ('Original image', 'Do not create an image in 16:9', '1024x1536'),
    ('Original image', 'Reference landscape image is 16:9', '1024x1536'),
])
def test_revision_entry_uses_only_current_feedback_canvas(monkeypatch, entry, old_prompt, feedback, expected):
    import asyncio
    from types import SimpleNamespace
    from app.schemas import ImagePromptPlan, ReviseImageRequest
    from app.services import image_service
    base = ImagePromptPlan(main_subject=old_prompt, size='1024x1536', composition='Original portrait composition')
    before = base.model_dump()
    source = SimpleNamespace(id='source-job', session_id='session', provider='mock_image', model='mock', prompt_plan=base)
    output = SimpleNamespace(job_id=source.id)
    monkeypatch.setattr(image_service, 'resolve_revision_source', lambda *args: (source, output))
    monkeypatch.setattr(image_service, '_persist_restored_revision_source', lambda *args: None)
    monkeypatch.setattr(image_service.repository, 'save_job', lambda job: job)
    monkeypatch.setattr(image_service, '_emit_image_events', lambda *args: None)

    async def run(job, request, **kwargs):
        return job

    monkeypatch.setattr(image_service, '_run_image_request', run)
    result = asyncio.run(getattr(image_service, entry)(source.id, ReviseImageRequest(output_id='output', feedback=feedback)))
    result = result.job if entry == 'submit_revise_image_job' else result
    assert result.prompt_plan.size == expected
    if expected == '1536x864':
        assert '横版' in result.prompt_plan.composition
    assert base.model_dump() == before


@pytest.mark.parametrize('prompt', ['Create a 16:9 image', 'Create a 16:9 portrait of a person', 'Output width1536 height864'])
def test_prompt_canvas_beats_stale_ui(prompt):
    assert build_prompt_plan(prompt=prompt, size='1024x1536').size == '1536x864'


@pytest.mark.parametrize('prompt', [
    'Do not use a 16:9 image', 'Reference image is 16:9',
    'A box with width1536 height864', 'A bottle size 1536x864 mm',
    'A source says "output 16:9"', 'Output 16:9 or 2:3',
])
def test_non_authoritative_canvas_does_not_override_ui(prompt):
    assert resolve_prompt_canvas(prompt) is None
    assert build_prompt_plan(prompt=prompt, size='1024x1536').size == '1024x1536'


def test_pixels_are_not_rescaled_or_approximated():
    assert build_prompt_plan(prompt='Output image 1920x1080 pixels').size == '1920x1080'


def test_independent_product_parsers_stay_identical():
    root = Path(__file__).resolve().parents[1]
    assert (root / 'src_skeleton/app/services/canvas_intent.py').read_bytes() == (
        root / 'custom_media_agent_2_0/app/services/canvas_intent.py').read_bytes()


def test_lab_mapper_preserves_ratio_and_prompt_has_final_authority():
    from app.services.alchemy_lab import _size_from_aspect_ratio
    assert _size_from_aspect_ratio('16:9') == '1536x864'
    assert _size_from_aspect_ratio('9:16') == '864x1536'
    assert build_prompt_plan(prompt='Create a 16:9 image', size=_size_from_aspect_ratio('portrait')).size == '1536x864'


@pytest.mark.parametrize('model,size,expected', [
    ('gpt-image-2', '1536x864', '1536x864'),
    ('gpt-image-2', '864x1536', '864x1536'),
    ('gpt-image-2', '1920x1080', 'auto'),
    ('gpt-image-2', '4000x4000', 'auto'),
    ('gpt-image-1', '1536x864', 'auto'),
    ('gpt-image-1.5', '1024x1536', '1024x1536'),
])
def test_shared_api_canvas_adaptation_preserves_original_plan(monkeypatch, model, size, expected):
    from app.config import settings
    from app.providers.openai_image import OpenAIGPTImageProvider
    monkeypatch.setattr(settings, 'openai_base_url', None)
    monkeypatch.setattr(settings, 'openai_image_transport_profile', 'standard')
    plan = build_prompt_plan(prompt=f'Output image {size} pixels', size='1024x1536')
    before = plan.model_dump()
    assert OpenAIGPTImageProvider(model=model)._image_kwargs(plan)['size'] == expected
    assert plan.model_dump() == before


def test_shared_api_retains_malformed_size_guard(monkeypatch):
    from app.config import settings
    from app.providers.openai_image import OpenAIGPTImageProvider
    from app.providers.base import ProviderCapabilityMismatchError
    monkeypatch.setattr(settings, 'openai_image_transport_profile', 'standard')
    plan = build_prompt_plan(prompt='Create an image', size='invalid')
    with pytest.raises(ProviderCapabilityMismatchError):
        OpenAIGPTImageProvider(model='gpt-image-2')._image_kwargs(plan)


def test_unsupported_ratio_defaults_without_square_prompt_hint(monkeypatch):
    from app.config import settings
    from app.providers.openai_image import OpenAIGPTImageProvider
    monkeypatch.setattr(settings, 'openai_base_url', None)
    monkeypatch.setattr(settings, 'openai_image_transport_profile', 'standard')
    plan = build_prompt_plan(prompt='Output image ratio 4:1', size='1024x1536')
    provider = OpenAIGPTImageProvider(model='gpt-image-2')
    assert provider._image_kwargs(plan)['size'] == 'auto'
    assert '4:1' in provider._render_prompt(plan)
    assert '方图' not in plan.composition
    ambiguous = build_prompt_plan(prompt='Output ratio 4:1 or 16:9')
    assert '方图' not in ambiguous.composition
