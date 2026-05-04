# Development Workflow

## Quick Start

### Step 0: Init Developer (First Time Only)
```bash
python3 ./.trellis/scripts/get_developer.py
python3 ./.trellis/scripts/init_developer.py <name>   # if not initialized
```

### Step 1: Get Context
```bash
python3 ./.trellis/scripts/get_context.py
```

### Step 2: Read Guidelines [MANDATORY]
```bash
cat .trellis/spec/backend/index.md   # Backend
cat .trellis/spec/frontend/index.md  # Frontend (if applicable)
cat .trellis/spec/guides/index.md    # Thinking guides
```

Read specific guideline docs based on your task before coding.

---

## Core Principles

1. **Read Before Write** - understand context before starting
2. **Follow Standards** - MUST read `.trellis/spec/` before coding
3. **One task at a time** - incremental development
4. **Agent-first delivery** - use the task/PR pipeline when the work should land now
5. **Record promptly** - update tracking after completion
6. **Journal limit** - max 2000 lines per journal file

---

## Development Flow

```
1. Select/create task -> python3 ./.trellis/scripts/task.py list|create
2. Start task + read specs -> python3 ./.trellis/scripts/task.py start <dir>
3. Code following specs -> read .trellis/spec/ docs first
4. Self-test -> lint + targeted manual/automated verification
5. Deliver through PR -> set base/scope/branch, then python3 ./.trellis/scripts/task.py create-pr
6. Wait for checks -> gh pr checks / fix on same branch / rerun create-pr if needed
7. Merge + cleanup -> gh pr ready / gh pr merge --merge --delete-branch / sync local master
8. Record -> python3 ./.trellis/scripts/add_session.py --title "..." --commit "hash"
```

Quality: tests, lint, and relevant manual verification should pass before `create-pr` or merge.

---

## Session End

```bash
python3 ./.trellis/scripts/add_session.py --title "Title" --commit "abc1234" --summary "Brief"
```

If this was planning-only work, `--commit` may be omitted.

Pre-end: use `/trellis:finish-work` checklist.

---

## File System

```
.trellis/
├── .developer           # Identity (gitignored)
├── scripts/             # Python scripts (task.py, get_context.py, add_session.py, ...)
├── workspace/{dev}/     # Per-developer journals (journal-N.md)
├── tasks/{MM-DD-name}/  # Task directories (task.json, prd.md, context files)
├── spec/                # [!] MUST READ before coding
│   ├── backend/         # Backend guidelines (index.md -> *.md)
│   ├── frontend/        # Frontend guidelines (index.md -> *.md)
│   └── guides/          # Thinking guides (index.md -> *.md)
└── workflow.md          # This file
```

---

## Task Commands

```bash
python3 ./.trellis/scripts/task.py create "<title>" [--slug <name>]
python3 ./.trellis/scripts/task.py init-context <dir> <dev_type>
python3 ./.trellis/scripts/task.py start <dir>
python3 ./.trellis/scripts/task.py set-base-branch <dir> master
python3 ./.trellis/scripts/task.py set-branch <dir> <branch>
python3 ./.trellis/scripts/task.py set-scope <dir> <scope>
python3 ./.trellis/scripts/task.py create-pr [dir]
python3 ./.trellis/scripts/task.py finish
python3 ./.trellis/scripts/task.py archive <name>
python3 ./.trellis/scripts/task.py list
```

## Commit Convention

`type(scope): description` - types: feat, fix, docs, refactor, test, chore

`task.py create-pr` builds the commit/PR title from task metadata. If the change may later become public, keep that title public-readable.

## DO / DON\'T

DO: read specs, run tests frequently, keep task metadata accurate, record sessions, keep commit titles public-safe when needed
DON\'T: skip specs, exceed 2000 journal lines, commit with failing checks, publish private-only content to the public repo
