# ADR-0001: Local-First Pilot Architecture

- Status: Accepted
- Date: 2026-06-13

## Context

The Pilot must be useful for personal PDF and video learning workflows while demonstrating reliable Agent-callable Evidence. It must avoid recreating a multi-service legacy layout before the core lifecycle is proven.

## Decision

- Use project-owned domain models and ports.
- Use SQLite as domain truth for the Pilot.
- Treat retrieval indexes as rebuildable projections.
- Keep Assets and Artifacts immutable and content-addressed.
- Allow Search and Ask to read only active Publications.
- Run one local owner process with one worker.
- Keep LangChain, LlamaIndex, LangGraph, Milvus, Redis, PostgreSQL, and pgvector outside the Pilot core.

## Consequences

- The local workflow stays lightweight and deterministic.
- A future storage or retrieval adapter can be evaluated without changing public domain contracts.
- Multi-instance execution and hosted platform concerns are deferred.
