# Amadeus Media Acceleration

## Goal

Use `vps-amadeus` as a high-bandwidth static media node for generated image downloads without changing the user-facing Alchemy domain or bypassing account checks.

## Runtime Model

1. The main Alchemy app remains the authority for authentication, account visibility, and V1/V2 business rules.
2. V1 and V2 download endpoints first run their existing output visibility checks.
3. If media acceleration is enabled and the local output file is inside the product's own output storage root, the endpoint returns a short-lived signed redirect to `ALCHEMY_MEDIA_BASE_URL`.
4. If acceleration is disabled, misconfigured, or the file path is not eligible, the endpoint falls back to the original local file response.
5. The media node serves `/dl/...` only when Nginx `secure_link` validates the signature and expiration.

## V1/V2 Isolation

- V1 signs paths under its own `MEDIA_STORAGE_ROOT/generated_images`.
- V2 signs paths under its own `V2_STORAGE_DIR/outputs`.
- V2 does not call V1 routes, import V1 modules, or read V1 storage.
- The shared media node is a deployment target only; it is not a shared backend product.

## Environment

Set these on both V1 and V2 runtimes when enabling acceleration:

```env
ALCHEMY_MEDIA_ACCELERATION_ENABLED=true
ALCHEMY_MEDIA_BASE_URL=https://media.alchemy.aiself.vip
ALCHEMY_MEDIA_SIGNING_SECRET=<same secret as /etc/alchemy-media/secure_link_secret on media node>
ALCHEMY_MEDIA_URL_TTL_SECONDS=300
ALCHEMY_MEDIA_VERIFY_REMOTE_EXISTS=true
ALCHEMY_MEDIA_VERIFY_TIMEOUT_SECONDS=1.2
```

Defaults keep the feature disabled.
When remote verification is enabled, the app performs a short `HEAD` request against the signed media URL. If the media node does not have the file yet, the app serves the original local response so newly generated images do not fail during sync lag.

## VPS Layout

On `vps-amadeus`:

- Media root: `/srv/alchemy-media`
- Data disk: `/dev/vdb1` mounted by UUID to `/srv/alchemy-media`
- V1 files: `/srv/alchemy-media/v1/generated_images/...`
- V2 files: `/srv/alchemy-media/v2/outputs/...`
- Nginx site: `/etc/nginx/sites-available/alchemy-media-node`
- Signing secret: `/etc/alchemy-media/secure_link_secret`
- CORS: `/dl/` allows `https://alchemy.aiself.vip` so frontend blob downloads can follow the signed redirect.

On the main Alchemy VPS:

- Sync script: `/usr/local/bin/sync_alchemy_media_to_amadeus.sh`
- Systemd service: `alchemy-media-sync.service`
- Systemd timer: `alchemy-media-sync.timer`
- Sync interval: every 60 seconds

## Security Notes

- Unsigned media URLs return 403.
- Expired media URLs return 410.
- The media node does not expose directory listings.
- Sync SSH access uses a dedicated key restricted by source address and disables agent/X11/port forwarding and tty.
- No signing secret is committed to the repository.
