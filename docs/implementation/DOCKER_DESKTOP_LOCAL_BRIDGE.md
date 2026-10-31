# Docker Desktop to local Render Bridge

## Correction model

The Alchemy API container and the local Bridge run in different network namespaces. Inside the container, `127.0.0.1` points back to Alchemy, so it cannot reach the Windows Bridge listener. Docker Desktop's `host.docker.internal` relay reaches the Windows host, but the existing HTTP guard accepts only literal loopback names and rejects that local relay.

Keep the Bridge bound to Windows loopback. In this Windows/Docker Desktop runtime, a container request to `host.docker.internal:8798` was observed reaching that loopback listener. Accept `http://host.docker.internal:<port>` only when `ALCHEMY_RENDER_BRIDGE_ALLOW_HTTP_LOOPBACK=true`; continue rejecting other HTTP hosts and malformed ports.

## Runtime configuration

For Alchemy running in a Docker Desktop container, set its Bridge endpoint to `http://host.docker.internal:8798` and explicitly enable the loopback opt-in. Keep the Windows-hosted V2 process on `http://127.0.0.1:8798`. Both endpoints use the same workspace and source credential. Do not bind the Bridge API to `0.0.0.0` for this setup.
