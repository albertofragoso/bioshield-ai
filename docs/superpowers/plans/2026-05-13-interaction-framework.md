# Interaction Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy a three-layer framework that reduces wrong_approach + buggy_code friction by ~45% through automatic gotcha injection, prompt refinement detection, a pre-push CI gate, and a bi-weekly self-improving review cycle.

**Architecture:** User-level artifacts (`~/.claude/`) apply to all projects; project-level artifacts (`.claude/`, `scripts/hooks/`) are BioShield-specific. State lives in two files: `current-gotchas.md` (hot, read every session) and `interaction-log.md` (cold, versioned cycle history). The `/review-my-usage` skill updates both after each cycle.

**Tech Stack:** Bash hooks, Claude Code SKILL.md format, JSON (facets data), Markdown state files, Python 3 (ruff/mypy/pytest — BioShield backend)

---

## Pre-flight: Audit findings (already done — no action needed)

- `safety-gate.sh` already blocks `rm -rf`, `git push --force`, `git reset --hard` → no new PreToolUse hook for destructive commands
- `format.sh` already runs `ruff format` + `prettier` on every Write/Edit → no new PostToolUse hook
- `lint.sh` already runs `ruff check --fix` + `eslint` on every Write/Edit → no new PostToolUse hook
- `type-check.sh` runs `mypy` on Stop but always exits 0 (informational only) → pre-push-ci.sh must block
- `~/.claude/CLAUDE.md` exists but is empty → safe to write fresh content
- `~/.claude/skills/` does not exist → needs `mkdir -p`

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `~/.claude/CLAUDE.md` | Create content | 5 behavioral rule sections |
| `~/.claude/settings.json` | Modify | Add SessionStart gotcha hook + UserPromptSubmit |
| `~/.claude/framework/current-gotchas.md` | Create | Hot state — top-3 gotchas, read every session |
| `~/.claude/framework/interaction-log.md` | Create | Cold state — cycle history with metrics |
| `~/.claude/skills/gotcha-review/SKILL.md` | Create | On-demand pre-implementation risk review |
| `~/.claude/skills/review-my-usage/SKILL.md` | Create | On-demand bi-weekly analysis cycle |
| `scripts/hooks/pre-push-ci.sh` | Create | Blocks `git push` until CI is green |
| `.claude/settings.json` | Modify | Add pre-push PreToolUse hook entry |

---

## Task 1: User-level environment — `~/.claude/CLAUDE.md`

**Files:**
- Write: `~/.claude/CLAUDE.md`

- [ ] **Step 1: Write CLAUDE.md with the 5 behavioral sections**

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
  and wait for confirmation
