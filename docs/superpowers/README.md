# Superpowers Workspace

This directory is artifact storage for approved public-neutral designs, implementation plans, and
durable reviews. These records are implementation history, not current contract authority.

For current behavior and obligations, use this precedence:

1. code and tests;
2. accepted ADRs;
3. current reference documentation and release documentation; and
4. these historical design, plan, and review artifacts.

Historical skill or subagent wording does not override the current `AGENTS.md`. When an old plan
conflicts with current code, tests, an accepted ADR, or current public documentation, report the
conflict and follow the higher authority rather than silently reviving historical instructions.

Artifacts are grouped under [`specs/`](./specs/), [`plans/`](./plans/), and
[`reviews/`](./reviews/).

For the current Source discovery/read workflow, start with
[ADR-0014](../decisions/0014-source-discovery-and-browsing.md),
[the MCP reference](../reference/mcp-contract.md) and
[the independent walkthrough](../how-to/discover-and-read-sources.md). The approved Source design,
[completed plan](./plans/2026-10-01-source-discovery-read-implementation.md) and
[final local review](./reviews/2026-10-01-source-discovery-read-review.md) record implementation
history; their placement does not imply release publication.
