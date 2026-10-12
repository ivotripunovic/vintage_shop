#!/usr/bin/env bash
# SessionStart: activate the project venv for every Bash call in the session.
if [ -n "${CLAUDE_ENV_FILE:-}" ] && [ -f "${CLAUDE_PROJECT_DIR}/venv/bin/activate" ]; then
    echo "source \"${CLAUDE_PROJECT_DIR}/venv/bin/activate\"" >> "${CLAUDE_ENV_FILE}"
fi
exit 0
