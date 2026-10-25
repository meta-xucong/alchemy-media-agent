import asyncio
import base64
from types import SimpleNamespace

import pytest

from app.providers.images import doubao_image as provider


@pytest.fixture(autouse=True)
def seedream4(monkeypatch):
    monkeypatch.setattr(provider, 'settings', SimpleNamespace(
        doubao_image_model='doubao-seedream-4-0-250828', doubao_image_timeout_seconds=1,
    ))


def plan(value):
    return SimpleNamespace(provider_parameters={'size': value}, prompt='unchanged')


@pytest.mark.parametrize('requested,expected', [
    ('16:9', '1536x864'), ('9:16', '864x1536'), ('4:1', '2048x512'),
    ('1920x1080', '1920x1080'), ('1536x864', '1536x864'),
    ('5000x1000', '5000x1000'), ('1K', '1K'), ('2K', '2K'), ('4K', '4K'),
    ('1536x384', None), ('8192x4096', None), ('16000x500', None),
    ('auto', None), ('default', None), ('0x1024', None), ('garbage', None),
])
def test_exact_model_capability(requested, expected):
    assert provider._size(plan(requested)) == expected


def test_unknown_model_does_not_inherit_custom_or_resolution_support():
    provider.settings.doubao_image_model = 'some-other-model'
    for value in ('16:9', '1920x1080', '2K', '4:1'):
        assert provider._size(plan(value)) is None
    assert provider._size(plan('2:3')) == '1024x1536'
    assert 'custom_size' not in provider._canvas_capabilities()


@pytest.mark.parametrize('requested,response_dims,expected', [
    ('1536x384', {}, (None, None)),
    ('1536x384', {'width': 1280, 'height': 960}, (1280, 960)),
    ('16:9', {}, (1536, 864)),
    ('2K', {}, (None, None)),
])
def test_response_dimension_fallback_uses_effective_canvas(requested, response_dims, expected):
    original = plan(requested)
    data = {'data': [{'b64_json': base64.b64encode(b'image').decode(), **response_dims}]}
    outputs = asyncio.run(provider._outputs_from_response(
        data, original, index=0, operation='images.generate', reference_count=0,
    ))
    assert (outputs[0].width, outputs[0].height) == expected
    assert original.provider_parameters == {'size': requested}
    assert original.prompt == 'unchanged'
