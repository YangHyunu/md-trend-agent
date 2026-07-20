#!/usr/bin/env bash
# SessionStart hook — delivers "MEMORY.md is write-protected" to worktree sessions.
#
# Why a hook: CLAUDE.md is a per-checkout file, so a worktree on an old branch
# may see a stale version. A hook runs at the machine level, so it reaches
# every session regardless of branch.
#
# The rule body is not copy-pasted here — the single source of truth is
# CLAUDE.md §6; copies drift into two versions. This hook only fires a pointer.
#
# Wiring: this project's .claude/settings.json under hooks.SessionStart
# (project-local, gitignored — see .gitignore)
set -uo pipefail

MAIN_REPO="/Users/yanghyeon-u/Desktop/Claude-BZRR-SUB"

# The hook must fail silently — it fires on every session start, so any noise
# here is seen by every session.
command -v git >/dev/null 2>&1 || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

# -P: resolve symlinks. Without it, path comparison mismatches and silently no-ops.
abs() { (cd "$1" 2>/dev/null && pwd -P); }

git_dir=$(git rev-parse --git-dir 2>/dev/null) || exit 0
common_dir=$(git rev-parse --git-common-dir 2>/dev/null) || exit 0
git_dir=$(abs "$git_dir") || exit 0
common_dir=$(abs "$common_dir") || exit 0
[ -n "$git_dir" ] && [ -n "$common_dir" ] || exit 0

# In the main checkout, both paths match → not a worktree, stay silent.
[ "$git_dir" != "$common_dir" ] || exit 0

# A worktree of a different repo isn't covered by this rule → stay silent.
[ "$common_dir" = "$(abs "$MAIN_REPO")/.git" ] || exit 0

branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "?")

python3 - "$branch" "$MAIN_REPO" <<'PY'
import json, sys

branch, main_repo = sys.argv[1], sys.argv[2]
msg = (
    f"[Worktree session — branch {branch}]\n"
    "MEMORY.md (global auto-memory) is **read-only in worktrees**. No edits, "
    "additions, or deletions. Only for a genuinely major change or a completed "
    "feature may you propose a change to the owner (no writing before approval). "
    "Writing is done by the main checkout session only — a single writer avoids "
    "breakage without needing a lock.\n"
    f"Source of truth = {main_repo}/CLAUDE.md §6 — this worktree's CLAUDE.md may "
    "be stale, so read that path directly.\n"
    "Session handoffs go in docs/agent-logs/<worktree>-<date>-<topic>--handoff.md. "
    "Commit only when the owner instructs it. Do not use a root-level HANDOFF.md."
)
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": msg,
    }
}, ensure_ascii=False))
PY
