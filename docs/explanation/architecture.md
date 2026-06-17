# Architecture

## Product Boundary

Multimodal Knowledge Engine converts documents and media into published Evidence that users and Agents can search, cite, and ask questions over.

## Domain Vocabulary

`Library`, `Source`, `Asset`, `Run`, `Artifact`, `Segment`, `Passage`, `Evidence`, and `Publication` are the public product concepts.

## Lifecycle

```text
Source
  -> immutable Asset
  -> observable Run
  -> candidate Evidence and RunManifest
  -> validated Run
  -> active Search projection
  -> atomic Publication switch
  -> Search / Ask Evidence
```

A failed, interrupted, superseded, or partial Run never changes the active Publication. Retry
creates a new immutable Run.

The current PDF and short-video slices implement only the lifecycle concepts needed to prove
trustworthy Search:
`Library`, `Source`, `Asset`, `Run`, `Evidence`, `RunManifest`, and `Publication`. `Artifact`,
`Segment`, and `Passage` remain public vocabulary for later cross-modal and Ask workflows, but
their durable semantics are not stabilized before the PDF and video slices validate the lifecycle.

## Publication Semantics

Publication is atomic per `Source`.

```text
candidate Evidence + RunManifest
  -> validate counts, locators, extractor fingerprint, required stages
  -> check Run generation and Source active revision
  -> create Publication
  -> replace this Source's active FTS5 rows
  -> switch Source.active_publication_id
  -> mark Run published
```

Candidate, failed, superseded, or historical output is not stored in the active FTS5 projection.
Search reads only active Publication rows and joins back through the active Publication identity.
A stale Run that loses the Source generation or active revision check is marked `superseded`
without changing active Search visibility.

## Current Runtime Shape

The runtime is an in-process CLI plus a project-owned application service. SQLite remains the
domain truth and owns the rebuildable active FTS5 projection. The built-in PDF adapter extracts
page-addressed text Evidence from deterministic text-layer PDFs. The built-in video adapter reads
timestamp-addressed transcript Evidence from a deterministic local sidecar for the documented
short MP4 fixture profile. The proof path uses no external services, credentials, model downloads,
OCR, real speech-model transcription, or network calls.

## Current Module Shape

```text
src/mke/
  domain/
  application/
  adapters/
    pdf/
    sqlite/
    video/
  interfaces/
  proof/
```

The domain and application layers must not depend on FastAPI, database implementations, model SDKs, LangChain, or LlamaIndex.
