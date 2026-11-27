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

active_release="$(realpath /opt/alchemy-media-agent)"
candidate=/opt/alchemy-media-agent-releases/doc276-277-90a897bacee6
v1_media="$(docker inspect alchemy-media-agent --format '{{range .Mounts}}{{if eq .Destination "/app/.media_storage"}}{{.Source}}{{end}}{{end}}')"
v2_data="$(awk -F= '$1 == "V2_DATA_DIR" {sub(/^[^=]*=/, ""); print; exit}' /etc/alchemy/alchemy-v2.env)"
v2_data="${v2_data:-/var/lib/alchemy/v2/storage}"
v2_history="$(awk -F= '$1 == "V2_IMAGE_HISTORY_PATH" {sub(/^[^=]*=/, ""); print; exit}' /etc/alchemy/alchemy-v2.env)"
v2_history="${v2_history:-$v2_data/image_history.jsonl}"
bridge_paths="$(python3 "$candidate/scripts/vps_cutover_guard.py" verify-bridge-storage-configuration \
  --v1-environment "$candidate/src_skeleton/.env" --v2-environment /etc/alchemy/alchemy-v2.env \
  --release-root "$active_release" --release-root "$candidate")"
bridge_control="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["control_path"])' <<<"$bridge_paths")"
bridge_state="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["state_root"])' <<<"$bridge_paths")"
bridge_sources=(--source "$bridge_control")
if [[ -d "$v2_data/render_bridge_primary" ]]; then
  while IFS= read -r -d '' path; do bridge_sources+=(--source "$path"); done < <(find "$v2_data/render_bridge_primary" -type f -name '*.json' -print0)
fi
inventory=/var/backups/alchemy/pr29-90a897bacee6-20261127T164803Z/database-inventory.bin
if [[ ! -f "$inventory" ]]; then
  inventory=<(for root in "$v1_media" "$v2_data" "$(dirname "$v2_history")" "$bridge_state"; do
    find "$root" -type f \( -name '*.sqlite3' -o -name '*.sqlite' -o -name '*.db' \) -print0
  done | sort -zu)
fi
printf 'NEXT_CUTOVER_ESTIMATE='
python3 "$candidate/scripts/vps_cutover_guard.py" estimate-space \
  --inventory-file "$inventory" --reserve-bytes 1073741824 \
  --source "$v1_media/history/outputs.jsonl" --source "$v1_media/favorites/image_favorites.json" \
  --source "$v2_history" --source "$v2_data/image_favorites.json" "${bridge_sources[@]}"
printf '%s\n' 'INACTIVE_RUNTIME_BYTES'
du -x -B1 -d1 /opt/alchemy-media-agent-releases | sort -n | tail -n 19
