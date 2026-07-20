# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## Isolate Large Tool Output
Any tool that can return >20k chars per call (browser/DOM dumps, large file
reads, broad greps, screenshots) runs inside a subagent that returns only the
distilled findings, never the raw dump — raw dumps landing in the main context
degrade later reasoning. Prefer targeted reads (get_page_text / find / filtered
read) over full-page dumps.

## Parallel Subagents
- Scope every subagent read to specific dirs/files; never hand it a whole large
  tree.
- Don't fan out multiple heavy agents at once if any one has large scope.
- After interrupting one branch of a parallel batch, don't type "Continue" —
  name the dropped task explicitly (e.g. "re-run the frontend audit").
  Interrupts don't auto-recover.

## Session Checkpoint
On long sessions (many hundreds of turns / large token count), periodically
write key decisions and findings to memory, so a fresh session resumes cheap
instead of re-deriving everything.

## Diagnose vs. Act
Scan / analysis / trace tasks report only; never auto-apply. File edits require
owner approval. Author and evaluator are separate passes — don't self-approve a
change in the same breath you made it.

## UI / Visual Changes
When there's a layout or visual choice, render the options side-by-side first
and let the owner pick. Don't change visuals on a silent assumption — show,
then pick, then change. Record the chosen option and the reason in the relevant
spec or design doc.

## Interpreting Source Material
Don't reinterpret specific words, terms, or values in the source material, or
swap them for a "more plausible" meaning. Treat them exactly as written. When
something is ambiguous, ask rather than filling the gap with a guess, and don't
supply unstated assumptions that make a request seem safer or easier than it
was written (e.g. if the user wrote `auth_token`, don't silently call it
`access_token`).

## Implementation Gate
After the owner asks to BUILD/IMPLEMENT (e.g. "MVP 구현하자"), do not keep
producing docs/specs in place of code. No new `docs:`-only commit is allowed
after an implementation request until a corresponding code file is committed.
If you catch yourself writing another spec, stop and ask: "is this doc required
to write the code, or is it deferring the code?" One canonical spec wins — flag
and defer overlapping spec docs rather than spawning new ones.

## 6. Session Continuity Protocol

> This project has no git repo yet — no worktrees exist, so the rules below are
> currently dormant. They activate once `git init` is run and worktrees are
> actually created. This is pre-provisioning only.

1. **MEMORY.md has a single writer — only the main session writes it.**
   - **Main checkout session** (`/Users/yanghyeon-u/Desktop/Claude-BZRR-SUB`): **may write**
     to the global auto-memory
     (`~/.claude/projects/-Users-yanghyeon-u-Desktop-Claude-BZRR-SUB/memory/`).
     No approval wait needed.
   - **Worktree sessions** (multiple may exist at once, per branch or purpose):
     **read-only.** No edits, additions, or deletions. Only for genuinely major
     changes or a completed feature may it **propose** a change to the owner
     (no writing before approval).
   - **Why this line**: the auto-memory path is a slug derived from the
     repo's absolute path — main and every worktree share the **same
     directory** (pattern confirmed empirically in BZRR_CUBE; this project
     uses the same mechanism). Shared mutable file + no locking = parallel
     worktrees writing at once collide. Main is the only single instance, so
     **narrowing the writer to main alone removes the collision without
     needing a lock.** The goal isn't prohibition — it's a single writer.
   - The SessionStart hook (`ops/hooks/worktree_memory_guard.sh`, wired in
     `.claude/settings.json`) fires the warning/read-only notice only in
     worktrees — main is not a target.

2. **Session handoffs go in `docs/agent-logs/`.**
   - Filename: `docs/agent-logs/<worktree>-<date>-<topic>--handoff.md`
   - Commit only when the owner instructs it.
   - Do not use a single root-level `HANDOFF.md` — that structure diverges
     per worktree and easily contaminates main, so it's excluded from the
     start.

3. **This §6 is the single source of truth.** Don't copy-paste the rule body
   into worktree copies, hooks, or other docs — copies drift into two
   versions. Worktree sessions receive a pointer from the SessionStart hook
   and read this file's absolute path directly.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
