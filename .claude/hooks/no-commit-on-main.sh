#!/usr/bin/env bash
# Block `git commit` on main so issue work always lands on a reviewable branch.
# Called by Claude Code (PreToolUse on Bash, JSON on stdin). Commits you run
# yourself outside Claude Code are not affected.
set -eu

command="$(jq -r '.tool_input.command // empty' 2>/dev/null || true)"
# git, optionally with -C <dir> or other leading options, then the commit subcommand
if ! printf '%s' "${command}" |
    grep -Eq '(^|[^[:alnum:]_.-])git([[:space:]]+(-C[[:space:]]+[^[:space:]]+|-[^[:space:]]+))*[[:space:]]+commit([[:space:]]|$)'; then
    exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
branch="$(git -C "${PROJECT_DIR}" branch --show-current 2>/dev/null || true)"
case "${branch}" in
    main | master) ;;
    *) exit 0 ;;
esac

reason="Committing on ${branch} is blocked. Create a branch for the issue first, \
e.g. git switch -c enhancement/<issue-number>-<short-name>, then commit there \
(see \"Working on Issues\" in AGENTS.md)."
jq -n --arg reason "${reason}" '{
    hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: $reason
    }
}'
