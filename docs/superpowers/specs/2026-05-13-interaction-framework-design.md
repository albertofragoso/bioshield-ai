# Interaction Framework — Design Spec
**Date:** 2026-05-13  
**Status:** Approved — pending implementation plan  
**Scope:** User-level (~/.claude/) + project-level (.claude/) hybrid

---

## Context

Based on the Claude Code Insights report (2026-04-15 → 2026-05-13):
- 1,184 messages · 62 sessions · 57 commits · 23 days
- **Top friction:** Wrong Approach 26 events (41%), Buggy Code 24 events (38%)
- **Outcome:** Fully Achieved 50% · Dissatisfied 12.2%
- **Root causes:** session misalignment at start, premature "done" declarations, root cause skipping, CI failures discovered post-push

The framework targets a **~45% reduction in combined wrong_approach + buggy_code friction** and pushes Fully Achieved from 50% to ~68%.

---

## Architecture Overview

```
~/.claude/                          ← USER GLOBAL (all projects)
├── CLAUDE.md                       ← behavior rules: language, workflow, guards, refinement
├── settings.json                   ← SessionStart hook + destructive PreToolUse guard
├── skills/
│   ├── gotcha-review/SKILL.md      ← pre-implementation risk review (on-demand)
│   └── review-my-usage/SKILL.md   ← bi-weekly analysis cycle (on-demand)
└── framework/
    ├── current-gotchas.md          ← hot state: top-3 active gotchas (read every session)
    └── interaction-log.md          ← cold state: cycle history + metrics delta

.claude/                            ← PROJECT-SPECIFIC (BioShield + future projects)
├── settings.json                   ← pre-push CI gate hook (project CI matrix)
├── CLAUDE.md                       ← project conventions (unchanged)
└── skills/
    └── (no pre-pr skill — replaced by automatic hook)
```

**Split rationale:**
- User-level = *how you work with Claude* (language, gotchas, workflow rules). Stack-agnostic.
- Project-level = *how this code is validated* (ruff/mypy/pytest vs tsc/eslint/vitest). Stack-specific.

---

## Layer A — Immediate Environment

### `~/.claude/CLAUDE.md` — 5 new sections

```markdown
## Language & Communication
- Respond in Spanglish: natural mix of Spanish and English in the same response
- In brainstorming/design tasks: critical viability analysis BEFORE asking questions
- In design questions: always present alternatives with an explicit recommendation
- In multiple-choice questions: always list the recommended option first

## Git Workflow
- ALWAYS use git worktrees for feature work; never commit directly to main
- Before push: run the project's full CI matrix locally — all green
- After merge: delete feature branch and sync main

## Destructive Commands
- NEVER run rm -rf, force-push, or branch deletions without explicit confirmation in session
- For destructive ops: print the exact command and ask the user to run it manually

## Verification Before Fixes
- Before any fix or plan: two review rounds — first catches the obvious,
  second finds what the first missed (most gotchas live in the second pass)
- Before expanding data (categories, keywords, rules): verify they exist in the real codebase
- Do not claim side-effects (e.g., API costs) without checking for fallback paths in code

## Prompt Refinement
- When a prompt matches a known pitfall pattern (vague scope, missing workflow context,
  fix without root cause, missing session mode), propose a refined version BEFORE acting
  and wait for ✓/✗ confirmation
- Trigger patterns: "fix X", "arregla X", "haz X" without how/scope/validation context
- Do NOT trigger on prompts that already include workflow, scope, or validation criteria
- Refined version must incorporate: root cause first, validation criteria, correct workflow
```

### `~/.claude/settings.json` — additions

Add `UserPromptSubmit` hook and (if safety-gate.sh audit confirms gap) destructive `PreToolUse`:

