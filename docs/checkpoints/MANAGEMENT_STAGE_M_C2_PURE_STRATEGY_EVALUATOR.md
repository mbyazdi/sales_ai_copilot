# Stage M-C2 — Pure Strategy Evaluator

Date: 2026-10-16. Baseline: V3.0.23 / `045390dcb45608c9125c1567c38e07f96baf8290`.
Authority: approved M-A2 contract and approved uncommitted M-C1 foundation.
Status: isolated validation passed; NOT ACTIVATED or DEPLOYED.

## Boundary and public contract

`apps.management.strategy_evaluator.evaluate_strategy(StrategySnapshot)` returns
an immutable `StrategyEvaluation`. No ORM, settings access, wall clock, database
write, publication, price calculation or live journey integration. It reuses
M-C1 canonical serialization/config validation, whose Django dependency is only
the core ValidationError class; Django setup is unnecessary.

Frozen, slotted dataclasses define the boundary:

- `StrategyRules`, `PriorityRule`, `PromotionRule`: typed V1 config and algorithm.
  `StrategyRules.from_config` accepts the existing M-C1 config shape.
- `ProductFacts`: product ID/code, brand/category IDs, group and active flag.
- `SavedRecommendation`: ID/product, saved rank, Decimal score, original reason,
  commercial facts and optional opaque saved evidence JSON. Position in the
  input tuple is authoritative; stored rank/score never determine a new baseline.
- `CommercialFacts`: canonical stock state/sellable quantity, pricing state,
  can_add and reason annotations. Uses current quote/pricing state vocabulary.
- `TargetFacts` and `PromotionFacts`: explicit dates, identities, scope, unit,
  amounts, membership/grade restrictions, quantity terms and active flags.
- `StrategySnapshot`: customer/salesperson/grade, explicit Tehran evaluation
  date, ordered recommendations, all required reference facts/ID registries,
  targets, promotions and rules. Capture/authorization is a future boundary.

Reference facts can include products outside the shortlist to validate global
rules and promotion/target references; those products never become candidates.
Explicit empty tuples mean known-none. Missing required facts, duplicate IDs,
unknown references, invalid types/periods/amounts/configs and contradictory
addability annotations fail closed with `StrategyInputError(code, path)`.
Unknown stock keeps quantity null; missing price stays unavailable, never zero.

Output contains before/after IDs, original positions, effective ranks, untouched
source facts, base priority, three contributions, total adjustment, effective
priority, configuration/input hashes and a deterministic result digest.
`as_dict()` returns detached JSON-ready data with decimal strings. Reason records
contain stable codes, Persian text, source IDs and structured data. Examples:
`PRIORITY_EXPLICIT_ZERO`, `TARGET_APPLIED`, `TARGET_OVERLAP_NOT_STACKED`,
`TARGET_UNIT_UNSUPPORTED`, `PROMOTION_GRADE_INELIGIBLE`,
`PROMOTION_QUANTITY_ONE_INELIGIBLE`, `PROMOTION_EMPHASIS_ZERO`.

## Algorithm V1

```text
base_priority = 10 * (N - original_position)
priority = most-specific matching PRODUCT > BRAND > CATEGORY rule (0..20)
target = highest qualifying ROUND_HALF_UP(weight * (target-actual)/target, .01)
promotion = highest configured qualifying promotion emphasis (0..5)
adjustment = min(30, priority + target + promotion)
effective_priority = base_priority + adjustment
```

An explicit zero priority overrides broader priority rules, not target/promotion
contributions. Targets are active, inclusive-date, matching-scope, same-salesperson
QUANTITY records with remaining shortfall. Achieved targets add nothing; MSU is
excluded. Equal target contributions prefer PRODUCT, CATEGORY, PRODUCT_GROUP,
then lowest target ID. Targets never stack.

Promotions must be explicitly emphasized, active, linked, inclusive-date,
grade-qualified and valid for quantity one. Empty grade restrictions are open;
missing customer grade cannot satisfy restricted offers. Multi-unit offers do
not boost quantity-one ranking. Highest emphasis wins, then lowest promotion ID;
no stacking and no discount calculation. The saved engine promotion component
is never recomputed, corrected or subtracted.

