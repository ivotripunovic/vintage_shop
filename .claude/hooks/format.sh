#!/usr/bin/env bash
# PostToolUse (Edit|Write): run isort + black on the edited Python file.
file="$(jq -r '.tool_input.file_path // empty')"
case "${file}" in
    *.py) ;;
    *) exit 0 ;;
esac
[ -f "${file}" ] || exit 0
cd "${CLAUDE_PROJECT_DIR}" || exit 0
venv/bin/isort -q "${file}" && venv/bin/black -q "${file}"
exit 0
