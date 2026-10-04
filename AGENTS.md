# Sales AI Platform — Agent Engineering Contract

## 1. Project Mission

This repository is evolving from the existing Sales AI Copilot into a professional
AI-native Sales Platform for large-scale field sales and distribution.

The existing application is a valuable working baseline and MUST be evolved
incrementally. Do not rewrite the project from scratch.

Primary goals:
- improve field-sales effectiveness
- improve customer/product fit
- improve profitability and organizational execution
- support sales representatives, supervisors and managers
- preserve explainability of commercial decisions
- provide a professional Persian RTL-first user experience

---

## 2. Product Language and UX

The final user-facing product is Persian-only and RTL-first.

Technical identifiers, source code, APIs, model names and internal documentation
may remain English.

All new user-facing experiences must eventually support:
- Persian copy
- correct RTL behavior
- mobile-first responsive design
- tablet and desktop layouts where appropriate
- professional visual hierarchy
- loading, empty and error states
- contextual Help / Info where business rationale matters

Do not introduce bilingual product UX unless explicitly requested.

---

## 3. Repository Branch Policy

Stable branch:
- main

Active development branch:
- fast-track

Normal implementation work must happen on fast-track.

Do not push directly to main.

For unusually risky or large refactors, a temporary task branch may be created
from fast-track when explicitly requested.

Before starting work:
1. git fetch origin
2. git status
3. confirm working tree is clean
4. update using fast-forward-only workflow when appropriate

Never overwrite uncommitted user work.

---

## 4. Existing System Preservation

The current application contains valuable working business logic.

Preserve and evolve existing behavior unless a task explicitly changes it.

Important existing assets include:
- Customer / Customer360
- Product / Brand / Category
- sales history
- Inventory
- Promotions
- Recommendation Engine v1
- Product Associations
- Recommendation tuning
- Visits
- VisitCustomerSnapshot
- VisitCommercialSnapshot
- SalesOutcome
- FollowUpTask
- Targets
- Management analytics
- controlled Ollama-based AI narration
- deterministic demo seed/reset workflow

Do NOT replace these merely because a cleaner architecture could be designed.

Prefer:
KEEP → TEST → EXTRACT → EXTEND

over:
REWRITE → REPLACE

---

## 5. Critical Business Rules

### Recommendation

Recommendation Engine v1 is an existing business asset.

Do not change recommendation scoring, ranking or business semantics unless the
task explicitly requires it.

Future architecture may introduce:
- Opportunity
- Recommendation Session
- Recommendation Events
- ranking lenses
- Quantity Engine

These must be introduced incrementally and with backward compatibility where
required.

### AI

AI/LLM must not become hidden business authority.

Preferred pattern:

Business Data
→ Deterministic Engines / Policies
→ Structured Context
→ LLM
→ Explanation / Conversation

Critical commercial rules must remain deterministic and testable.

The application must eventually degrade gracefully if the LLM is unavailable.

### Visit Snapshots

VisitCustomerSnapshot and VisitCommercialSnapshot are immutable point-in-time
decision snapshots.

Do not mutate historical snapshots.

The existing demo reset command is an explicit exception that may delete scoped
demo snapshots to restore the deterministic demo baseline.

### Demo Reset

Preserve the scoped and repeatable demo workflow documented in:

docs/checkpoints/SALES_AI_COPILOT_V3.0.10.9_DEMO_RESET_REPEATABILITY.md

Do not replace it with a global database wipe.

### Returns

Future recommendation and quantity logic must distinguish gross purchase from
effective retained demand.

Do not interpret promotional overbuy followed by returns as normal customer
demand.

### Financial Risk

Customer grade alone must not determine commercial eligibility.

Recent overdue balances, returned cheques or other commercial-risk signals may
restrict otherwise high-grade customers.

Hard blocks must originate from explicit policy/authorized data, not free-form
LLM judgment.

---

## 6. Architecture Direction

Preferred architecture:

Django Modular Monolith
+ API-first
+ Event-ready
+ independent modern frontend

Do not introduce microservices without explicit approval.

Target technical direction:
- Django / Django REST Framework backend
- PostgreSQL production database
- Redis for suitable cache/state use cases
- queue-ready asynchronous architecture
- Next.js + TypeScript frontend
- responsive PWA
- Persian RTL-first design system

SQLite may remain during the current demo/development stage where appropriate.

Do not perform PostgreSQL migration merely as incidental work.

---

## 7. Domain Direction

Expected future domains include:

- organization
- customers
- products
- product knowledge
- field sales
- commercial policy
- orders
- targets
- initiatives
- opportunities
- recommendations
- intelligence
- actions
- AI
- integrations
- experience APIs

Do not create all domains prematurely.

Introduce them only through approved implementation tasks.

---

## 8. Refactoring Rules

Large refactors must be incremental.

In particular, do NOT rewrite apps/visits/services.py in one operation.

Preferred sequence:

