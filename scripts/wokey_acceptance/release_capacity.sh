set -euo pipefail
printf 'ACTIVE_SHA='
git -C "$(realpath /opt/alchemy-media-agent)" rev-parse HEAD
printf 'ROLLBACK_SHA='
docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' alchemy-media-agent:rollback-pr29
df -PB1 /var/backups/alchemy /var/lib/docker /var/lib/alchemy /opt/alchemy-media-agent-releases | sed -n '1,5p'
printf '%s\n' 'ALCHEMY_IMAGES'
docker image ls --no-trunc --filter reference='alchemy-media-agent:*' --format '{{.Tag}} {{.ID}} {{.Size}}'
printf '%s\n' 'ALCHEMY_SNAPSHOT_BYTES'
du -x -B1 -d1 /var/backups/alchemy | sort -n | tail -n 12
printf '%s\n' 'DOCKER_TEMPORARY_SPACE'
docker system df --format '{{if eq .Type "Build Cache"}}{{.Type}} {{.Size}} {{.Reclaimable}}{{end}}'
