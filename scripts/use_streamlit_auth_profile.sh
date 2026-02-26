#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-}"
STREAMLIT_DIR=".streamlit"
ACTIVE_SECRETS="${STREAMLIT_DIR}/secrets.toml"
LOCAL_PROFILE="${STREAMLIT_DIR}/secrets.local.toml"
TRAEFIK_PROFILE="${STREAMLIT_DIR}/secrets.traefik.toml"

if [[ -z "${PROFILE}" ]]; then
  echo "Usage: $0 <local|traefik>" >&2
  exit 1
fi

if [[ "${PROFILE}" != "local" && "${PROFILE}" != "traefik" ]]; then
  echo "Invalid profile '${PROFILE}'. Expected 'local' or 'traefik'." >&2
  exit 1
fi

mkdir -p "${STREAMLIT_DIR}"

if [[ ! -f "${LOCAL_PROFILE}" || ! -f "${TRAEFIK_PROFILE}" ]]; then
  if [[ ! -f "${ACTIVE_SECRETS}" ]]; then
    cat >&2 <<'EOF'
Missing .streamlit/secrets.toml.
Create it first, then re-run:
  cp .streamlit/secrets.toml .streamlit/secrets.local.toml
  cp .streamlit/secrets.toml .streamlit/secrets.traefik.toml
EOF
    exit 1
  fi

  cp "${ACTIVE_SECRETS}" "${LOCAL_PROFILE}"
  cp "${ACTIVE_SECRETS}" "${TRAEFIK_PROFILE}"

  # Local Streamlit server callback.
  sed -E -i.bak 's#^redirect_uri[[:space:]]*=.*#redirect_uri = "http://localhost:8501/oauth2callback"#' "${LOCAL_PROFILE}"
  # Traefik app path callback.
  sed -E -i.bak 's#^redirect_uri[[:space:]]*=.*#redirect_uri = "http://localhost/app/oauth2callback"#' "${TRAEFIK_PROFILE}"
  rm -f "${LOCAL_PROFILE}.bak" "${TRAEFIK_PROFILE}.bak"
fi

if [[ "${PROFILE}" == "local" ]]; then
  cp "${LOCAL_PROFILE}" "${ACTIVE_SECRETS}"
  echo "Active Streamlit auth profile: local (http://localhost:8501/oauth2callback)"
else
  cp "${TRAEFIK_PROFILE}" "${ACTIVE_SECRETS}"
  echo "Active Streamlit auth profile: traefik (http://localhost/app/oauth2callback)"
fi
