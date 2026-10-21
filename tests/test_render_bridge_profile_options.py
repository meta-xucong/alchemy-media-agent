"""Typed native profile negotiation, wire preservation and original-byte checks."""
from dataclasses import replace
from io import BytesIO
from types import SimpleNamespace

import httpx
from PIL import Image
import pytest
from pydantic import ValidationError

from app.integrations.render_bridge.client import BridgeClient, BridgeError
from app.integrations.render_bridge.native_service import NativeBridgeService
from app.integrations.render_bridge.options import native_profile, image_options_projection
from app.integrations.render_bridge.service import digest
from app.integrations.render_bridge.settings import BridgeSettings
from test_render_bridge_native_coordinator import NativeGatewayDouble, NativeMockBridge, request
from test_render_bridge_preview import settings, run, due


def descriptor(profile='codex-image'):
    return {'schema_version': '1', 'quality': {'values': ['auto'], 'semantics': 'unspecified_only'},
        'output_format': {'values': ['png', 'jpeg'], 'semantics': 'original_artifact_postcondition'},
        'input_fidelity': {'values': [], 'semantics': 'omitted_only'},
        'references': {'max_count': 0 if profile == 'midjourney-manual' else 8,
            'semantics': {'fake-image':'hash_checked_not_conditioning', 'codex-image':'local_image_input_unverified',
                          'midjourney-manual':'not_supported'}[profile]}}


def capabilities(profile='codex-image'):
    return {'schema_version':'1', 'profiles':[{'execution_profile_id':profile, 'execution_profile_revision':'1',
        'operation':'image.generate', 'limits':{'max_output_bytes':16777216,'max_image_pixels':16777216,'max_dimension':8192},
        'image_options_contract':descriptor(profile)}]}


class OptionsBridge(NativeMockBridge):
    def __init__(self, profile, output_format):
        super().__init__()
        self.profile, self.output_format = profile, output_format
        output = BytesIO()
        Image.new('RGB', (1024, 1024), 'green').save(output, format=output_format.upper())
        self.content = output.getvalue()
        self.capabilities = capabilities(profile)

    async def __call__(self, request):
        if request.url.path.endswith('/capabilities'):
            self.calls.append((request.method, 'capabilities'))
            return httpx.Response(200, json=self.capabilities)
        response = await super().__call__(request)
        if '/receipts/' in request.url.path and not request.url.path.endswith('/ack'):
            value = response.json()
            value.update(execution_profile_id=self.profile, mime_type=f'image/{self.output_format}')
            return httpx.Response(200, json=value)
        if '/artifacts/' in request.url.path and request.url.path.endswith('/content'):
            return httpx.Response(200, content=self.content, headers={'Content-Type': f'image/{self.output_format}'})
        return response


class OptionsGateway(NativeGatewayDouble):
    def create_plan(self, *args, execution_profile_id='fake-image', output_format='png', **kwargs):
        self.profile, self.output_format = execution_profile_id, output_format
        return super().create_plan(*args, **kwargs)

    def prepare(self, actor, target, *, execution_profile_id):
        assert execution_profile_id == self.profile
        value = super().prepare(actor, target, execution_profile_id='fake-image')
        value.update(execution_profile_id=self.profile, test_fixture=self.profile == 'fake-image')
        value['image_options']['output_format'] = self.output_format
        return value

    def read_reference(self, *args, execution_profile_id='fake-image', **kwargs):
        assert execution_profile_id == self.profile
        return super().read_reference(*args, **kwargs)

    def register_receipt(self, *args, **kwargs):
        assert kwargs['execution_profile_id'] == self.profile
        self.registered_format = Image.open(BytesIO(kwargs['artifact_bytes'])).format
        return super().register_receipt(*args, **{**kwargs, 'execution_profile_id':'fake-image'})


def service(tmp_path, profile, output_format):
    gateway, bridge = OptionsGateway(), OptionsBridge(profile, output_format)
    config = settings(tmp_path, native_enabled=True, profiles=(profile,), native_profiles=(profile,))
    svc = NativeBridgeService(config, lambda *_: {'revision':'r1'}, gateway,
        client=BridgeClient(config.base_url, config.token, transport=httpx.MockTransport(bridge)), target_factory=SimpleNamespace)
    return svc, gateway, bridge


@pytest.mark.parametrize('profile', ['fake-image', 'codex-image', 'midjourney-manual'])
@pytest.mark.parametrize('output_format', ['png', 'jpeg'])
def test_typed_profile_roundtrip_and_same_request_recovery(tmp_path, profile, output_format):
    async def case():
        svc, gateway, bridge = service(tmp_path, profile, output_format)
        try:
            payload = request(profile_id=profile, output_format=output_format, acknowledge_native_development=True,
                              uploaded_asset_ids=['reference_a'] if profile == 'codex-image' else [])
            job = await svc.create('101', payload)
            assert gateway.create_calls == 0 and bridge.calls == []
            bridge.lose_ack = True
            await svc.tick()
            final = await due(svc, job)
            assert final['state'] == 'registered', final
            assert gateway.create_calls == gateway.register_calls == 1 and len(bridge.tasks) == 1
            wire = next(iter(bridge.tasks.values()))['request']
            assert wire['parameters']['image_options'] == {'schema_version':'1', 'quality':'auto','output_format':output_format}
            assert wire['execution_profile_id'] == profile
            assert gateway.registered_format == output_format.upper()
            assert (await svc.create('101', payload))['id'] == job['id']
            assert len(bridge.acks) == 2 and bridge.acks[0] == bridge.acks[1]
            public = svc.public(final)
            assert public['test_fixture'] == (profile == 'fake-image')
            assert public['real_tool_verified'] is public['formal_delivery'] is False
            assert public['format_semantics'] == 'original_artifact_postcondition'
            changed = payload.model_copy(update={'output_format':'jpeg' if output_format == 'png' else 'png'})
            with pytest.raises(BridgeError, match='idempotency_conflict'):
                await svc.create('101', changed)
        finally:
            await svc.close()
    run(case())