```json
{
  "hooks": {
    "UserPromptSubmit": [{
      "hooks": [{
        "type": "command",
        "command": "cat ~/.claude/framework/current-gotchas.md 2>/dev/null"
      }]
    }],
    "SessionStart": [
      { "hooks": [{ "type": "command", "command": "\"/Users/albertofragoso/.claude/hooks/context-mode-cache-heal.mjs\"" }] },
      { "hooks": [{ "type": "command", "command": "cat ~/.claude/framework/current-gotchas.md 2>/dev/null" }] }
    ]
  }
}
```

**Hook audit required before adding:** inspect `scripts/hooks/safety-gate.sh` and `format.sh` to confirm gaps before duplicating behavior.

---

## Layer B — Bi-Weekly Review Cycle

### Trigger
Run `/review-my-usage` manually every ~15 days (or ~30 new sessions).

### Skill location
`~/.claude/skills/review-my-usage/SKILL.md`

### 4-Phase flow

**Phase 1 — Analyze**
- Read `~/.claude/usage-data/facets/*.json` (sessions since last cycle date in interaction-log.md)
- Read `~/.claude/usage-data/session-meta/*.json`
- Compute metrics from raw JSON keys: `friction_counts`, `outcome`, `user_satisfaction_counts`, `tool_errors`, `session_type`
- Compare against previous cycle entry in `interaction-log.md`
- Identify: what improved · what persists · what is new

**Phase 2 — Propose** *(two internal review rounds before presenting)*
- Draft targeted diffs for `~/.claude/CLAUDE.md`
- Draft updates to skills if a new pattern justifies it
- New top-3 gotchas for `current-gotchas.md` — both Claude's failure modes AND user's own pitfall patterns
- Second internal review: check for gotchas in the proposals themselves
- Present report + diffs to user

**Phase 3 — Approve** *(pause — wait for user OK)*
- Delta table: Cycle N-1 vs Cycle N metrics
- List of proposed changes with data-backed justification
- User approves, rejects, or adjusts each change individually

**Phase 4 — Apply**
- Apply approved changes to `~/.claude/CLAUDE.md` and skills
- Update `~/.claude/framework/current-gotchas.md`
- Append new cycle entry to `interaction-log.md`
- Commit: `chore(framework): bi-weekly interaction review YYYY-MM-DD`

### State schemas

**`~/.claude/framework/current-gotchas.md`** (hot state — injected every session):
```markdown
<!-- Updated: YYYY-MM-DD | Cycle: N -->
**Active gotchas — both sides:**

Claude watch-outs:
1. [most frequent Claude failure mode this cycle]
2. [second most frequent]
3. [emerging pattern or persistent issue]

Your reminders:
1. [your most costly pitfall this cycle]
2. [second most costly]
3. [session-start context to include]
```

**`~/.claude/framework/interaction-log.md`** (cold state — versioned history):
```markdown
## YYYY-MM-DD | Cycle N
- Sessions analyzed: N | Period: YYYY-MM-DD → YYYY-MM-DD
- wrong_approach: N (%) | buggy_code: N (%) | fully_achieved: %
- dissatisfied: % | command_failed: N
- Changes applied: [list]
- Next review: ~YYYY-MM-DD

## YYYY-MM-DD | Cycle N-1
...
```

---

## Layer C — In-Session Interventions

### 1. SessionStart gotcha injection (automatic)
Hook in `~/.claude/settings.json` reads `current-gotchas.md` and injects as context before the first message. Silent. Cross-project.

### 2. Prompt Refinement (automatic — requires ✓/✗)
Behavioral rule in `~/.claude/CLAUDE.md`. Activates when prompt matches pitfall pattern. Proposes refined version, waits for confirmation before acting. No skill invocation needed.

### 3. Pre-push CI gate (automatic — blocks push)

**Location:** `.claude/settings.json` per project + `scripts/hooks/pre-push-ci.sh`

**Mechanism:** `PreToolUse` hook on `Bash` tool. Script reads `$CLAUDE_TOOL_INPUT`, checks if command contains `git push`. If yes, runs CI matrix. Exit code 2 blocks the push.

