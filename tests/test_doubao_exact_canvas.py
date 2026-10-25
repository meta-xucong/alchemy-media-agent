from types import SimpleNamespace
import asyncio

import pytest

from app.config import settings
from app.providers.doubao_image import _size, _outputs_from_response, _canvas_capabilities
from app.services.canvas_intent import exact_canvas_size


@pytest.fixture(autouse=True)
def seedream4(monkeypatch):
    monkeypatch.setattr(settings, 'doubao_image_model', 'doubao-seedream-4-0-250828')


@pytest.mark.parametrize('value,expected', [
    ('16:9', '1536x864'), ('9:16', '864x1536'), ('4:1', '2048x512'),
    ('1920x1080', '1920x1080'), ('1536x384', None),
    ('4096x4096', '4096x4096'), ('8192x1024', '8192x1024'),
    ('4097x4097', None), ('20000x1000', None), ('1000x1000', '1000x1000'),
    ('auto', None), ('default', None), ('4K', '4K'), ('2k', '2K'),
    ('invalid', None), ('-1024x1024', None), ('0x0', None),
])
def test_seedream4_exact_or_native(value, expected):
    assert _size(value) == expected


def test_unknown_model_does_not_inherit_custom_contract(monkeypatch):
    monkeypatch.setattr(settings, 'doubao_image_model', 'unknown-older-model')
    assert _size('16:9') is None
    assert _size('1024x1536') == '1024x1536'
    assert 'custom_size' not in _canvas_capabilities()


def test_ratio_resolution_selection_never_rescales_explicit_pixels():
    assert exact_canvas_size('4:1') == '2048x512'
    assert exact_canvas_size('1536x384') == '1536x384'


def test_native_default_does_not_label_output_with_unsupported_request_dimensions():
    plan = SimpleNamespace(size='1536x384', output_format='png')
    outputs = _outputs_from_response({'data': [{'b64_json': 'aGVsbG8='}]}, plan, index=0)
    assert outputs[0]['width'] is None and outputs[0]['height'] is None
    assert plan.size == '1536x384'
    outputs = _outputs_from_response({'data': [{'b64_json': 'aGVsbG8=', 'size': '2048x2048'}]}, plan, index=0)
    assert outputs[0]['width'] == 2048


@pytest.mark.parametrize('size,expected', [('1920x1080', '1920x1080'), ('1536x384', None)])
def test_generation_payload_keeps_prompt_and_omits_unsupported_size(monkeypatch, size, expected):
    from app.providers import doubao_image
    captured = {}

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            captured.update(kwargs['json'])
            return SimpleNamespace(status_code=200, json=lambda: {'data': [{'b64_json': 'aGVsbG8='}]})

    monkeypatch.setattr(doubao_image.httpx, 'AsyncClient', Client)
    prompt = f'Output exact {size}; preserve the subject.'
    plan = SimpleNamespace(size=size, output_format='png')
    asyncio.run(doubao_image.DoubaoImageProvider()._generate_one(prompt, plan, index=0))
    assert captured['prompt'] == prompt
    assert captured.get('size') == expected
    assert captured.get('size') != 'auto'
    assert plan.size == size
