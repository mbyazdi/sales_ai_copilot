# Task 001-D — Demo continuity hardening

Baseline: fast-track, bacd1d5. No domain/schema or authorization policy change.

- Customer360 search preserves a validated visit for the same customer. Changing
  the customer drops the hidden visit parameter; server-side matching independently
  rejects invalid, nonexistent and other-customer visit IDs with a Persian warning.
  Workspace and follow-up entry links already contain their original visit IDs.
  Ordinary customer navigation does not select a visit automatically.
- Customer-only Customer360 uses the existing product commercial-context builder
  when a primary recommendation exists. Sales-session normalization previously
  ran only for HIGH_VALUE customers; it now applies to every segment. An absent
  recommendation retains null product identity and empty product-specific signals.
  Customer360 and Sales Copilot explicitly explain that no active recommendation
  exists. Copilot does not invoke Ollama in that state.
- Management returns its existing not-ready response structure for empty source
  data instead of attempting narration of an unready context. Real ready-data
  executive narration continues to use deterministic authoritative facts.
- Optional sales/executive Ollama calls use the lower of configured timeout and
  five seconds. Sales provider errors retain the approved deterministic wording
  and explicitly announce AI unavailability. Unexpected sales-generation errors
  are not converted to successful deterministic responses. Existing management
  provider-failure handling remains in place.

The timeout is a synchronous socket timeout, not a strict total request deadline.
No live Ollama or browser responsiveness verification is required by the automated
regressions. New sale modes, role hierarchy, UI redesign, recommendation scoring,
visit lifecycle semantics and demo-data changes remain outside this task.

Regression coverage: apps/visits/tests_continuity.py. Fixtures are isolated from
the tracked database, and all provider calls are mocked.