1. identify responsibility
2. add characterization/regression tests
3. extract one coherent responsibility
4. preserve public behavior
5. run tests
6. inspect diff
7. continue only when stable

Avoid unrelated cleanup while implementing a scoped task.

Do not rename/move large numbers of files unless required.

---

## 9. Testing Contract

Tests are required around critical business behavior.

Priority areas:
- recommendation behavior
- commercial policy
- inventory restrictions
- promotion behavior
- visit lifecycle
- snapshot immutability
- targets
- permissions and organizational scope
- return-aware quantity logic when introduced

Before modifying existing business logic:
- understand current behavior
- add characterization tests when coverage is missing

After changes:
- run relevant tests
- run Django system checks when environment permits
- report exactly what was and was not tested

Never claim tests passed if they were not executed.

---

## 10. Security Contract

Server-side authorization is mandatory.

UI visibility is not authorization.

Future access control must account for:
- authentication
- role
- organizational scope
- territory
- sales line
- customer assignment where applicable

Never expose secrets in source code, logs, fixtures, documentation or commits.

.env must remain untracked.

.env.example may contain safe placeholders only.

---

## 11. Database and Migration Safety

Do not create destructive migrations without explicit approval.

Do not delete or rewrite historical business data as part of refactoring.

Do not casually modify tracked db.sqlite3.

Validation-only database changes should normally be restored before commit unless
the task explicitly requires a canonical demo database change.

Always inspect migrations before applying potentially destructive changes.

---

## 12. Demo Data Contract

The demo environment must remain deterministic and repeatable.

Current V3.0.10.9 demo workflow is authoritative until replaced by an approved
newer checkpoint.

Important current demo salesperson:
- SP001

Current scoped demo customers:
- C0003
- C0005
- C0013
- C0014
- C0029

Do not silently change these assumptions.

Future canonical demo scenarios may extend this dataset.

---

## 13. API Direction

Prefer explicit versioned experience-oriented APIs.

Do not break existing endpoints unless the task explicitly authorizes a breaking
change.

Future experience APIs may include concepts such as:
- Daily Brief
- Route
- Customer 360
- Pre-Visit
- Guided Smart Sale
- Product 360
- Product Advisor
- Basket
- Order
- Visit Summary
- Manager Overview

Freeze contracts before independently implementing frontend and backend against
them.

---

## 14. Frontend Direction

The existing Django template frontend is a useful working baseline and UX
reference.

Do not spend large effort rebuilding new strategic UX inside the legacy frontend
unless explicitly requested.

The target frontend is a modern Persian RTL responsive application.

New design work should converge on a reusable design system rather than
page-specific styling.

---

## 15. Documentation

Important architecture, business decisions and milestones must be documented in
the repository.

Existing checkpoint location:

docs/checkpoints/

Before making architecture-level decisions, inspect the latest relevant
checkpoint.

Do not treat old checkpoints as more authoritative than newer approved
decisions.

When implementation materially changes architecture or business behavior, update
or create the appropriate checkpoint.

---

## 16. Agent Task Discipline

For every implementation task:

### Before coding
- read this AGENTS.md
- read task-specific referenced documentation
- inspect current implementation
- inspect git status
- identify the smallest required change

### During coding
- stay within task scope
- preserve unrelated behavior
- avoid speculative features
- avoid unnecessary dependencies
- do not perform unrelated formatting/cleanup

### After coding
- inspect git diff
- run relevant tests/checks
- report changed files
- report behavior changed
- report tests executed and results
- report known limitations or follow-up work

Do not commit or push unless the task explicitly requests it.

---

## 17. Fast-Track Delivery Strategy

Current delivery strategy is vertical-slice and demo-first without sacrificing
core architecture.

Priority:

1. stable engineering baseline
2. secure/testable backend
3. fixed experience contracts
4. professional RTL design foundation
5. Customer / Visit journey
6. Guided Smart Sale
7. Product Intelligence
8. Basket / Order loop
9. Manager / Supervisor story
10. production hardening

Advanced ML, full offline synchronization, microservices, advanced route
optimization and full enterprise integrations are not current critical-path
items unless explicitly promoted.

---

## 18. Definition of Done

A task is not complete merely because code was generated.

A completed engineering task should satisfy, as applicable:

- requested behavior implemented
- existing behavior preserved unless intentionally changed
- tests added/updated
- relevant tests pass
- Django checks pass where applicable
- no unexpected migration
- no secrets introduced
- git diff contains only scoped changes
- documentation updated when needed
- known limitations explicitly reported

For hero UI work also require:
- professional appearance
- Persian RTL correctness
- responsive behavior
- loading/empty/error states
- contextual Help/Info where appropriate

---

## 19. Current Baseline

Official Fast Track starting baseline:

- repository: sales_ai_copilot
- stable baseline commit: fd3b53e
- baseline milestone: V3.0.10.9
- development branch: fast-track
- demo reset: validated
- working strategy: evolve, do not rewrite

If repository state conflicts with this section, stop and report the discrepancy
before making structural changes.