Sort: effective priority descending, original position ascending, recommendation
ID ascending. All arithmetic uses a local Decimal context and HALF_UP to two
places, independent of ambient precision/rounding. Equivalent Decimal encodings
have equal input/output digests; wire scores use their existing four-place scale.
Source JSON remains exact opaque text, including legitimate legacy JSON floats;
its values never enter overlay arithmetic.

Illustrative tested result (four saved recommendations):

| ID | Base | Priority | Target | Promotion | Effective |
| --- | ---: | ---: | ---: | ---: | ---: |
| 101 | 30 | 0 | 0 | 0 | 30 |
| 102 | 20 | 8 | 0 | 0 | 28 |
| 103 | 10 | 20 | 5 | 5 | 40 |
| 104 | 0 | 0 | 0 | 0 | 0 |

After: **103, 101, 102, 104**. Neutral: **101, 102, 103, 104**, even with
saved scores **40, 90, 70, 60**. Another tested tie yields effective priorities
**30, 22.50, 30, 30**, ordered **101, 103, 104, 102**. Target 100, actual 99.90,
weight 5 produces 0.005 and rounds to **0.01**.

Commercial eligibility is not a ranking factor or an output permission grant.
Inactive rows, if captured, remain disabled audit evidence; future live catalog
integration must retain existing inactive-product visibility filtering. Zero or
unknown stock, missing prices and Visit restrictions are never enabled by boosts.

Before in this single-policy evaluator means saved baseline. A future active vs
draft comparison must evaluate both policies against the same captured facts;
M-C2 does not retrieve the active policy or create comparison records.

## Validation and reproducibility

```powershell
.\venv\Scripts\python.exe -B -m unittest apps.management.tests_strategy_evaluator -v
.\venv\Scripts\python.exe -B -m apps.management.verify_strategy_evaluator --sqlite
.\venv\Scripts\python.exe -B -m apps.management.verify_strategy_evaluator
```

Final focused selection: **41/41 passed on PostgreSQL and 41/41 on SQLite**,
zero failures/errors/skips: 31 pure tests, 2 DB round-trip tests, 4 M-C1
serialization regressions and 4 unchanged recommendation-engine baseline tests.
Includes fresh processes with different hash seeds and no Django setup/ORM
import, shuffled fact registries, Decimal-context/encoding invariance, missing
data, all qualification/overlap cases, source immutability and commercial states.

The same database-captured fixture produced the identical result digest on both:
`b1df445d05b1620e2713d67c1e6351a5b0d58f634a0ad5fd46e7ed8de0f9c748`.
Evaluation made **zero SQL queries**; source business rows matched before/after.
An initial fixture reused a unique brand name; test names were corrected before
the final runs. No application/domain model was changed for that fixture issue.

The M-C1 runner now accepts optional test labels; its default selection and
identity/cleanup safeguards are unchanged. The thin M-C2 runner supplies only
the focused selection above. PostgreSQL used independent UUID-marked disposable
databases/owners, applied the existing 51-migration graph there, and removed test
resources afterward. Persistent Demo reads were read-only preservation checks;
all user-table and sequence digests matched before/after. No full suite or JS
tests: no JavaScript changed. Django check and migration drift passed.

## Preservation and remaining work

No C2 migration or model change. M-C1 model/serialization/access/transaction/test
and migration files are retained; only its test-runner selection hook changed.
No API, UI, Guided Sale, Basket, Submit, Visit or recommendation-engine edit.
No original PostgreSQL connection, persistent writes, service restart, Gate V2,
Prepare Day, reset, generation switch, credential change, staging, commit or push.

Original SQLite SHA256:
`1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15`.
Original stash: `2dac7bdc26f07f611f471564476ceaa52ec367cc`.
Unrelated DEMO-02 planning and all protected state remain preserved.

Next approval boundaries: authoritative authorized snapshot capture, immutable
active/draft comparisons, publication/replay APIs, fresh signed-context lineage,
and management UI. No current caller activates this evaluator. Existing database
deployment restrictions remain in force.
