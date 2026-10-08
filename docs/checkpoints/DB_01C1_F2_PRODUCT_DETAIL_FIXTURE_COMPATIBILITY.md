# DB-01C1-F2 — Product Detail and fixture compatibility

Date: 2026-10-08. Scope: deterministic saved-component presentation and the two
invalid test fixtures. F1 and existing Stage 3/DB work are preserved.

## Corrections

Product Detail previously iterated score_breakdown.items(), so JSONB key order
changed the rendered component sequence. The presentation now explicitly follows
Recommendation Engine v1's established sequence:

group, purchase, association, upsell, grade, promotion, similar, rule, feedback,
final score. Known aliases appear beside their canonical component; unknown saved
keys follow in sorted key order. Actual values, zeros, negative values and all
saved keys remain available. This does not score, rank, deduplicate, fabricate or
persist components. Explanation signal lists retain their existing source order.

The customer-name fixture is exactly the existing maximum of 200 characters,
including its complete HTML script payload and long Persian prefix. All escaping,
Unicode and bdi assertions remain. BRIEF-GRADE (11 characters) becomes BRIEF-GRD
(9), within CustomerGrade.code's maximum 10. No fields were widened.

Templates/CSS/JS and card/page anatomy are unchanged. Product Detail's validated
return URLs, customer/visit context, authorization, recommendation ranking and
product eligibility remain unchanged; no screenshots are required for this fix.

## Tests and safety

- 36 focused PostgreSQL tests passed: 35 Product Detail/helper tests and the
  affected Guided long-name test. Includes both prior ordering failures, the
  promotion-grade fixture, reverse-key persistence through actual JSONB, zero/
  unknown-value preservation and explicit Engine v1 display ordering.
- Django PostgreSQL check: no issues. Migration drift: no changes detected.
- Only test_db01c1_f2_20261008T150926_5531c9 was created/dropped; production
  connections were read-only and SQLite test connections prohibited.
- Production reconciliation preserved all 2396 rows, financial totals, framework
  metadata, empty sessions/foundations and the approved legacy exception.
- No full compatibility suite, schema migration, role change, source SQLite
  mutation, cutover, staging, commit or push.

Protected ignored evidence: venv/db01c1-f2-artifacts/20261008T150926Z/.
Original SQLite SHA256:
1E18CB45927A5AFA87838D13ED8385EEA6740DD849C9C9A8AE1BB73B0C19DD15.
Original stash: 2dac7bdc26f07f611f471564476ceaa52ec367cc.

The identified F2 issues are closed by focused coverage. The broader PostgreSQL
compatibility gate must be rerun only under separate authorization; runtime
privilege reduction still precedes final cutover.