@pytest.mark.parametrize('invalid', [{'quality':'high'}, {'quality':'medium'}, {'input_fidelity':'high'}, {'input_fidelity':None}])
def test_unsupported_user_options_are_not_coerced(invalid):
    with pytest.raises(ValidationError):
        request(**invalid)


@pytest.mark.parametrize('change', ['missing', 'version', 'unsupported_format', 'references'])
def test_incompatible_contract_rejects_before_planning(tmp_path, change):
    async def case():
        svc, gateway, bridge = service(tmp_path, 'codex-image', 'jpeg')
        try:
            item = bridge.capabilities['profiles'][0]
            if change == 'missing': item.pop('image_options_contract')
            elif change == 'version': item['image_options_contract']['schema_version'] = '2'
            elif change == 'unsupported_format': item['image_options_contract']['output_format']['values'] = ['png']
            else: item['image_options_contract']['references']['max_count'] = 0
            job = await svc.create('101', request(profile_id='codex-image', output_format='jpeg',
                acknowledge_native_development=True, uploaded_asset_ids=['reference_a']))
            await svc.tick()
            final = await svc.local(svc.store.get, job['id'])
            assert final['state'] == 'protocol_error'
            assert gateway.create_calls == gateway.register_calls == 0 and not bridge.tasks and not bridge.acks
        finally: await svc.close()
    run(case())


def test_mismatched_original_format_never_registers_or_acknowledges(tmp_path):
    async def case():
        svc, gateway, bridge = service(tmp_path, 'codex-image', 'png')
        try:
            job = await svc.create('101', request(profile_id='codex-image', output_format='jpeg', acknowledge_native_development=True))
            await svc.tick()
            final = await svc.local(svc.store.get, job['id'])
            assert final['state'] == 'protocol_error' and final['last_error'] == 'native_output_format_mismatch'
            assert gateway.register_calls == 0 and not bridge.acks and len(bridge.tasks) == 1
            await svc.tick()
            assert gateway.create_calls == 1 and len(bridge.tasks) == 1
        finally: await svc.close()
    run(case())


def test_default_config_manual_refs_and_old_request_identity(tmp_path):
    async def case():
        svc, _, _ = service(tmp_path, 'fake-image', 'png')
        try:
            payload = request()
            job = await svc.create('101', payload)
            assert job['digest'] == digest({'project_id':'project_1', 'user_input':payload.user_input,
                'profile_id':'fake-image', 'width':1024, 'height':1024, 'seed':0})
            with pytest.raises(BridgeError, match='native_profile_not_enabled'):
                await svc.create('101', request(profile_id='codex-image', acknowledge_native_development=True))
        finally: await svc.close()
        svc, _, _ = service(tmp_path / 'manual', 'midjourney-manual', 'png')
        try:
            with pytest.raises(BridgeError, match='native_profile_references_unsupported'):
                await svc.create('101', request(profile_id='midjourney-manual', acknowledge_native_development=True,
                    uploaded_asset_ids=['reference_a']))
        finally: await svc.close()
    run(case())
    assert BridgeSettings().native_profiles == ('fake-image',)
    value = descriptor(); value['unknown_future_field'] = 'ignored'
    assert image_options_projection(value) == descriptor()


def test_native_profile_configuration_is_separate_and_fail_closed(monkeypatch):
    monkeypatch.setenv('ALCHEMY_RENDER_BRIDGE_MODE', 'enabled')
    monkeypatch.setenv('ALCHEMY_RENDER_BRIDGE_URL', 'https://fixture.test')
    monkeypatch.setenv('ALCHEMY_RENDER_BRIDGE_TOKEN', 'fixture')
    monkeypatch.setenv('ALCHEMY_RENDER_BRIDGE_WORKSPACE', 'fixture')
    monkeypatch.setenv('ALCHEMY_RENDER_BRIDGE_PROFILES', 'fake-image,codex-image')
    monkeypatch.setenv('ALCHEMY_RENDER_BRIDGE_NATIVE_ENABLED', 'true')
    monkeypatch.delenv('ALCHEMY_RENDER_BRIDGE_NATIVE_PROFILES', raising=False)
    assert BridgeSettings.from_env().native_profiles == ('fake-image',)
    monkeypatch.setenv('ALCHEMY_RENDER_BRIDGE_NATIVE_PROFILES', 'fake-image,codex-image')
    assert BridgeSettings.from_env().config_error is None
    assert BridgeSettings.from_env().native_profiles == ('fake-image','codex-image')
    for invalid in ('', 'fake-image,fake-image', 'midjourney-manual', 'future-renderer'):
        monkeypatch.setenv('ALCHEMY_RENDER_BRIDGE_NATIVE_PROFILES', invalid)
        assert BridgeSettings.from_env().config_error == 'invalid_native_profiles'
    monkeypatch.setenv('ALCHEMY_RENDER_BRIDGE_MODE', 'disabled')
    assert BridgeSettings.from_env() == BridgeSettings()