- Trigger patterns: "fix X", "arregla X", "haz X" without how/scope/validation context
- Do NOT trigger on prompts that already include workflow, scope, or validation criteria
- Refined version must incorporate: root cause first, validation criteria, correct workflow
```

- [ ] **Step 2: Verify file is non-empty**

```bash
wc -l ~/.claude/CLAUDE.md
```

Expected: at least 25 lines.

- [ ] **Step 3: Verify and confirm**

```bash
echo "Task 1 complete — ~/.claude/CLAUDE.md written"
wc -l ~/.claude/CLAUDE.md
```

Expected: 30+ lines.

---

## Task 2: User-level settings — gotcha injection hooks

**Files:**
- Modify: `~/.claude/settings.json`

The current `settings.json` has one `SessionStart` entry. We add a second `SessionStart` entry and a new `UserPromptSubmit` section. The `UserPromptSubmit` hook fires on every message — output is injected as a system reminder, keeping gotchas fresh in long sessions.

- [ ] **Step 1: Read current settings.json to confirm structure**

```bash
cat ~/.claude/settings.json
```

Expected: JSON object with `hooks.SessionStart` containing one entry for `context-mode-cache-heal.mjs`.

- [ ] **Step 2: Write updated settings.json**

Replace the `hooks` section only — preserve all other keys (`model`, `statusLine`, `enabledPlugins`, `extraKnownMarketplaces`, `effortLevel`, `theme`):

```json
{
  "model": "sonnet",
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"/Users/albertofragoso/.claude/hooks/context-mode-cache-heal.mjs\""
          }
        ]
      },
      {
        "hooks": [
          {
            "type": "command",
            "command": "cat ~/.claude/framework/current-gotchas.md 2>/dev/null"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "cat ~/.claude/framework/current-gotchas.md 2>/dev/null"
          }
        ]
      }
    ]
  },
  "statusLine": {
    "type": "command",
    "command": "bash /Users/albertofragoso/.claude/statusline-command.sh"
  },
  "enabledPlugins": {
    "frontend-design@claude-plugins-official": true,
    "superpowers@claude-plugins-official": true,
    "skill-creator@claude-plugins-official": true,
    "context-mode@context-mode": true
  },
  "extraKnownMarketplaces": {
    "context-mode": {
      "source": {
        "source": "github",
        "repo": "mksglu/context-mode"
      }
    },
    "thedotmack": {
      "source": {
        "source": "github",
        "repo": "thedotmack/claude-mem"
      }
    }
  },
  "effortLevel": "medium",
  "theme": "dark-daltonized"
}
```

- [ ] **Step 3: Validate JSON is well-formed**

```bash
python3 -c "import json; json.load(open(open('/dev/stdin').read().strip()))" <<< "~/.claude/settings.json" 2>/dev/null || python3 -m json.tool ~/.claude/settings.json > /dev/null && echo "JSON valid" || echo "JSON INVALID — fix before continuing"
```

Simpler check:

```bash
python3 -m json.tool ~/.claude/settings.json > /dev/null && echo "valid" || echo "INVALID"
```

Expected: `valid`

---

## Task 3: Framework state files — baseline for Cycle 1

**Files:**
- Create: `~/.claude/framework/current-gotchas.md`
- Create: `~/.claude/framework/interaction-log.md`

- [ ] **Step 1: Create framework directory**

```bash
mkdir -p ~/.claude/framework
```

- [ ] **Step 2: Write current-gotchas.md with Cycle 1 baseline**

```markdown
<!-- Updated: 2026-05-13 | Cycle: 1 -->
**Active gotchas — both sides:**

Claude watch-outs:
1. Premature "done" — never trust without local CI green first
2. Wrong approach at session start — if it picks wrong skill/language/workflow, stop early not late
3. Root cause skipping — add debug logging before proposing any fix

Your reminders:
1. Front-load context — include workflow + language + scope in your first message
2. Run CI locally before push — not CI's job to discover your bugs
3. Specify session mode upfront — "just merge" vs "full TDD flow" vs "only explain"
```

- [ ] **Step 3: Write interaction-log.md with Cycle 1 baseline metrics**

```markdown
# Interaction Framework — Cycle Log

## 2026-05-13 | Cycle 1 (baseline)
- Sessions analyzed: 42 | Period: 2026-04-15 → 2026-05-13
- wrong_approach: 26 (41%) | buggy_code: 24 (38%) | fully_achieved: 50% (21/42)
- dissatisfied: 12.2% (17/139) | command_failed: 98
- Changes applied:
  - ~/.claude/CLAUDE.md: 5 new sections (Language, Git Workflow, Destructive Commands, Verification, Prompt Refinement)
  - ~/.claude/settings.json: SessionStart + UserPromptSubmit gotcha injection hooks
  - ~/.claude/skills/gotcha-review/SKILL.md: created
  - ~/.claude/skills/review-my-usage/SKILL.md: created
  - scripts/hooks/pre-push-ci.sh: created
  - .claude/settings.json: pre-push PreToolUse hook added
- Next review: ~2026-05-28
```

- [ ] **Step 4: Verify both files exist**

```bash
ls -la ~/.claude/framework/
```

Expected: two files — `current-gotchas.md` and `interaction-log.md`.

---

## Task 4: `/gotcha-review` skill

**Files:**
- Create: `~/.claude/skills/gotcha-review/SKILL.md`

- [ ] **Step 1: Create skill directory**

```bash
mkdir -p ~/.claude/skills/gotcha-review
```

- [ ] **Step 2: Write SKILL.md**

```markdown
# Gotcha Review

