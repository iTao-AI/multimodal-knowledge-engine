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
  -> Artifacts, Segments, Passages
  -> rebuildable retrieval projection
  -> atomic Publication switch
  -> Search / Ask Evidence
```

A failed or partial Run never changes the active Publication. Retry creates a new immutable Run.

## Planned Pilot Modules

```text
src/mke/
  core/
  ingestion/
  retrieval/
  publication/
  adapters/
  interfaces/
  runtime/
```

The domain and application layers must not depend on FastAPI, database implementations, model SDKs, LangChain, or LlamaIndex.
