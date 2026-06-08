# Concepts

Shared domain vocabulary for this project — entities, named processes, and status concepts with project-specific meaning. Seeded with core domain vocabulary, then accretes as ce-compound and ce-compound-refresh process learnings; direct edits are fine. Glossary only, not a spec or catch-all.

---

## Scan Pipeline

### Scan

A product analysis request initiated by a user. The user submits a product identifier (barcode, image, or manual entry); the Scan is the lifecycle event that runs the full pipeline and produces a structured risk report with ingredient breakdown, regulatory findings, and personalized health signals.

### Scan Pipeline

The multi-stage agentic flow that processes a Scan. Organized as a directed graph of sequential nodes — from product identification through ingredient extraction, entity resolution, regulatory lookup, biomarker cross-reference, conflict detection, personalization, and risk calculation. Each node is a pure function over the Scan's shared state; nodes do not communicate directly with each other.

### Pipeline Node

A single processing stage in the Scan Pipeline. Each node receives the accumulated scan state, performs a specific analysis step (typically involving an LLM call, vector search, or database lookup), and returns an updated state. Nodes are registered statically at pipeline-build time; the pipeline itself is compiled before a Scan begins.