Pre-implementation risk analysis. Run BEFORE writing any non-trivial code.
Trigger: /gotcha-review

## Process

**Round 1 — Obvious risks:**
1. Read `~/.claude/framework/current-gotchas.md` — apply active pitfall patterns to this task
2. List 3-5 risks across these categories:
   - Data assumptions: does the data you expect actually exist in the codebase or DB?
   - Dependencies: are all required packages, APIs, and env vars available?
   - Race conditions or ordering issues
   - Environment differences (dev vs CI vs prod)
   - Edge cases that invalidate the proposed approach
3. For each risk: query the actual codebase, schema, or config to confirm or invalidate it
   Do NOT assume — check

**Round 2 — What Round 1 missed:**
4. Re-examine each confirmed risk: is the root cause deeper than identified?
5. Check for hidden coupling: does this change affect something outside the stated scope?
6. Verify assumptions about calling code, schemas, and external APIs

## Output format

```
✅ Confirmed safe: [assumption] — verified via [file/query]
❌ Invalidated: [assumption] — actual state is [X] → plan needs revision
⚠️  Unknown: [assumption] — requires [data/env/access] to verify → flag before proceeding
```

Revised plan: [updated approach based on findings]

## Gate

Do NOT begin implementation until the user approves the revised plan.
If all assumptions are confirmed safe, state that explicitly before proceeding.
```

- [ ] **Step 3: Verify skill is discoverable**

```bash
ls ~/.claude/skills/gotcha-review/SKILL.md
```

Expected: file exists.

---

## Task 5: `/review-my-usage` skill

**Files:**
- Create: `~/.claude/skills/review-my-usage/SKILL.md`

- [ ] **Step 1: Create skill directory**

```bash
mkdir -p ~/.claude/skills/review-my-usage
```

- [ ] **Step 2: Write SKILL.md**

```markdown
# Review My Usage

Bi-weekly Claude Code interaction analysis. Run every ~15 days with `/review-my-usage`.

## Phase 1 — Analyze

Determine the last review date from the most recent entry in `~/.claude/framework/interaction-log.md`.

Read all session files modified after that date:
- `~/.claude/usage-data/facets/*.json` — keys: `friction_counts`, `outcome`, `user_satisfaction_counts`, `session_type`, `brief_summary`
- `~/.claude/usage-data/session-meta/*.json` — keys: `tool_errors`, `tool_error_categories`, `git_commits`, `duration_minutes`

Compute these metrics across all sessions in the period:

```
wrong_approach_count    = sum of friction_counts.wrong_approach across sessions
buggy_code_count        = sum of friction_counts.buggy_code across sessions
total_friction          = sum of all friction_counts values
wrong_approach_rate     = wrong_approach_count / total_friction

fully_achieved_count    = count of sessions where outcome == "fully_achieved"
total_sessions          = count of all sessions in period
fully_achieved_pct      = fully_achieved_count / total_sessions

dissatisfied_count      = sum of user_satisfaction_counts.dissatisfied
total_satisfaction      = sum of all user_satisfaction_counts values
dissatisfied_pct        = dissatisfied_count / total_satisfaction

command_failed_count    = sum of tool_errors where tool_error_categories contains "command_failed"
```

Compare each metric to the previous cycle entry in `interaction-log.md`.