**BioShield implementation:**
```bash
#!/bin/bash
COMMAND=$(echo "$CLAUDE_TOOL_INPUT" | python3 -c \
  "import json,sys; print(json.load(sys.stdin).get('command',''))" 2>/dev/null)
[[ "$COMMAND" != *"git push"* ]] && exit 0

echo "Running pre-push CI checks..."
ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"

ruff format --check . 2>&1 || { echo "ruff format failed"; exit 2; }
ruff check .          2>&1 || { echo "ruff lint failed";   exit 2; }
mypy .                2>&1 || { echo "mypy failed";         exit 2; }
pytest                2>&1 || { echo "pytest failed";       exit 2; }

echo "All checks passed"
exit 0
```

**Convention for new projects:** each project creates its own `scripts/hooks/pre-push-ci.sh` with its stack-specific matrix (e.g., `tsc --noEmit + eslint + vitest` for Next.js).

### 4. `/gotcha-review` skill (on-demand)

**Location:** `~/.claude/skills/gotcha-review/SKILL.md`  
**Trigger:** Invoke before any non-trivial implementation.

```
1. Read current-gotchas.md — apply active pitfall patterns
2. First review: list 3-5 risks (data assumptions, deps, race conditions, env issues)
3. Verify each risk against real codebase — no assumptions
4. Second review: what did the first pass miss?
5. Deliver: confirmed / invalidated / unknown risks + revised plan
6. ⏸ Wait for approval before implementing
```

### 5. `/review-my-usage` skill (on-demand, ~15 days)
Described fully in Layer B.

---

## Intervention modes — summary

| Piece | Mode | Location |
|---|---|---|
| SessionStart gotcha injection | Automatic | `~/.claude/settings.json` |
| Prompt Refinement detection | Automatic (asks ✓/✗) | `~/.claude/CLAUDE.md` |
| Pre-push CI gate | Automatic (blocks push) | `.claude/settings.json` per project |
| `/gotcha-review` | On-demand | `~/.claude/skills/` |
| `/review-my-usage` | On-demand (~15 days) | `~/.claude/skills/` |

---

## Learning loop

```
SessionStart → inject active gotchas as context
      ↓
User writes prompt → pitfall detection → refinement if triggered (✓/✗)
      ↓
Pre-implementation → /gotcha-review (two-pass review)
      ↓
Pre-push → CI gate blocks push until all green
      ↓
Every ~15 days → /review-my-usage updates gotchas + CLAUDE.md
      ↑___________________________________________________↑
              learning propagates to next cycle
```

---

## Projected metrics improvement

| Metric | Baseline | Projected |
|---|---|---|
| Wrong Approach friction | 26 events (41%) | ~13 events (-50%) |
| Buggy Code friction | 24 events (38%) | ~14 events (-40%) |
| User Rejected Action | 5 events (8%) | ~1 event (-80%) |
| Misunderstood Request | 5 events (8%) | ~2 events (-60%) |
| Fully Achieved sessions | 50% (21/42) | ~68% (+18pp) |
| Partially/Not Achieved | 7% (3/42) | ~2% (-5pp) |
| Dissatisfied turns | 12.2% (17/139) | ~6% (-6pp) |
| Command Failed errors | 98 | ~70 (-28%) |
| Fix-up commits post-PR | ~4 sessions affected | ~1 session (-75%) |

---

## Open items before implementation

1. **Audit (first implementation step):** inspect `scripts/hooks/safety-gate.sh`, `format.sh`, `lint.sh` — determine gaps before adding new hooks; do not duplicate existing behavior
2. **`/insights` command:** report regeneration is NOT scriptable via CLI — `/review-my-usage` reads `~/.claude/usage-data/facets/*.json` directly
3. **`~/.claude/CLAUDE.md`:** verify if file exists and has conflicting rules before appending
4. **Cycle 1 baseline:** `interaction-log.md` must be seeded with current report metrics as the baseline before first `/review-my-usage` run
