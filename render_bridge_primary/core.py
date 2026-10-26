from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from PIL import Image
from .http import BridgeClient, BridgeError


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def _hash(value: bytes):
    return hashlib.sha256(value).hexdigest()


_ROOT = Path(__file__).resolve().parent.parent / '.render_bridge_primary'

def control_path():
    return Path(os.environ.get('ALCHEMY_RENDER_BRIDGE_PRIMARY_CONFIG', str(_ROOT / 'control.json')))

def state_root():
    return Path(os.environ.get('ALCHEMY_RENDER_BRIDGE_PRIMARY_STATE_ROOT', str(_ROOT / 'ledgers')))


class PrimaryError(Exception):
    """Safe fail-closed error; never an API fallback authorization."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PrimarySettings:
    enabled: bool = False
    base_url: str = ''
    token: str = field(default='', repr=False)
    profile: str = 'codex-image'
    state_dir: Path = _ROOT / 'ledgers/default'
    workspace: str = ''

    @classmethod
    def from_env(cls, product: str):
        path = control_path()
        data = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(data, dict): raise ValueError()
                if data.get('schema_version') != '1' or data.get('mode') not in {'disabled','enabled','draining'}: raise ValueError()
                profiles=data.get('profiles')
                if not isinstance(profiles,list) or not profiles or any(not isinstance(p,str) or p not in {'fake-image','codex-image','midjourney-manual'} for p in profiles) or len(set(profiles))!=len(profiles): raise ValueError()
                if not isinstance(data.get('base_url',''),str) or not isinstance(data.get('workspace',''),str): raise ValueError()
            except (OSError, ValueError):
                raise PrimaryError('primary_config_invalid') from None
        root = state_root()
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', product):
            raise PrimaryError('invalid_product')
        base = str(data.get('base_url', '')).rstrip('/')
        if base:
            try:
                parsed=urlsplit(base)
                local_http=(parsed.scheme=='http' and parsed.hostname in {'127.0.0.1','localhost','::1'} and os.environ.get('ALCHEMY_RENDER_BRIDGE_ALLOW_HTTP_LOOPBACK')=='true')
                if not parsed.hostname or not (parsed.scheme=='https' or local_http) or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {'','/'}: raise ValueError()
                _=parsed.port
            except ValueError:
                raise PrimaryError('invalid_bridge_url') from None
        elif data.get('mode') in {'enabled','draining'}:
            raise PrimaryError('bridge_configuration_missing')
        expected = os.environ.get('ALCHEMY_RENDER_BRIDGE_URL', '').rstrip('/')
        if expected and base and expected != base:
            raise PrimaryError('bridge_credential_endpoint_mismatch')
        expected_workspace=os.environ.get('ALCHEMY_RENDER_BRIDGE_WORKSPACE','')
        if expected_workspace and data.get('workspace') and expected_workspace!=data['workspace']:
            raise PrimaryError('bridge_credential_workspace_mismatch')
        profiles = data.get('profiles', [])
        return cls(enabled=data.get('mode') == 'enabled' and 'codex-image' in profiles,
                   base_url=base, workspace=str(data.get('workspace','')),
                   token=os.environ.get('ALCHEMY_RENDER_BRIDGE_PRIMARY_TOKEN', os.environ.get('ALCHEMY_RENDER_BRIDGE_TOKEN','')),
                   state_dir=root / product)


@dataclass(frozen=True)
class Reference:
    content: bytes
    mime_type: str


@dataclass(frozen=True)
class PrimaryRequest:
    product: str
    owner_id: str
    unit_id: str
    prompt: str
    parameters: dict[str, Any]
    references: tuple[Reference, ...] = ()
    hard_requirements: dict[str, Any] = field(default_factory=dict)
    binding_id: str | None = None

    @property
    def key(self):
        return _hash(_json([self.product, self.owner_id, self.unit_id]).encode())

    @property
    def digest(self):
        return _hash(_json([self.product, self.owner_id, self.unit_id, self.prompt,
                           self.parameters, self.hard_requirements, self.binding_id,
                           [[_hash(r.content), r.mime_type] for r in self.references]]).encode())


@dataclass(frozen=True)
class OriginalImage:
    content: bytes
    mime_type: str
    sha256: str
    width: int
    height: int


@dataclass(frozen=True)
class PrimaryResult:
    route: str
    state: str
    reason: str
    origin_key: str
    execution_key: str
    task_id: str | None = None
    receipt_id: str | None = None
    image: OriginalImage | None = None
    provenance: dict[str, Any] = field(default_factory=dict)


def pending_count(settings_or_path):
    root = Path(settings_or_path.state_dir if isinstance(settings_or_path, PrimarySettings) else settings_or_path)
    total = 0
    for path in root.rglob('primary.sqlite3') if root.exists() else []:
        with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as db:
            total += db.execute("SELECT count(*) FROM units WHERE state NOT IN ('api_ready','api_completed','acked','canceled','failed','expired') AND COALESCE(json_extract(data, '$.cancel_reconciled'), 0)=0").fetchone()[0]
    return total


class PrimaryTransport:
    def __init__(self, settings: PrimarySettings, client=None):
        self.settings = settings
        self.client = client or BridgeClient(settings.base_url, settings.token)
        self.path = Path(settings.state_dir) / 'primary.sqlite3'

    def _db(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=15)
        db.execute('CREATE TABLE IF NOT EXISTS units (key TEXT PRIMARY KEY, digest TEXT NOT NULL, state TEXT NOT NULL, data TEXT NOT NULL, image BLOB)')
        db.row_factory = sqlite3.Row
        return db

    async def close(self):
        await self.client.close()
    aclose = close

    async def __aenter__(self): return self
    async def __aexit__(self, *args): await self.close()

    def _read(self, request):
        if not self.path.exists(): return None
        with self._db() as db:
            row = db.execute('SELECT * FROM units WHERE key=?', (request.key,)).fetchone()
        if row and row['digest'] != request.digest:
            raise PrimaryError('request_semantics_changed')
        return row

    def match_existing_request(self, candidates):
        """Select an exact historical digest without modifying the journal.

        Callers supply known versioned reconstructions, never arbitrary saved
        payloads. A known key with no matching digest remains a hard failure.
        """
        candidates = tuple(candidates)
        if not candidates or len({request.key for request in candidates}) != 1:
            raise PrimaryError('invalid_request_candidates')
        if not self.path.exists(): return None
        with sqlite3.connect(self.path.resolve().as_uri() + '?mode=ro', uri=True) as db:
            row = db.execute('SELECT digest FROM units WHERE key=?', (candidates[0].key,)).fetchone()
        if row is None: return None
        for request in candidates:
            if request.digest == row[0]:
                return request
        raise PrimaryError('request_semantics_changed')

    def _save(self, request, data, *, state=None, image=None):
        return self._save_key(request.key, data, state=state, image=image)

    def _save_key(self, key, data, *, state=None, image=None):
        state = state or data['state']
        data['state'] = state
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT data FROM units WHERE key=?',(key,)).fetchone()
            if old:
                previous=json.loads(old['data'])
                # A product has durably published this unit and retired only its
                # duplicate transport bytes. A stale poll/ACK cannot resurrect it.
                if previous.get('cache_retired'):
                    return
                for name in ('task_id','receipt_id','attempt_id','image','registration_ref'):
                    if previous.get(name) is not None:
                        if data.get(name) is not None and data[name]!=previous[name]:
                            raise PrimaryError('bridge_journal_identity_mismatch')
                        data[name]=previous[name]
                if previous.get('cancel_requested'): data['cancel_requested']=True
                if previous.get('cancel_reconciled'): data['cancel_reconciled']=True
                if previous.get('cache_retirement_requested'):
                    data['cache_retirement_requested'] = True
                order={'preflight':0,'bridge_submission_unknown':1,'queued':2,'running':3,'execution_unknown':4,'awaiting_user':4,'canceled':5,'failed':5,'expired':5,'artifacts_ready':6,'acked':7}
                if previous['route']=='bridge' and order.get(previous['state'],0)>order.get(state,0):
                    state=previous['state']
                    data['state']=state
            if data.get('cache_retirement_requested') and (
                    (state == 'acked' and data.get('registration_ref')) or state == 'api_completed'):
                data['cache_retired'] = True
                data.pop('payload', None)
                db.execute('UPDATE units SET state=?,data=?,image=NULL WHERE key=?',
                           (state, _json(data), key))
            else:
                db.execute('UPDATE units SET state=?,data=?,image=COALESCE(?,image) WHERE key=?',
                           (state, _json(data), image, key))

    def _start(self, request):
        data = dict(product=request.product, owner_hash=_hash(request.owner_id.encode()), unit_id=request.unit_id, route='bridge', state='preflight', reason='bridge_primary', origin_key='rb_'+request.key,
                    execution_key='api_'+request.key, endpoint=self.settings.base_url,
                    workspace=self.settings.workspace, profile=self.settings.profile)
        with self._db() as db:
            db.execute('INSERT OR IGNORE INTO units(key,digest,state,data) VALUES(?,?,?,?)',
                       (request.key,request.digest,'preflight',_json(data)))
        return self._read(request)

    def _result(self, row):
        data=json.loads(row['data']); image=None
        if row['image'] is not None and not data.get('cancel_requested'):
            meta=data['image']; image=OriginalImage(bytes(row['image']),meta['mime_type'],meta['sha256'],meta['width'],meta['height'])
        provenance={k:v for k,v in data.items() if k in {'product','profile','route','state','reason','origin_key','execution_key','task_id','receipt_id','attempt_id','image','queue_active_count','queue_limit','queue_observed_at'}}
        deadline = (data.get('payload') or {}).get('deadline')
        if isinstance(deadline, str): provenance['deadline'] = deadline
        if data.get('cancel_requested') and data['state'] not in {'canceled','failed','expired'}:
            data['state']='cancel_requested'
        provenance['policy_version']='rb14'
        if data['route']=='bridge':
            provenance.update(execution_profile_id=data['profile'], execution_profile_revision='1',
                              actual_provider='render_bridge', provider_evidence='transport_only',
                              actual_model=None, model_evidence='not_reported')
        if 'queue_observed_at' in provenance:
            provenance['queue_snapshot_diagnostic']=True
        return PrimaryResult(data['route'],data['state'],data['reason'],data['origin_key'],data['execution_key'],data.get('task_id'),data.get('receipt_id'),image,provenance)

    def has_binding(self, request):
        return self._read(request) is not None

    def cached_result(self, request):
        """Inspect an existing exact binding without HTTP or new admission."""
        if not self.path.exists(): return None
        with sqlite3.connect(self.path.resolve().as_uri() + '?mode=ro', uri=True) as db:
            db.row_factory = sqlite3.Row
            row = db.execute('SELECT * FROM units WHERE key=?', (request.key,)).fetchone()
        if row and row['digest'] != request.digest:
            raise PrimaryError('request_semantics_changed')
        return self._result(row) if row is not None else None

    has_unit = has_binding

    def _api(self, request, data, reason, *, first_create=False):
        data.update(route='api',state='api_ready',reason=reason)
        expected = 'bridge_submission_unknown' if first_create else 'preflight'
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            previous=db.execute('SELECT state,data FROM units WHERE key=?',(request.key,)).fetchone()
            if previous and previous['state']==expected and not json.loads(previous['data']).get('cancel_requested'):
                db.execute('UPDATE units SET state=?,data=? WHERE key=? AND state=?',
                           ('api_ready',_json(data),request.key,expected))
        return self._result(self._read(request))

    def claim_api(self, request):
        row=self._read(request)
        if row is None and not self.settings.enabled:
            row=self._start(request)
            self._api(request,json.loads(row['data']),'bridge_disabled')
            row=self._read(request)
        if not row: raise PrimaryError('route_not_resolved')
        data=json.loads(row['data'])
        if data['route']!='api': raise PrimaryError('bridge_owns_execution')
        data['state']='api_execution_unknown'
        with self._db() as db:
            result=db.execute("UPDATE units SET state=?,data=? WHERE key=? AND state='api_ready'",('api_execution_unknown',_json(data),request.key))
            return result.rowcount==1

    def complete_api(self, request):
        row=self._read(request)
        if not row: raise PrimaryError('route_not_resolved')
        data=json.loads(row['data'])
        if data['route']!='api' or row['state'] not in {'api_execution_unknown','api_completed'}:
            raise PrimaryError('api_not_claimed')
        self._save(request,data,state='api_completed')

    @staticmethod
    def _supported(request, caps, profile):
        selected=next((p for p in caps.get('profiles',[]) if p.get('execution_profile_id')==profile and p.get('execution_profile_revision')=='1'),None)
        if not selected: return False
        pc=selected.get('parameter_contract',{}); ic=selected.get('image_options_contract',{})
        limits=selected.get('limits',{})
        width=request.parameters.get('width',32); height=request.parameters.get('height',32); seed=request.parameters.get('seed',0)
        if not isinstance(request.prompt,str) or not 1<=len(request.prompt)<=16000: return False
        if type(width) is not int or type(height) is not int or min(width,height)<1: return False
        if max(width,height)>limits.get('max_dimension',40000) or width*height>limits.get('max_image_pixels',40000000): return False
        if type(seed) is not int or not 0<=seed<=2**32-1: return False
        if request.binding_id is not None and (not isinstance(request.binding_id,str) or not 1<=len(request.binding_id)<=256): return False
        if set(request.parameters)-{'width','height','seed','image_options','codex_adapter'}: return False
        adapter = request.parameters.get('codex_adapter')
        if 'codex_adapter' in request.parameters and (profile != 'codex-image' or adapter != 'codex_cli_imagegen_v1' or adapter not in pc.get('codex_adapter', {}).get('values', [])): return False
        if adapter is not None:
            ic = pc['codex_adapter'].get('image_options_contract')
            if not isinstance(ic, dict): return False
        options=request.parameters.get('image_options')
        if options is not None:
            if not isinstance(options,dict) or options.get('schema_version')!='1' or set(options)-{'schema_version','quality','output_format','transparent_background'}: return False
            if 'quality' in options and options['quality'] not in ic.get('quality',{}).get('values',[]): return False
            if 'output_format' in options and options['output_format'] not in ic.get('output_format',{}).get('values',[]): return False
            if 'transparent_background' in options and options['transparent_background'] not in ic.get('transparent_background',{}).get('values',[]): return False
        if len(request.references)>ic.get('references',{}).get('max_count',0): return False
        if any(r.mime_type not in {'image/png','image/jpeg'} or len(r.content)<1 or len(r.content)>caps.get('limits',{}).get('max_input_bytes',1048576) for r in request.references): return False
        for key,value in request.hard_requirements.items():
            if value is None or value is False or value=='': continue
            if key=='output_format' and value in ic.get('output_format',{}).get('values',[]) and options and options.get('output_format')==value: continue
            if key=='quality' and value=='auto': continue
            if key=='exact_dimensions' and pc.get('dimension_semantics')=='exact_output_match': continue
            if key=='reference_fusion' and request.references and len(request.references)<=ic.get('references',{}).get('max_count',0): continue
            if key=='reference_semantics' and value==pc.get('reference_semantics'): continue
            return False
        return True

    @staticmethod
    def _health_state(health):
        """Classify execution evidence without treating missing evidence as downtime."""
        if not isinstance(health, dict): return 'unknown'
        state=health.get('health')
        if state=='unavailable': return 'unavailable'
        if state!='available': return 'unknown'
        try:
            valid_until=health['valid_until']
            if not isinstance(valid_until,str): return 'unknown'
            deadline=datetime.fromisoformat(valid_until.replace('Z','+00:00'))
            return 'available' if deadline.tzinfo is not None and deadline>datetime.now(timezone.utc) else 'unknown'
        except (KeyError, ValueError, TypeError): return 'unknown'

    async def resolve(self, request):
        row=self._read(request)
        if row is None and not self.settings.enabled:
            return PrimaryResult('api','api_ready','bridge_disabled','rb_'+request.key,'api_'+request.key)
        row=row or self._start(request)
        data=json.loads(row['data'])
        if data['route']=='api' or row['image'] is not None or row['state']=='acked' or (row['state']=='canceled' and not data.get('payload')): return self._result(row)
        if (data['endpoint'],data['workspace'],data['profile']) != (self.settings.base_url,self.settings.workspace,self.settings.profile):
            raise PrimaryError('bridge_scope_changed')
        if data['state']=='preflight':
            if not self.settings.enabled: return self._api(request,data,'bridge_disabled')
            if not self.settings.base_url or not self.settings.token: return self._api(request,data,'bridge_unavailable')
            try: caps=await self.client.capabilities()
            except BridgeError: return self._api(request,data,'bridge_unavailable')
            queue=caps.get('queue',{})
            if isinstance(queue,dict):
                for source,target in (('active_tasks','queue_active_count'),('max_queued_tasks','queue_limit')):
                    value=queue.get(source)
                    if type(value) is int and value>=0: data[target]=value
                if 'queue_active_count' in data or 'queue_limit' in data:
                    data['queue_observed_at']=datetime.now(timezone.utc).isoformat()
            if not self._supported(request,caps,self.settings.profile): return self._api(request,data,'bridge_capability_unsupported')
            if caps.get('admission',{}).get('accepting_new_tasks') is False: return self._api(request,data,'bridge_unavailable')
            availability=caps.get('routing_availability_v1',{}).get('profiles',[])
            health=next((h for h in availability if isinstance(h,dict) and h.get('profile_id')==self.settings.profile),None)
            health_state=self._health_state(health)
            if health_state=='unavailable': return self._api(request,data,'bridge_unavailable')
            # Unknown/expired profile health is not proof of non-admission. The
            # authenticated Bridge endpoint has accepted this preflight and is
            # accepting tasks, so keep the request bridge_only and let Bridge
            # report a recoverable executor/account state instead of silently
            # selecting a second, potentially billable provider.
            # Input uploads cannot execute a renderer. A failure here proves this unit was not submitted.
            references=[]
            try:
                for index,ref in enumerate(request.references):
                    sha=_hash(ref.content)
                    item=await self.client.create_input(dict(input_key=f'{data["origin_key"]}_{index}',original_sha256=sha,size=len(ref.content),mime_type=ref.mime_type))
                    ref_id=item.get('input_id') or item.get('input_ref')
                    if not ref_id: raise BridgeError('invalid_bridge_response')
                    await self.client.upload_input(ref_id,ref.content,ref.mime_type)
                    references.append(dict(input_ref=ref_id,role='reference',hash=sha))
            except BridgeError: return self._api(request,data,'bridge_unavailable')
            payload=dict(schema_version='1',origin_key=data['origin_key'],binding_id=request.binding_id or request.key,
                         operation='image.generate',execution_profile_id=self.settings.profile,execution_profile_revision='1',
                         prompt=request.prompt,parameters=request.parameters,references=references,output_slot={'slot_id':'primary','count':1},
                         deadline=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),routing='bridge_only')
            data.update(payload=payload,state='bridge_submission_unknown')
            # CAS is the only create permit, across workers/processes. Store the exact wire payload first.
            with self._db() as db:
                won=db.execute("UPDATE units SET state=?,data=? WHERE key=? AND state='preflight'",(data['state'],_json(data),request.key)).rowcount==1
            if not won: return self._result(self._read(request))
            try: task=await self.client.create_task(payload)
            except BridgeError as error:
                if (error.code,error.status) in {('queue_capacity',429),('bridge_draining',503)}:
                    return self._api(request,data,'bridge_queue_capacity' if error.code=='queue_capacity' else 'bridge_unavailable', first_create=True)
                return self._result(self._read(request))
        else:
            try: task=await self.client.by_origin(data['origin_key'])
            except BridgeError: return self._result(row)
        if task.get('origin_key')!=data['origin_key'] or task.get('request')!=data.get('payload'):
            raise PrimaryError('bridge_task_identity_mismatch')
        if not task.get('remote_task_id'): raise PrimaryError('invalid_bridge_task')
        data.update(task_id=task['remote_task_id'],state=task.get('state','bridge_submission_unknown'),attempt_id=task.get('attempt_id'),receipt_id=task.get('receipt_id'))
        self._save(request,data)
        if data.get('cancel_requested') and data['state'] not in {'canceled','failed','expired','artifacts_ready'}:
            try: await self.client.cancel(data['task_id'])
            except BridgeError: pass
        if data.get('receipt_id'):
            await self._download(request,data)
        return self._result(self._read(request))

    async def _download(self, request, data):
        try:
            receipt=await self.client.receipt(data['receipt_id'])
            if (receipt.get('task_id')!=data['task_id'] or receipt.get('receipt_id')!=data['receipt_id']
                    or not data.get('attempt_id') or receipt.get('attempt_id')!=data['attempt_id']
                    or receipt.get('execution_profile_id')!=data['profile']
                    or receipt.get('execution_profile_revision')!='1' or receipt.get('slot_id')!='primary'):
                raise PrimaryError('bridge_receipt_identity_mismatch')
            content,_=await self.client.artifact(receipt['artifact_id'],16777216)
        except BridgeError: return
        sha=_hash(content)
        if sha!=receipt.get('original_sha256') or len(content)!=receipt.get('size'):
            raise PrimaryError('bridge_artifact_integrity_failed')
        try:
            with Image.open(io.BytesIO(content)) as im:
                width,height=im.size; mime=Image.MIME.get(im.format)
                if width*height>40000000 or getattr(im,'n_frames',1)!=1: raise ValueError()
                im.verify()
            with Image.open(io.BytesIO(content)) as im: im.load()
        except Exception:
            raise PrimaryError('bridge_artifact_decode_failed') from None
        if mime!=receipt.get('mime_type') or receipt.get('dimensions')!={'width':width,'height':height}:
            raise PrimaryError('bridge_artifact_metadata_mismatch')
        options=request.parameters.get('image_options',{})
        if request.hard_requirements.get('exact_dimensions') and (width,height)!=(request.parameters.get('width'),request.parameters.get('height')):
            raise PrimaryError('bridge_artifact_dimensions_mismatch')
        if options.get('output_format') and mime!='image/'+options['output_format']:
            raise PrimaryError('bridge_artifact_format_mismatch')
        data['image']=dict(sha256=sha,mime_type=mime,width=width,height=height,size=len(content))
        self._save(request,data,state='artifacts_ready',image=content)

    def _check_scope(self, data):
        if (data['endpoint'], data['workspace'], data['profile']) != (self.settings.base_url, self.settings.workspace, self.settings.profile):
            raise PrimaryError('bridge_scope_changed')

    async def _ack_saved(self, key, data):
        self._check_scope(data)
        await self.client.accept_registered_receipt(data['receipt_id'], client_receipt_id='ack_'+key,
            original_hash=data['image']['sha256'], native_registration_ref=data['registration_ref'])
        self._save_key(key, data, state='acked')

    async def acknowledge(self, request, registration_ref):
        if not isinstance(registration_ref, str) or not registration_ref.strip():
            raise PrimaryError('native_confirmation_required')
        # Durable native registration is the authority. Save its immutable ACK
        # intent before sending, so a terminal product need not be polled again.
        self._read(request)  # Validate the frozen request digest.
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM units WHERE key=?', (request.key,)).fetchone()
            if not row: raise PrimaryError('artifact_not_registered')
            data=json.loads(row['data'])
            if data.get('registration_ref') not in {None, registration_ref}:
                raise PrimaryError('native_registration_mismatch')
            if data.get('cancel_requested'): raise PrimaryError('bridge_cancel_requested')
            if row['state']=='acked': return
            if row['image'] is None: raise PrimaryError('artifact_not_registered')
            self._check_scope(data)
            data['registration_ref']=registration_ref
            db.execute('UPDATE units SET data=? WHERE key=?', (_json(data), request.key))
        await self._ack_saved(request.key, data)

    def retire_units(self, requests):
        """Drop duplicate bytes only after the owning product confirms publication.

        All units must be ACKed/API-completed. Keep semantic digests and receipt
        identities permanently; absent bytes never authorize a new execution.
        This is an explicit product lifecycle hook, not an age-based sweep.
        """
        requests = tuple(requests)
        if not requests or not self.path.exists(): return False
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            rows = []
            for request in requests:
                row = db.execute('SELECT * FROM units WHERE key=?', (request.key,)).fetchone()
                if row is None: return False
                if row['digest'] != request.digest:
                    raise PrimaryError('request_semantics_changed')
                data = json.loads(row['data'])
                if row['state'] not in {'acked', 'api_completed'}: return False
                if row['state'] == 'acked' and not data.get('registration_ref'): return False
                rows.append((request.key, data))
            for key, data in rows:
                data['cache_retired'] = True
                # The digest remains authoritative; no replay needs raw prompt
                # or reference bindings after the remote receipt is ACKed.
                data.pop('payload', None)
                db.execute('UPDATE units SET data=?, image=NULL WHERE key=?', (_json(data), key))
        return True

    def request_retirement(self, requests):
        """Record product-confirmed native completion without losing pending ACK bytes.

        The caller must verify all native outputs before invoking this hook.
        Existing ACK reconciliation can retire the duplicate BLOB atomically,
        but an intent never counts as ACK confirmation or authorizes new work.
        """
        requests = tuple(requests)
        if not requests or not self.path.exists(): return False
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            rows = []
            for request in requests:
                row = db.execute('SELECT * FROM units WHERE key=?', (request.key,)).fetchone()
                if row is None: return False
                if row['digest'] != request.digest:
                    raise PrimaryError('request_semantics_changed')
                data = json.loads(row['data'])
                if row['state'] not in {'artifacts_ready', 'acked', 'api_completed'}: return False
                if data.get('cancel_requested'): return False
                if row['state'] == 'artifacts_ready' and row['image'] is None: return False
                if row['state'] == 'acked' and not data.get('registration_ref'): return False
                rows.append((request.key, row['state'], data))
            for key, state, data in rows:
                data['cache_retirement_requested'] = True
                if state in {'acked', 'api_completed'}:
                    data['cache_retired'] = True
                    data.pop('payload', None)
                    db.execute('UPDATE units SET data=?,image=NULL WHERE key=?', (_json(data), key))
                else:
                    db.execute('UPDATE units SET data=? WHERE key=?', (_json(data), key))
        return True

    async def reconcile_pending(self, limit=32):
        """Retry durable ACK/cancel intents only; never create, render or import."""
        counts=dict(checked=0, acked=0, canceled=0, pending=0, errors=0)
        if not self.path.exists(): return counts
        limit=max(0, min(int(limit), 256))
        with self._db() as db:
            rows=db.execute('SELECT key,data FROM units').fetchall()
        for row in rows:
            data=json.loads(row['data'])
            ack=data.get('registration_ref') and data['state']!='acked'
            cancel=data.get('cancel_requested') and not data.get('cancel_reconciled') and data.get('payload')
            if data.get('route')!='bridge' or not (ack or cancel): continue
            if counts['checked']>=limit: break
            counts['checked']+=1
            try:
                self._check_scope(data)
                if ack:
                    await self._ack_saved(row['key'], data)
                    counts['acked']+=1
                    continue
                task=await self.client.by_origin(data['origin_key'])
                if task.get('origin_key')!=data['origin_key'] or task.get('request')!=data['payload'] or not task.get('remote_task_id'):
                    raise PrimaryError('bridge_task_identity_mismatch')
                if data.get('task_id') and data['task_id']!=task['remote_task_id']:
                    raise PrimaryError('bridge_task_identity_mismatch')
                data.update(task_id=task['remote_task_id'], attempt_id=task.get('attempt_id'), receipt_id=task.get('receipt_id'), state=task.get('state','bridge_submission_unknown'))
                self._save_key(row['key'], data)
                if task.get('state') not in {'canceled','failed','expired','artifacts_ready'}:
                    await self.client.cancel(task['remote_task_id'])
                    # Confirm through the origin binding, including an uncertain
                    # cancel response on the next pass; never infer completion.
                    counts['pending']+=1
                else:
                    data['cancel_reconciled']=True
                    self._save_key(row['key'], data)
                    counts['canceled']+=1
            except BridgeError:
                counts['pending']+=1
            except PrimaryError:
                counts['errors']+=1
        return counts

    async def cancel(self, request):
        # Validate the frozen digest before using the trusted product-key cancellation path.
        if not self._read(request): raise PrimaryError('route_not_resolved')
        return await self.cancel_binding(request.product, request.owner_id, request.unit_id)

    def bindings_for(self, product, owner_id, unit_prefix, *, route=None, active_only=False):
        if not self.path.exists(): return []
        owner_hash=_hash(owner_id.encode())
        with self._db() as db:
            rows=db.execute('SELECT data FROM units').fetchall()
        return sorted(data['unit_id'] for row in rows if (data:=json.loads(row['data'])).get('product')==product and data.get('owner_hash')==owner_hash and data.get('unit_id','').startswith(unit_prefix) and (route is None or data.get('route')==route) and (not active_only or (data.get('state') not in {'acked','api_completed','canceled','failed','expired'} and not data.get('registration_ref') and not data.get('cancel_reconciled'))))

    async def cancel_binding(self, product, owner_id, unit_id):
        """Cancel only a pre-existing product-owned binding; never submit or import."""
        key=_hash(_json([product,owner_id,unit_id]).encode())
        if not self.path.exists(): raise PrimaryError('route_not_resolved')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM units WHERE key=?',(key,)).fetchone()
            if not row: raise PrimaryError('route_not_resolved')
            data=json.loads(row['data'])
            if data['state']=='acked' or data.get('registration_ref'): return self._result(row)
            data['cancel_requested']=True
            if data['state'] in {'preflight','api_ready'}: data['state']='canceled'
            db.execute('UPDATE units SET state=?,data=? WHERE key=?',(data['state'],_json(data),key))
        if data['route']=='bridge' and data.get('payload'):
            if (data['endpoint'],data['workspace'],data['profile']) != (self.settings.base_url,self.settings.workspace,self.settings.profile):
                raise PrimaryError('bridge_scope_changed')
            try:
                task=await self.client.by_origin(data['origin_key'])
                if task.get('origin_key')!=data['origin_key'] or task.get('request')!=data['payload']:
                    raise PrimaryError('bridge_task_identity_mismatch')
                if task.get('remote_task_id'):
                    await self.client.cancel(task['remote_task_id'])
            except BridgeError:
                pass
        with self._db() as db:
            row=db.execute('SELECT * FROM units WHERE key=?',(key,)).fetchone()
        return self._result(row)
