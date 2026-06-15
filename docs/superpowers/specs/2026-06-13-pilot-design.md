# Multimodal Knowledge Engine Pilot Design

Status: Superseded for active implementation order by
`docs/superpowers/specs/2026-06-15-trustworthy-pdf-video-slice-design.md`.

This document remains historical bootstrap context. The active implementation plan now proves
trustworthy PDF Search first, then adds the short-video slice, before stabilizing broader
HTTP, MCP, Ask, or workspace contracts.

## Goal

Build a local-first Evidence engine whose first verified slice processes one PDF and one short video, publishes only complete output, and returns page- or timestamp-addressable Evidence through consistent HTTP, CLI, MCP, and workspace contracts.

## Constraints

- Do not copy the legacy service layout or APIs.
- SQLite is Pilot domain truth; retrieval indexes are rebuildable projections.
- Required-stage failure prevents Publication switching.
- Public paths do not use `/api`, `/v1`, or `/v2`.
- Provider and framework choices remain behind project-owned ports.
- No hosted multi-tenant platform, RBAC, distributed worker, or automatic deployment in the Pilot.

## Delivery Slices

1. Bootstrap and documentation governance.
2. Evidence Core and Publication lifecycle.
3. Text-layer PDF ingestion with page Evidence.
4. Hybrid retrieval and low-confidence refusal.
5. Video and audio ingestion with timestamp Evidence.
6. HTTP, CLI, MCP, and minimal workspace.
7. Eval, hardening, and verified demo.

## Acceptance

The Pilot is accepted only when an actual PDF and short video complete observable Runs, become active Publications, produce stable Evidence locators, and support reliable Ask or explainable refusal.
