# Sales AI Copilot â€” Development Checkpoint

**Checkpoint:** V2.6 Complete
**Continuation Point:** V2.7 â€” Customer Visit Workspace V2
**Date:** 2026-08-24

---

## 1. Project Status

Completed:

```text
V2.1 Role & Experience Foundation        COMPLETE
V2.2 Sales Rep Daily Workspace V2        COMPLETE
V2.3 Sales Target Foundation             COMPLETE
V2.4 Commercial Context                  COMPLETE
V2.5 Commercial Decision Layer           COMPLETE
V2.6 Pre-Visit Intelligence / Nightly    COMPLETE
```

Next:

```text
V2.7 Customer Visit Workspace V2
```

---

## 2. V2.6 Objective

Make pre-visit intelligence reusable for today and future visits without duplicating the canonical Commercial Decision logic.

Chosen architecture:

```text
Visit Window
    â†“
Target Progress by Visit Date
    â†“
build_pre_visit_briefs()
    â†“
Canonical Commercial Decision
    â†“
Pre-Visit Intelligence Package
    â†“
Nightly-ready Management Command
```

Persistent snapshot/cache was intentionally NOT added because the current fresh computation path is already efficient and avoids invalidation complexity around recommendation, inventory, promotion, target, and follow-up changes.

---

## 3. New Window Service

File:

```text
apps/visits/services.py
```

New service:

```text
build_pre_visit_intelligence_window(
    salesperson,
    start_date,
    end_date,
    statuses=None,
)
```

Default eligible statuses:

```text
PLANNED
IN_PROGRESS
```

Validation:

```text
start_date > end_date
â†’ ValueError("start_date cannot be after end_date.")
```

Target progress is intentionally evaluated per visit date.

---

## 4. Today Window Validation

For SP001 / 2026-08-24:

```text
VISIT COUNT: 5

14 | C0003 | PHI002 | VISIT HIGH 7   | COMMERCIAL HIGH 9
18 | C0029 | PHI002 | VISIT HIGH 6   | COMMERCIAL HIGH 8
16 | C0013 | PHI002 | VISIT MEDIUM 5 | COMMERCIAL HIGH 8
15 | C0005 | PHI004 | VISIT MEDIUM 4 | COMMERCIAL HIGH 7
17 | C0014 | PHS001 | VISIT MEDIUM 3 | COMMERCIAL NORMAL 3
```

---

## 5. Future Demo Visits

New safe/idempotent command:

```text
apps/visits/management/commands/seed_pre_visit_intelligence_demo.py
```

Purpose:

Create future Demo visits for SP001 without modifying today's visits.

Future date:

```text
2026-08-25
```

Created:

```text
Visit 19 | C0003
Visit 20 | C0005
Visit 21 | C0014
```

First run:

```text
Visits created: 3
Visits already existing: 0
```

Second run:

```text
Visits created: 0
Visits already existing: 3
```

Therefore seed command is idempotent.

---

## 6. Nightly-ready Preparation Command

New command:

```text
apps/visits/management/commands/prepare_pre_visit_intelligence.py
```

Examples:

```powershell
python manage.py prepare_pre_visit_intelligence `
  --salesperson SP001 `
  --days 1 `
  --include-today
```

```powershell
python manage.py prepare_pre_visit_intelligence `
  --salesperson SP001 `
  --days 7
```

```powershell
python manage.py prepare_pre_visit_intelligence `
  --days 1
```

Validation:

```text
--days 0
â†’ CommandError: --days must be at least 1.
```

---

## 7. Future Window Validation

For SP001 / 2026-08-25:

```text
Visit 19 | C0003 | PHI002 | Commercial HIGH 9
Visit 20 | C0005 | PHI004 | Commercial HIGH 7
Visit 21 | C0014 | PHS001 | Commercial NORMAL 3
```

---

## 8. Future Query Sanity

For 3 future visits:

```text
TOTAL QUERIES: 7
```

Query structure:

```text
1 Visit window selection
2 Target progress
3 Recommendations batch
4 Inventory batch
5 Promotion/Product batch
6 Promotion grade prefetch
7 Follow-ups batch
```

No N+1 regression.

---

## 9. Future Decision Consistency

Window Service vs Canonical Visit Decision API:

```text
Visit 19 / C0003 â†’ HIGH 9 = HIGH 9
Visit 20 / C0005 â†’ HIGH 7 = HIGH 7
Visit 21 / C0014 â†’ NORMAL 3 = NORMAL 3
```

All:

```text
MATCH: True
```

---

## 10. Whole Sales Force Nightly Validation

Command:

```powershell
python manage.py prepare_pre_visit_intelligence `
  --days 1
```

Result:

```text
SP001 | Ali Ahmadi  | VISITS: 3
SP002 | Sara Karimi | VISITS: 0
SP003 | Reza Moradi | VISITS: 0

SALESPERSONS PROCESSED: 3
VISITS PREPARED: 3
```

Nightly orchestration therefore works for both:

```text
single salesperson
whole active sales force
```

---

## 11. Persistent Snapshot Decision

Current decision:

```text
Persistent Snapshot / Cache = NOT REQUIRED for Demo
```

Reason:

```text
fresh computation is already batch-efficient
future 3-visit window = 7 queries
snapshot invalidation would add unnecessary complexity
```

Do not introduce snapshot persistence unless a later performance or product requirement justifies it.

---

## 12. Final Validation

Confirmed:

```text
python manage.py check
â†’ System check identified no issues (0 silenced).

git diff --check
â†’ passed
```

Therefore:

```text
V2.6 STATUS = COMPLETE
```

---

## 13. Current Git State Before V2.6 Commit

Modified:

```text
apps/visits/services.py
db.sqlite3
```

Untracked:

```text
apps/visits/management/commands/prepare_pre_visit_intelligence.py
apps/visits/management/commands/seed_pre_visit_intelligence_demo.py
sales_ai_copilot_checkpoint_v2_6_complete.md
```

Note:

```text
git diff --stat
```

does not include untracked files until staged.

Tracked stat before staging:

```text
apps/visits/services.py | 208 insertions
db.sqlite3              | binary modified
```

---

## 14. NEXT ACTION â€” Close V2.6 Safely in Git

Inspect caches:

```powershell
Get-ChildItem "apps\visits" -Recurse -File |
Where-Object {
    $_.FullName -match "__pycache__|\.pyc$"
} |
Select-Object FullName
```

Remove cache directories if present.

Stage:

```powershell
git add `
  apps/visits/services.py `
  apps/visits/management/commands/prepare_pre_visit_intelligence.py `
  apps/visits/management/commands/seed_pre_visit_intelligence_demo.py `
  db.sqlite3 `
  sales_ai_copilot_checkpoint_v2_6_complete.md
```

Review:

```powershell
git status
git diff --cached --stat
git diff --cached --check
```

Suggested commit:

```text
Complete Pre-Visit Intelligence V2
```

Then:

```powershell
git commit -m "Complete Pre-Visit Intelligence V2"
git push origin main
```

Final:

```powershell
git status
git log -5 --oneline
```

Expected:

```text
nothing to commit, working tree clean
```

---

## 15. NEXT STAGE

```text
V2.7 â€” Customer Visit Workspace V2
```

Primary focus:

```text
visit execution experience
start visit
customer context
commercial decision
next best action
talking point
outcome capture
follow-up workflow
```

Reuse all canonical V2.5/V2.6 services. Do not duplicate Commercial Decision logic.

---

## 16. One-line Handoff

```text
V2.6 Pre-Visit Intelligence is complete: canonical date-window preparation works for today, future visits, single reps and the whole active sales force; future windows stay batch-efficient at 7 queries for 3 visits, so no persistent snapshot is needed for the Demo. Close V2.6 safely in Git, then start V2.7 Customer Visit Workspace V2.
```
