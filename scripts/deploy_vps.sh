#!/usr/bin/env bash
set -Eeuo pipefail

REPO_URL="${REPO_URL:-https://github.com/meta-xucong/alchemy-media-agent.git}"
DEPLOY_DIR="${DEPLOY_DIR:-/opt/alchemy-media-agent}"
APP_PORT="${APP_PORT:-8017}"
LOCAL_MODE=0
SKIP_ENV=0
INSTALL_DOCKER=1

usage() {
  cat <<'USAGE'
Usage:
  scripts/deploy_vps.sh [--local] [--dir PATH] [--repo URL] [--skip-env] [--no-install-docker]

Environment:
  OPENAI_API_KEY             Required unless --skip-env is used
  ANTHROPIC_AUTH_TOKEN       Required unless --skip-env is used
  GITHUB_TOKEN               Optional for cloning this private repo from a fresh VPS
  APP_PORT                   Host port, defaults to 8017
  DEPLOY_DIR                 Deploy directory, defaults to /opt/alchemy-media-agent
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --local)
      LOCAL_MODE=1
      shift
      ;;
    --dir)
      DEPLOY_DIR="$2"
      shift 2
      ;;
    --repo)
      REPO_URL="$2"
      shift 2
      ;;
    --skip-env)
      SKIP_ENV=1
      shift
      ;;
    --no-install-docker)
      INSTALL_DOCKER=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

run_as_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    echo "Need root privileges for: $*" >&2
    exit 1
  fi
}

ensure_command() {
  local name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    return 1
  fi
}

install_docker_if_needed() {
  if ensure_command docker && docker compose version >/dev/null 2>&1; then
    return
  fi
  if [[ "${INSTALL_DOCKER}" != "1" ]]; then
    echo "Docker with Compose plugin is required." >&2
    exit 1
  fi
  if ! ensure_command apt-get; then
    echo "Auto-install only supports apt-based Linux. Install Docker and rerun." >&2
    exit 1
  fi
  run_as_root apt-get update
  run_as_root apt-get install -y ca-certificates curl git docker.io docker-compose-plugin
  run_as_root systemctl enable --now docker || true
}

ensure_deploy_tools() {
  local missing=()
  for tool in git curl; do
    if ! ensure_command "${tool}"; then
      missing+=("${tool}")
    fi
  done
  if [[ "${#missing[@]}" -eq 0 ]]; then
    return
  fi
  if ! ensure_command apt-get; then
    echo "Missing required tools: ${missing[*]}. Install them and rerun." >&2
    exit 1
  fi
  run_as_root apt-get update
  run_as_root apt-get install -y "${missing[@]}"
}

git_with_auth() {
  if [[ -n "${GITHUB_TOKEN:-}" && "${REPO_URL}" == https://github.com/* ]]; then
    git -c "http.https://github.com/.extraheader=AUTHORIZATION: bearer ${GITHUB_TOKEN}" "$@"
  else
    git "$@"
  fi
}

sync_repo() {
  if [[ "${LOCAL_MODE}" == "1" ]]; then
    DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    return
  fi

  if [[ -d "${DEPLOY_DIR}/.git" ]]; then
    git_with_auth -C "${DEPLOY_DIR}" fetch --prune origin
    git -C "${DEPLOY_DIR}" reset --hard origin/main
    return
  fi

  run_as_root mkdir -p "${DEPLOY_DIR}"
  if [[ ! -w "${DEPLOY_DIR}" ]]; then
    run_as_root chown -R "$(id -u):$(id -g)" "${DEPLOY_DIR}"
  fi
  git_with_auth clone "${REPO_URL}" "${DEPLOY_DIR}"
}

write_env_file() {
  if [[ "${SKIP_ENV}" == "1" ]]; then
    return
  fi
  if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    echo "OPENAI_API_KEY is required. Pass it as an environment variable or use --skip-env with an existing src_skeleton/.env." >&2
    exit 1
  fi
  if [[ -z "${ANTHROPIC_AUTH_TOKEN:-}" ]]; then
    echo "ANTHROPIC_AUTH_TOKEN is required. Pass it as an environment variable or use --skip-env with an existing src_skeleton/.env." >&2
    exit 1
  fi

  umask 077
  cat > "${DEPLOY_DIR}/src_skeleton/.env" <<EOF
MEDIA_AGENT_MODE=live
MOCK_IMAGE_PROVIDER_ENABLED=false
ORCHESTRATION_MODE=runtime_first

DEFAULT_IMAGE_PROVIDER=${DEFAULT_IMAGE_PROVIDER:-openai_gpt_image}
DEFAULT_IMAGE_MODEL=${DEFAULT_IMAGE_MODEL:-gpt-image-2}
OPENAI_IMAGE_MODEL=${OPENAI_IMAGE_MODEL:-gpt-image-2}
GEMINI_IMAGE_MODEL=${GEMINI_IMAGE_MODEL:-gemini-3.1-flash-image}
GEMINI_IMAGE_BASE_URL=${GEMINI_IMAGE_BASE_URL:-}

DEFAULT_LLM_PROVIDER=${DEFAULT_LLM_PROVIDER:-anthropic}
DEFAULT_LLM_MODEL=${DEFAULT_LLM_MODEL:-kimi-for-coding}
BACKUP_LLM_PROVIDER=${BACKUP_LLM_PROVIDER:-openai}
BACKUP_LLM_MODEL=${BACKUP_LLM_MODEL:-gpt-5.5}
OPENAI_LLM_MODEL=${OPENAI_LLM_MODEL:-gpt-5.5}
KIMI_LLM_MODEL=${KIMI_LLM_MODEL:-kimi-for-coding}
LLM_PROMPT_PLANNING_ENABLED=${LLM_PROMPT_PLANNING_ENABLED:-true}
IMAGE_WORK_INTENSITY=${IMAGE_WORK_INTENSITY:-atelier}

DEFAULT_VIDEO_PROVIDER=${DEFAULT_VIDEO_PROVIDER:-seedance}

OPENAI_API_KEY=${OPENAI_API_KEY}
OPENAI_BASE_URL=${OPENAI_BASE_URL:-https://aiself.vip/v1}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
ANTHROPIC_AUTH_TOKEN=${ANTHROPIC_AUTH_TOKEN}
ANTHROPIC_BASE_URL=${ANTHROPIC_BASE_URL:-https://aiself.vip}
GEMINI_IMAGE_API_KEY=${GEMINI_IMAGE_API_KEY:-}
BYTEPLUS_API_KEY=${BYTEPLUS_API_KEY:-}

MEDIA_STORAGE_ROOT=.media_storage
EOF
}

start_stack() {
  cd "${DEPLOY_DIR}"
  APP_PORT="${APP_PORT}" docker compose up -d --build
}

health_check() {
  local url="http://127.0.0.1:${APP_PORT}/v1/providers"
  for _ in $(seq 1 30); do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      echo "Alchemy Media Agent is running: http://127.0.0.1:${APP_PORT}/"
      return
    fi
    sleep 2
  done
  echo "Service did not pass health check. Recent logs:" >&2
  docker compose -f "${DEPLOY_DIR}/docker-compose.yml" logs --tail=80 alchemy-media-agent >&2 || true
  exit 1
}

install_docker_if_needed
ensure_deploy_tools
sync_repo
write_env_file
start_stack
health_check