Identify:
- What improved (metric decreased from previous cycle)
- What persists (metric stayed similar or increased)
- What is new (pattern not seen in previous cycle's brief_summaries)

Also analyze user pitfall patterns from `brief_summary` fields:
- How often did sessions start with missing context (language, workflow, scope)?
- How often was CI failure discovered post-push?
- How often was session mode ambiguous?

## Phase 2 — Propose (two internal rounds before presenting)

**Round 1 draft:**
- Proposed changes to `~/.claude/CLAUDE.md` (only for persistent or new patterns with data)
- Updated top-3 gotchas for `current-gotchas.md` — both Claude failure modes AND user patterns
- Any new skill or hook justified by data (not by intuition)

**Round 2 check:**
- Do any proposed CLAUDE.md changes contradict existing rules?
- Do the top-3 gotchas reflect actual data, not guessed patterns?
- Are there gotchas in the proposals themselves?

**Present to user:**

```
## Cycle N Analysis — YYYY-MM-DD

### Metrics delta
| Metric | Cycle N-1 | Cycle N | Trend |
|---|---|---|---|
| wrong_approach | X% | Y% | ↑↓→ |
| buggy_code | X% | Y% | ↑↓→ |
| fully_achieved | X% | Y% | ↑↓→ |
| dissatisfied | X% | Y% | ↑↓→ |
| command_failed | N | N | ↑↓→ |

### Proposed changes
1. [change] — justified by [metric/pattern]
2. ...

### Proposed top-3 gotchas
Claude watch-outs: ...
Your reminders: ...
```

## Phase 3 — Approve

⏸ Wait for user confirmation on each proposed change.
User can approve all, reject individual items, or request adjustments.
Do NOT apply any change without explicit approval.

## Phase 4 — Apply

For each approved change:

1. Apply CLAUDE.md edits to `~/.claude/CLAUDE.md`

2. Overwrite `~/.claude/framework/current-gotchas.md`:
```markdown
<!-- Updated: YYYY-MM-DD | Cycle: N -->
**Active gotchas — both sides:**

Claude watch-outs:
1. [top Claude failure mode]
2. [second]
3. [third]

Your reminders:
1. [top user pitfall]
2. [second]
3. [third]
```

3. Append to `~/.claude/framework/interaction-log.md`:
```markdown
## YYYY-MM-DD | Cycle N
- Sessions analyzed: N | Period: YYYY-MM-DD → YYYY-MM-DD
- wrong_approach: N (%) | buggy_code: N (%) | fully_achieved: %
- dissatisfied: % | command_failed: N
- Changes applied: [list each approved change, or "none"]
- Next review: ~YYYY-MM-DD
```

4. Commit in the current project repo:
```bash
git add ~/.claude/CLAUDE.md ~/.claude/framework/current-gotchas.md ~/.claude/framework/interaction-log.md 2>/dev/null || true
git commit -m "chore(framework): bi-weekly interaction review YYYY-MM-DD"
```
```

- [ ] **Step 3: Verify skill is discoverable**

```bash
ls ~/.claude/skills/review-my-usage/SKILL.md
```

Expected: file exists.

---

## Task 6: Pre-push CI gate (BioShield-specific)

**Files:**
- Create: `scripts/hooks/pre-push-ci.sh`
- Modify: `.claude/settings.json`

This hook follows the exact same stdin-parsing pattern as the existing project hooks (`safety-gate.sh`, `format.sh`). It reads JSON from stdin, extracts the Bash command, and only activates on `git push`.

- [ ] **Step 1: Write pre-push-ci.sh**

```bash
#!/usr/bin/env bash
# PreToolUse — bloquea git push si el CI matrix no está verde.
# Exit 0: permitir. Exit 1: bloquear.

set -uo pipefail

INPUT="$(cat)"

TOOL_NAME="$(python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('tool_name',''))" <<< "$INPUT")"

if [[ "$TOOL_NAME" != "Bash" ]]; then
    exit 0
fi

CMD="$(python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('tool_input',{}).get('command',''))" <<< "$INPUT")"

# Only intercept git push — ignore all other Bash commands
if ! echo "$CMD" | grep -qE 'git\s+push'; then
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

echo "[pre-push-ci] git push detected — running CI matrix before allowing push..."

cd "${REPO_ROOT}/backend"

echo "[pre-push-ci] ruff format --check..."
.venv/bin/python -m ruff format --check . 2>&1 || {
    echo "[pre-push-ci] BLOQUEADO: ruff format failed."
    echo "[pre-push-ci] Fix: cd backend && .venv/bin/python -m ruff format ."
    exit 1
}

