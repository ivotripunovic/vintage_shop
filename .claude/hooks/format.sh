#!/usr/bin/env bash
# Format a .py file with isort + black after Edit/Write.
# Called by Claude Code (PostToolUse, JSON on stdin) and opencode
# (.opencode/plugins/venv-format.ts, file path as $1).
set -eu

file="${1:-}"
if [ -z "${file}" ]; then
    file="$(jq -r '.tool_input.file_path // empty' 2>/dev/null || true)"
fi
case "${file}" in
    *.py) ;;
    *) exit 0 ;;
esac
[ -f "${file}" ] || exit 0

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
# Never fail the agent's edit: a file black can't parse just stays unformatted.
cd "${PROJECT_DIR}" || exit 0
venv/bin/isort -q "${file}" || true
venv/bin/black -q "${file}" || true
exit 0
