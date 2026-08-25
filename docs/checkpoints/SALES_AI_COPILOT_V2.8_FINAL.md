# Sales AI Copilot — V2.8 Final Checkpoint

## Status

V2.8 is officially completed and regression-tested.

Final regression result:

- V2.8 Final Regression: PASSED
- Django system check: PASSED
- git diff --check: PASSED
- Pending migrations: NONE
- ML training: DISABLED
- ML prediction: DISABLED
- Ollama integration runtime test: POSTPONED

---

## V2.8 Scope Completed

### V2.8.1
Post-Visit Intelligence

### V2.8.2
Historical Outcome Context

### V2.8.3
AI Context Integration

### V2.8.4
Prompt Historical Guardrails

### V2.8.5
Learning Readiness

### V2.8.6
ML Learning Contract

### V2.8.7
Point-in-Time Safe Contract

### V2.8.8
Visit Customer Snapshot Foundation

### V2.8.9
Customer Snapshot to ML Contract

### V2.8.10
Visit Commercial Snapshot

### V2.8.11
Commercial Snapshot to ML Contract

### V2.8.12
Safe ML Dataset Builder

### V2.8.13
ML Dataset Export Contract

### V2.8.14
Dataset Validator and Data Quality Report

### V2.8.15
Final Regression and Release Checkpoint

---

## Immutable Snapshot Architecture

Two immutable visit-time snapshots now exist:

### VisitCustomerSnapshot

Captured when a visit starts.

Contains point-in-time customer features including:

- customer grade
- segment
- total orders
- total sales amount
- average order value
- days since last purchase
- recency score
- frequency score
- monetary score
- RFM score
- top category
- top product code
- source Customer360 calculated timestamp

The snapshot is idempotent and immutable.

Current Customer360 changes do not change the historical visit snapshot.

### VisitCommercialSnapshot

Captured when a visit starts.

Contains decision-time commercial context including:

- primary product code
- recommendation type
- commercial score
- commercial priority
- commercial blocked state
- target context
- inventory context
- promotion context
- commercial signals
- decision reasons
- why-now reasons

The snapshot is idempotent and immutable.

Current Inventory, Promotion, Target, or commercial context changes do not alter the historical snapshot.

---

## Recommendation Outcome Resolution

Raw SalesOutcome records remain unchanged.

Final recommendation outcome is resolved using the canonical rule:

PURCHASED > INTERESTED > FOLLOW_UP > REJECTED > NOT_PRESENTED

Resolution is performed per:

Visit + Recommendation

Purchased quantity and sales amount are taken from the relevant purchased outcome record.

---

## Historical Outcome Context

Customer outcome history includes finalized visits only:

- COMPLETED
- CANCELLED

Historical context is factual only.

It does not perform prediction, propensity estimation, or future behavior inference.

Historical outcome context is available to:

- Customer 360
- Sales AI Context
- Prompt Builder

---

## AI Prompt Guardrails

Historical outcome facts may be summarized.

The LLM must not:

- predict future purchase behavior from historical outcomes
- convert history into probability or propensity
- infer intent from historical counts
- infer preference from historical outcome counts alone
- treat historical revenue as future revenue evidence

Recommendation decisions remain authoritative backend decisions.

The LLM must not reorder, replace, or invent recommendations.

Ollama runtime validation is postponed because Ollama is not available on the current development system.

---

## ML Learning Contract

Current source learning contract:

V2.8.11

The ML learning contract uses only immutable point-in-time-safe features.

Feature provenance explicitly identifies whether the following snapshots are used:

- customer snapshot
- commercial snapshot
- inventory snapshot
- promotion snapshot
- target snapshot

No ML model is loaded.

No ML prediction is generated.

No training is performed.

---

## Safe Dataset Builder

Dataset schema:

V2.8.12

Source contract:

V2.8.11

Unsafe historical visits without complete point-in-time snapshots are excluded.

Skipped visits receive the reason:

POINT_IN_TIME_SNAPSHOT_INCOMPLETE

This behavior is intentional.

---

## Dataset Export Contract

Export schema:

V2.8.13

The flat export contains 47 columns:

- 13 metadata columns
- 29 training feature columns
- 5 label columns

Metadata, features, and labels are strictly disjoint.

Validated:

- no metadata-feature overlap
- no metadata-label overlap
- no feature-label overlap
- CSV serializable
- JSON serializable

This prevents accidental target leakage and metadata leakage.

---

## Dataset Data Quality Validator

Quality report schema:

V2.8.14

The validator checks:

- schema contract integrity
- duplicate columns
- missing required metadata
- invalid outcome labels
- invalid binary labels
- outcome-label consistency
- invalid boolean feature types
- invalid numeric types
- negative numeric values
- missing snapshots
- duplicate learning identities
- missing-value profile

The validator does not mutate, repair, or impute data.

Validated error detection includes:

- INVALID_FINAL_OUTCOME
- INVALID_BINARY_LABEL
- PURCHASED_LABEL_MISMATCH
- INVALID_BOOLEAN_FEATURE
- NEGATIVE_NUMERIC_VALUE
- MISSING_REQUIRED_METADATA
- CUSTOMER_SNAPSHOT_MISSING

---

## Final Regression Result

Customer used for regression:

C0003

Historical outcome summary:

- historical visits: 3
- resolved recommendations: 3
- purchased: 2
- interested: 1
- follow-up: 0
- rejected: 0
- not presented: 0
- total quantity: 6
- total revenue: 20000.0

Current finalized visits in demo database:

12

Snapshot-safe finalized visits:

0

This is expected because existing historical demo visits were created before the immutable snapshot architecture was introduced.

Therefore:

- ML Dataset Builder Ready: False
- ML Dataset Export Ready: False
- Data Quality Level: NO_DATA

This is not considered a regression failure.

Historical visits without decision-time snapshots must not be retroactively reconstructed from current mutable data.

---

## Final Version Chain

V2.8.11
ML Learning Contract

↓

V2.8.12
Point-in-Time Safe Dataset Builder

↓

V2.8.13
Flat Dataset Export Contract

↓

V2.8.14
Dataset Validator and Data Quality Report

↓

V2.8.15
Final Regression / Release Checkpoint

---

## Database Migrations

Visits migrations applied:

- 0001_initial
- 0002_salesoutcome
- 0003_followuptask
- 0004_salesperson_user
- 0005_visitcustomersnapshot
- 0006_visitcommercialsnapshot
- 0007_alter_visitcommercialsnapshot_target_context

No pending model changes were detected at V2.8 close.

---

## Architecture Rules Preserved

1. Recommendation Engine remains authoritative.

2. AI explains and assists but does not replace deterministic recommendation decisions.

3. Historical outcomes remain factual and non-predictive.

4. ML features must be point-in-time safe.

5. Current mutable data must not be used to reconstruct past decision-time features.

6. Unsafe historical visits must be excluded from ML datasets.

7. Metadata, model features, and labels must remain explicitly separated.

8. ML prediction remains disabled in V2.8.

9. ML training remains disabled in V2.8.

10. Ollama runtime validation remains postponed until an Ollama-enabled system is available.

---

## Next Phase

NEXT ACTION:

V2.9

Initial scope:

- Recommendation Outcome Analytics
- Recommendation Conversion KPIs
- Management Intelligence
- Outcome / Recommendation performance APIs
- Manager-facing analytics contracts

Actual ML model training belongs to a later phase and must not begin automatically at V2.9 start.