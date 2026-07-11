# Alchemy V3 Identity Sidecar

> RESEARCH ONLY. Doc100 forbids this service from being registered or called by
> the V3 production generation path. It must not process production projects or
> create, patch, composite, or replace user-delivered final images. Retention in
> this repository is for isolated capability research and benchmarking only.

This service is the deployable reference gateway for Doc98/Doc99. It translates
Alchemy's stable identity contract into an operator-supplied ComfyUI API-format
workflow. The gateway itself has no CUDA, model, or face-recognition dependency.

## Why ComfyUI

ComfyUI officially supports workflow submission through `/prompt`, execution
tracking through `/history` or WebSocket messages, input upload, and output
retrieval. Keeping the GPU graph outside V3 lets the same gateway carry a
PhotoMaker, PuLID, InstantID, or future identity workflow without changing the
Central Brain or Project Mode.

Primary references:

- [ComfyUI server routes](https://docs.comfy.org/development/comfyui-server/comms_routes)
- [ComfyUI official repository](https://github.com/Comfy-Org/ComfyUI)
- [PhotoMaker official repository](https://github.com/TencentARC/PhotoMaker)
- [PhotoMaker V2 model card](https://huggingface.co/TencentARC/PhotoMaker-V2)
- [PuLID official repository](https://github.com/ToTheBeginning/PuLID)
- [InstantID official repository](https://github.com/instantX-research/InstantID)

## Hard Gates

The service advertises `identity_conditioning=true` only when all checks pass:

1. The workflow JSON exists and contains `${prompt}` and `${reference_0}`.
2. The operator confirms that model and dependency licenses fit the deployment.
3. The operator confirms that the graph actually performs identity conditioning.
4. ComfyUI `/system_stats` is reachable.
5. Every workflow `class_type` exists in ComfyUI `/object_info`.

Identity-native local repair requires a separate repair workflow and separate
operator confirmation. A generic mask graph must not be marked identity-native.

## Run

```powershell
Copy-Item .env.example .env
docker compose -f docker-compose.identity-sidecar.yml up --build
```

Copy a reviewed API-format workflow to `workflows/identity.json`, then update the
three confirmation flags in `.env`. Keep the API bound to loopback or a private
network and place TLS/authentication at the ingress when remote.

There is intentionally no production Alchemy configuration. Run the service
only in an isolated research environment with synthetic or explicitly approved
test assets.

## Storage

The gateway writes request files only to a request-scoped temporary directory
and removes it after completion. Standard ComfyUI uploads are stored in its
input volume; production must use an ephemeral volume or a TTL cleanup policy.
No face embeddings are created or persisted by this gateway.

## Verify

```powershell
$env:PYTHONPATH = (Resolve-Path .).Path
python -m pytest tests -q
python tools/certify.py --endpoint http://127.0.0.1:8098 --api-key <key> `
  --reference D:\path\portrait-front.png --output-dir D:\identity-certification
```

The certifier runs a five-view matrix and writes images plus `report.json`. It
uses V3's local SFace metric when the model files are available; otherwise it
marks the objective identity metric unavailable and does not claim acceptance.
