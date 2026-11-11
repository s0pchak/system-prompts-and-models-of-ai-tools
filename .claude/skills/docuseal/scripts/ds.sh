#!/usr/bin/env bash
# Thin wrapper around the DocuSeal REST API.
#
#   ds.sh METHOD PATH [BODY]
#
#   METHOD  GET | POST | PUT | DELETE
#   PATH    API path incl. query string, e.g. /templates?q=NDA&limit=10
#   BODY    optional: a path to a JSON file, or "-" to read JSON from stdin
#
# Env:
#   DOCUSEAL_API_KEY  (required) API key from the DocuSeal console -> API
#   DOCUSEAL_API_URL  (optional) https://api.docuseal.com (default) or https://api.docuseal.eu
set -euo pipefail

if [[ $# -lt 2 ]]; then
  sed -n '2,13p' "$0" >&2
  exit 2
fi

: "${DOCUSEAL_API_KEY:?DOCUSEAL_API_KEY is not set. Export it in your shell profile (see SKILL.md).}"
base="${DOCUSEAL_API_URL:-https://api.docuseal.com}"
method="$1"; path="$2"; body="${3:-}"

args=(-sS -X "$method" "${base%/}${path}"
      -H "X-Auth-Token: ${DOCUSEAL_API_KEY}"
      -H "Accept: application/json"
      -w '\n%{http_code}')
if [[ -n "$body" ]]; then
  args+=(-H "Content-Type: application/json" --data-binary "@${body}")
fi

out="$(curl "${args[@]}")"
code="${out##*$'\n'}"
resp="${out%$'\n'*}"

if command -v jq >/dev/null 2>&1 && [[ -n "$resp" ]]; then
  printf '%s\n' "$resp" | jq . 2>/dev/null || printf '%s\n' "$resp"
else
  printf '%s\n' "$resp"
fi

if [[ "$code" -ge 400 ]]; then
  echo "HTTP $code" >&2
  exit 1
fi
