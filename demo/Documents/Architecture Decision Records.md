# Architecture Decision Records

## ADR-007: Use SQLite FTS5 for content search

- **Status:** accepted
- **Date:** 2026-06-24

We evaluated Elasticsearch, Meilisearch and SQLite FTS5 for content search.
FTS5 keeps the deployment a single process, indexes one million documents in
under an hour on a laptop, and query latency stays below 30 ms at that size.
We accept that ranking is simpler than in a dedicated engine.

## ADR-008: Multipart uploads with 8 MiB parts

- **Status:** accepted
- **Date:** 2026-06-30

Uploads are split into 8 MiB parts so that a dropped connection costs at most
one part. Smaller parts increased request overhead on S3; larger parts made
progress reporting too coarse on slow links.

## ADR-009: Soft delete with a fourteen day window

- **Status:** accepted
- **Date:** 2026-07-02

Deleted files are kept for fourteen days. This matches the data retention
policy and gives support enough time to restore accidental deletions.
