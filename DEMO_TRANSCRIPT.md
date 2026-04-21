# ForgeStack Demo Transcript

An end-to-end walkthrough of a ForgeStack session — from CLI invocation through the critique loop to applying the final output. This transcript uses a hypothetical `my-app` repository (a TypeScript project) to illustrate the workflow.

All paths, timestamps, and session IDs below are illustrative.

---

## 1. Listing configured repositories

```bash
$ forgestack repos
┌──────────────────────────────────────────────────────────────────┐
│  Configured repositories                                         │
├──────────────┬───────────────────────────┬───────────────────────┤
│ Key          │ Path                      │ Status                │
├──────────────┼───────────────────────────┼───────────────────────┤
│ my-app       │ ~/code/my-app             │ ✓ Valid (javascript)  │
│ my-library   │ ~/code/my-library         │ ✓ Valid (javascript)  │
│ my-service   │ ~/code/my-service         │ ✓ Valid (python)      │
└──────────────┴───────────────────────────┴───────────────────────┘
```

---

## 2. Running a code-improvement task

```bash
$ forgestack run \
  --repo my-app \
  --task code_improvement \
  "Refactor the cart store to use immutable updates and reduce re-renders"
```

### Setup

```
╔══════════════════════════════════════════════════════════════════╗
║                    ⚡ ForgeStack Session                         ║
╠══════════════════════════════════════════════════════════════════╣
║  Session ID: 7c8a4d12-f9e3-4b5a-9c61-0e2a8b6d4f17                ║
╚══════════════════════════════════════════════════════════════════╝

━━━ Setup ━━━
→ Resolving repository...
  ✓ /Users/developer/code/my-app
→ Gathering codebase context...
  Discovering related repos...
  Found 2 related repos
  ✓ Context gathered
→ Loading design system context...
  ✓ Design system loaded
→ Initializing MCP tools...
  ✓ Loaded 4 MCP tools
```

### Round 1 — initial proposal

```
━━━ Critique Loop ━━━

Round 1 / 3
  Generator working...
  ✓ Proposal drafted (1,842 tokens)
  Critic evaluating...
  ✓ Scored:
    - Correctness:     8.5 / 10
    - Architecture:    7.5 / 10
    - Code quality:    8.0 / 10
    - Completeness:    7.0 / 10
    - Risk:            8.0 / 10
    ─────────────────────────
    Final score:       7.8 / 10   (threshold 8.5 — revision needed)

  Critic feedback (summary):
  - The proposed reducer keeps a nested mutable `items` map; tests already
    depend on reference equality — switch to a shallow-cloned record.
  - Missing memoisation boundary for the derived `cartTotal` selector;
    component will still re-render on unrelated updates.
  - No migration note for existing persisted state in localStorage.
```

### Round 2 — revision

```
Round 2 / 3
  Generator working (revising with feedback)...
  ✓ Revised proposal (2,104 tokens)
  Critic evaluating...
  ✓ Scored:
    - Correctness:     9.0 / 10  (↑ +0.5: reference equality fixed)
    - Architecture:    8.5 / 10  (↑ +1.0: memoisation layer added)
    - Code quality:    8.5 / 10  (↑ +0.5)
    - Completeness:    8.5 / 10  (↑ +1.5: migration path documented)
    - Risk:            8.5 / 10  (↑ +0.5)
    ─────────────────────────
    Final score:       8.6 / 10   ✓ Consensus reached
```

### Synthesis

```
━━━ Synthesis ━━━
Synthesizer working...
✓ Final output produced (3,287 tokens)

Session complete.
  Final score:   8.6 / 10
  Rounds used:   2 / 3
  Consensus:     ✓ passed
  Output saved:  output/forgestack-7c8a4d12.md
```

---

## 3. Inspecting the output

```bash
$ head -40 output/forgestack-7c8a4d12.md
```

```markdown
## Summary

Refactor the cart store so that every state transition produces a new
top-level object (shallow clone) with item records keyed by product ID.
Add a `selectCartTotal` memoised selector and a one-shot migration for
persisted state written by the previous mutable version.

## Implementation Steps

### Step 1: Replace mutable reducers
**File**: `src/stores/cart.ts`
**Action**: Modify

```python
// (full file content follows)
```

### Step 2: Add memoised selector
**File**: `src/stores/selectors.ts`
**Action**: Create

```python
// (full file content follows)
```

### Step 3: Migrate persisted state
**File**: `src/stores/migrations/001_cart_shape.ts`
**Action**: Create

...
```

---

## 4. Applying the changes

```bash
$ forgestack apply output/forgestack-7c8a4d12.md --dry-run

ForgeStack apply — dry run
───────────────────────────────────────────────────────
Files to modify:  2
  - src/stores/cart.ts                          (modify)
  - src/stores/selectors.ts                     (create)
Files to create:  1
  - src/stores/migrations/001_cart_shape.ts     (create)

No changes written (dry run). Run without --dry-run to apply.
```

```bash
$ forgestack apply output/forgestack-7c8a4d12.md

Apply changes to ~/code/my-app? [y/N] y

✓ Modified  src/stores/cart.ts                          (+112 / -78)
✓ Created   src/stores/selectors.ts                     (+34)
✓ Created   src/stores/migrations/001_cart_shape.ts     (+47)

Applied 3 changes from session 7c8a4d12.
```

---

## 5. Reviewing session history

```bash
$ forgestack history --last 5
```

```
┌──────────┬────────────┬──────────────────┬───────┬────────┬────────────────────┐
│ ID       │ Repo       │ Task             │ Score │ Rounds │ Created            │
├──────────┼────────────┼──────────────────┼───────┼────────┼────────────────────┤
│ 7c8a4d12 │ my-app     │ code_improvement │  0.86 │      2 │ 2025-01-12 14:30   │
│ 4e1b2fa7 │ my-app     │ feature          │  0.88 │      2 │ 2025-01-11 11:20   │
│ 90cf3e21 │ my-library │ exploration      │  0.91 │      1 │ 2025-01-10 10:15   │
│ 13b6a8d4 │ my-service │ bugfix           │  0.87 │      2 │ 2025-01-09 16:45   │
│ 88fe0d55 │ my-app     │ architecture     │  0.84 │      3 │ 2025-01-08 09:00   │
└──────────┴────────────┴──────────────────┴───────┴────────┴────────────────────┘
```

---

## 6. Exporting a session

```bash
$ forgestack export --session-id 7c8a4d12 --format markdown > session-7c8a4d12.md
$ forgestack export --session-id 7c8a4d12 --format json    > session-7c8a4d12.json
```

The markdown export includes the full generator/critic exchange per round, the synthesizer's final output, and a summary header. The JSON export is suitable for pipelines, dashboards, or post-hoc analysis.

---

## What happened, and why it matters

1. **Round 1 was not good enough.** The Critic flagged three concrete issues rather than rubber-stamping the proposal. Without the loop, those issues would land in the output.
2. **Round 2 addressed every Critic flag.** The score jumped from 7.8 to 8.6 because the Generator treated the feedback as a checklist, not a vibe.
3. **The Synthesizer only ran once consensus was reached.** It was free to focus on polish and file layout rather than correctness — producing output that is ready to apply with one command.

This is the core ForgeStack loop: structured disagreement → measurable improvement → actionable synthesis.