echo "[pre-push-ci] ruff check..."
.venv/bin/python -m ruff check . 2>&1 || {
    echo "[pre-push-ci] BLOQUEADO: ruff lint errors."
    echo "[pre-push-ci] Fix: cd backend && .venv/bin/python -m ruff check --fix ."
    exit 1
}

echo "[pre-push-ci] mypy..."
.venv/bin/python -m mypy app/ 2>&1 || {
    echo "[pre-push-ci] BLOQUEADO: mypy type errors. Fix before pushing."
    exit 1
}

echo "[pre-push-ci] pytest..."
.venv/bin/python -m pytest 2>&1 || {
    echo "[pre-push-ci] BLOQUEADO: pytest failures. Fix failing tests before pushing."
    exit 1
}

echo "[pre-push-ci] All checks passed — proceeding with push."
exit 0
```

- [ ] **Step 2: Make script executable**

```bash
chmod +x scripts/hooks/pre-push-ci.sh
```

- [ ] **Step 3: Add pre-push PreToolUse entry to .claude/settings.json**

The existing `PreToolUse` array has one entry. Add a second entry after it. The full updated `hooks` section of `.claude/settings.json`:

```json
"hooks": {
  "PreToolUse": [
    {
      "matcher": "Bash|Write|Edit",
      "hooks": [
        { "type": "command", "command": "bash scripts/hooks/security-check.sh" },
        { "type": "command", "command": "bash scripts/hooks/safety-gate.sh" }
      ]
    },
    {
      "matcher": "Bash",
      "hooks": [
        { "type": "command", "command": "bash scripts/hooks/pre-push-ci.sh" }
      ]
    }
  ],
  "PostToolUse": [
    {
      "matcher": "Write|Edit",
      "hooks": [
        { "type": "command", "command": "bash scripts/hooks/format.sh" },
        { "type": "command", "command": "bash scripts/hooks/lint.sh" },
        { "type": "command", "command": "bash scripts/hooks/related-test.sh" }
      ]
    }
  ],
  "Stop": [
    {
      "matcher": "*",
      "hooks": [
        { "type": "command", "command": "bash scripts/hooks/type-check.sh" }
      ]
    }
  ]
}
```

- [ ] **Step 4: Validate .claude/settings.json is well-formed**

```bash
python3 -m json.tool .claude/settings.json > /dev/null && echo "valid" || echo "INVALID"
```

Expected: `valid`

- [ ] **Step 5: Smoke-test the hook intercepts correctly**

Create a temporary ruff violation, then attempt a push to verify the gate blocks it:

```bash
# Create a temp file with a ruff violation (unused import)
echo "import os" > backend/app/_test_violation.py
# Simulate a git push tool call through the hook
echo '{"tool_name": "Bash", "tool_input": {"command": "git push origin main"}}' | bash scripts/hooks/pre-push-ci.sh
```

Expected output: `[pre-push-ci] BLOQUEADO: ruff lint errors.`

```bash
# Clean up temp file
rm backend/app/_test_violation.py
```

- [ ] **Step 6: Commit**

```bash
git add scripts/hooks/pre-push-ci.sh .claude/settings.json
git commit -m "feat(framework): pre-push CI gate — blocks git push until ruff/mypy/pytest green"
```

---

## Verification checklist (run after all tasks)

- [ ] `cat ~/.claude/CLAUDE.md` — shows 5 sections
- [ ] `python3 -m json.tool ~/.claude/settings.json` — valid, has `UserPromptSubmit` key
- [ ] `ls ~/.claude/framework/` — shows `current-gotchas.md` and `interaction-log.md`
- [ ] `ls ~/.claude/skills/` — shows `gotcha-review/` and `review-my-usage/` directories
- [ ] Open a new CC session — check that gotchas appear as context in the first message
- [ ] Invoke `/gotcha-review` in any project — skill loads and runs two-pass review
- [ ] Invoke `/review-my-usage` — skill loads and starts Phase 1 analysis
- [ ] `python3 -m json.tool .claude/settings.json` — valid, has two `PreToolUse` entries
- [ ] Smoke-test pre-push-ci.sh as described in Task 6 Step 5
