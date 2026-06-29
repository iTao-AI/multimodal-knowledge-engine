# Local Dense Retrieval Candidate Autoplan Review

Status: clean and approved; PR 1 implementation is in progress. The 2026-06-29 execution amendment
below supersedes only the original prepare retry wording.

Review date: 2026-06-28

Reviewed inputs:

- `main@5ed0a722b83f9b4c70aec7c9333d8bf7d17b9335`
- [Local Dense Retrieval Candidate Design](../specs/2026-06-28-local-dense-retrieval-candidate-design.md)
- [Local Dense Retrieval Candidate Implementation Plan](../plans/2026-06-28-local-dense-retrieval-candidate-implementation.md)
- E1, E2, E3-A, E3-B, and E3-F canonical artifacts, runtime code, ADRs, tests, CLI, and CI
- current Qwen3, SentenceTransformers, Hugging Face Hub, and sqlite-vec package decisions recorded
  in the design

Review mode: selective expansion with strict comparison-only scope.

UI review: skipped because E3-C adds no graphical interface.

DX review: included because E3-C adds an optional package extra, model lifecycle CLI, evaluation
CLI, validation commands, and operator recovery paths.

## 2026-06-29 Prepare Transport Execution Amendment

### Finding

The original wording prohibited every implicit retry and required new authorization for every
additional network request. That boundary is not implementable through the pinned
`huggingface-hub==1.21.0` public API without a private monkeypatch or a project-owned downloader:

- `snapshot_download` exposes no retry-count or disable-resume parameter;
- regular HTTP performs managed Range resumes for connection, timeout, and remote-protocol errors;
- internal progress can reset its retry allowance, so request count is not strictly bounded;
- process-unique incomplete files left by a terminated process are not reused by a later process.

Building a separate downloader would exceed PR 1, weaken the supported SDK boundary, and add a
large-file supply-chain maintenance surface. The review therefore accepts an invocation-level
authorization boundary while retaining strict MKE-owned fail-closed behavior.

### Execution Evidence

Two separately authorized invocations failed before compatibility proof:

1. Default Xet reached 7 of 12 files and left an 880,731,994-byte weight partial. No cache-byte
   progress occurred for about 14 minutes while Xet workers waited through a local system proxy.
   This is evidence of a host-specific Xet no-progress stall, not evidence of a specific proxy
   implementation defect.
2. Explicit regular HTTP received 28,321,633 of 1,191,586,416 bytes before the peer closed the
   response. Hugging Face Hub then began a Range resume. The process was stopped under the older
   authorization wording and left a 262,144,000-byte process-unique partial.

Neither invocation produced a valid snapshot. Doctor, cache-ready compatibility, installed-wheel
model proof, and the compatibility artifact were not run. Both stale files remain in the external
operator cache and are neither reused nor deleted by this amendment.

### Approved Boundary

- One explicit authorization covers exactly one `prepare` process/invocation, one immutable
  model/revision/cache tuple, and one stated transport policy.
- Hugging Face Hub-managed requests and Range resumes inside that process are allowed. They are
  not described as retry-count bounded.
- MKE validates a complete exact cache without SDK network resolution. On an authorized cache
  miss it calls network `snapshot_download` exactly once with `max_workers=1`; it has no retry
  loop, second SDK call, alternate host/model/provider, or silent transport fallback.
- Doctor and operational paths remain cache-only and also use `max_workers=1` for local SDK
  resolution.
- The outer proof gate limits the process to 45 minutes total and 10 minutes without cache-byte
  progress. A limit or process failure stops execution; no new command starts automatically.
- The next host-specific proof may explicitly set `HF_HUB_DISABLE_XET=1` and
  `HF_HUB_DOWNLOAD_TIMEOUT=30`. These are proof transport inputs, not global product defaults.
- Any new process, including a restart after failure, requires new explicit authorization. Stale
  partial deletion requires separate authorization.

### Required Verification Before The Next Authorization

- Tests prove complete-cache prepare performs no SDK resolution and cache miss performs only one
  exact network `snapshot_download` call.
- Tests prove both local and network SDK calls use `max_workers=1` with the exact repository,
  revision, cache, and `local_files_only` value.
- A fake network failure maps immediately to the stable download error with no MKE reinvocation.
- The implementation plan and CLI reference carry the invocation/transport distinction and outer
  proof gates.

Outside voice: one independent Codex review ran for each applicable phase. A second configured
review voice was unavailable, so outside-voice conclusions were treated as findings to verify,
not as automatic consensus.

### Review Voice Coverage

| Phase | Primary review | Independent Codex | Second voice | Consensus status |
|---|---|---|---|---|
| CEO | complete | 8 concerns | unavailable | `codex-only`; no cross-model user challenge declared |
| Design | skipped: no UI scope | not run | not run | not applicable |
| Engineering | complete | 9 findings | unavailable | `codex-only`; every finding independently checked |
| DX | complete | 7 findings | unavailable | `codex-only`; every finding independently checked |

Missing voice is `N/A`, never treated as confirmation. No single independent finding was accepted
without checking the repository, frozen protocols, implementation plan, and current runtime
boundary.

CEO voice matrix:

| Dimension | Primary | Independent Codex | Consensus |
|---|---|---|---|
| Premises valid | narrow yes | candidate-specific caveats | `N/A`; caveats adopted |
| Right problem | bounded experiment | priority not proven globally | `N/A`; track bounded |
| Scope | comparison-only | PR 1 may be too platform-heavy | `N/A`; approved order retained |
| Alternatives | local/API/BGE/bakeoff/RRF reviewed | requested broader challenge | `N/A`; alternatives explicit |
| Market risk | not a product claim | single model can overgeneralize | `N/A`; negative candidate-specific |
| Six-month trajectory | provider-neutral boundary | avoid universal dense conclusion | `N/A`; future adapter remains open |

Engineering voice matrix:

| Dimension | Primary | Independent Codex | Consensus |
|---|---|---|---|
| Architecture | clear after amendments | partition/identity issues | `N/A`; issues closed in plan |
| Tests | full TDD matrix | tamper and tie gaps | `N/A`; adversarial cases added |
| Performance | bounded exact corpus | cutoff behavior ambiguous | `N/A`; full-distance rule added |
| Security | fixed model/cache boundary | cache symlink risk | `N/A`; same-cache blob rule added |
| Errors | stable public registry | valid-negative ambiguity | `N/A`; exit contract added |
| Delivery | two independent PRs | holdout state under-specified | `N/A`; freeze/receipt added |

DX voice matrix:

| Dimension | Primary | Independent Codex | Consensus |
|---|---|---|---|
| Getting started | staged lifecycle | install/network stages unclear | `N/A`; three install paths added |
| CLI naming | follows existing eval CLI | phase state under-specified | `N/A`; two fixed forms added |
| Errors | problem/cause/next step | negative exit ambiguous | `N/A`; JSON status check added |
| Docs | Diataxis coverage planned | cleanup missing | `N/A`; uninstall/cache cleanup added |
| Upgrade | candidate revisioned | new prompt/model behavior unclear | `N/A`; new candidate version required |
| Environment | installed-wheel proof | cache location ambiguous | `N/A`; OS default plus override added |

## Premise Review

| Premise | Verdict | Review basis |
|---|---|---|
| Remaining Chinese lexical misses justify one dense experiment | Accepted narrowly | E3-B/E3-F still miss direct Evidence in semantic, multi-condition, and hard-negative classes. E3-C is now explicitly a bounded research track, not the only product priority. |
| One immutable local model should precede an API adapter | Accepted | A local reference removes provider drift, credentials, network, hidden preprocessing, and content-upload trust from the quality comparison. |
| Qwen3-Embedding-0.6B is a defensible first candidate | Accepted as candidate-specific | Official model/package evidence supports the choice, but a negative result cannot reject dense retrieval generally. |
| Exact KNN is sufficient for the frozen corpus | Accepted | Development and holdout contain only 34 and 36 page Evidence rows respectively. Approximate search would add an uncontrolled variable. |
| Two PRs improve evidence integrity | Accepted | PR 1 proves compatibility without new dense qrel scoring; PR 2 alone performs development selection and holdout observation. |
| E3-C can prove RRF works | Rejected | E3-C may only decide whether a separate E3-D fusion experiment is justified. Runtime promotion remains untested. |

The premise gate was satisfied by the prior explicit approval of the design sections. Autoplan did
not reopen the selected model, local-first canonical path, API deferral, or two-PR delivery without
new evidence.

## Existing Code Leverage

| Sub-problem | Existing implementation | Decision |
|---|---|---|
| Model prepare/doctor | `src/mke/adapters/video/faster_whisper.py`, transcription CLI/tests | Reuse lifecycle and public-error patterns, not transcription DTOs. |
| Active Evidence snapshot | `EvaluationEvidenceSnapshot`, `SQLiteStore.list_evaluation_evidence()` | Reuse the snapshot source, then convert runtime UUIDs into stable document-locator identity. |
| Graded metrics | `src/mke/evaluation/graded_metrics.py` | Reuse exact metric semantics; add dense-specific threshold and complementarity derivations. |
| Frozen protocol loading | `chinese_protocol.py`, numeric protocol lock | Reuse strict schema/path/checksum patterns. |
| Artifact hardening | E1/E2/E3-A/E3-B artifact validators and refresh workflow | Reuse source inventory, replay, squash/shallow-clone, bool-as-int, and tamper regression patterns. |
| Installed-wheel proof | transcription, numeric, and Chinese retrieval proof scripts | Reuse external cwd, hostile environment, offline install, and installed identity gates. |
| Public errors | `src/mke/interfaces/public_errors.py` | Reuse `problem/cause/next_step` and cause allowlisting. |
| Runtime retrieval | `cjk-active-scan-overlap-v1` | Read as the future lexical arm; do not modify it in E3-C. |

## Dream State Delta

```text
CURRENT
  active-only lexical Search/Ask
  + reproducible E1/E2/E3 lexical evidence

E3-C
  + immutable local embedding reference
  + exact dense ordering
  + candidate-specific complementarity evidence
  + explicit resource and refusal trade-offs
  - no normal runtime dense behavior

12-MONTH IDEAL
  provider-neutral retrieval candidates
  + owner-selected local/API adapters
  + evidence-backed lexical/dense fusion
  + optional reranker
  + lifecycle-safe production projection
```

E3-C closes the reference-evidence gap. It intentionally does not close fusion, runtime projection,
API trust, or promotion gaps.

## Alternatives Review

| Approach | Effort | Risk | Decision |
|---|---:|---:|---|
| Local Qwen3 + exact KNN + optional sqlite-vec compatibility | Medium | Model/package/resource compatibility | Selected; preserves a reproducible canonical reference and future adapter evidence. |
| Hosted embedding API first | Medium | Provider drift, credentials, uploads, hidden preprocessing | Deferred; suitable later behind the same provider-neutral port. |
| BGE-M3 first | Medium | Larger snapshot and unused sparse/multi-vector modes | Rejected as the canonical first candidate; remains a later plan-amendment option, not fallback. |
| Development model bakeoff | Medium-high | More downloads, tuning surface, holdout contamination risk | Rejected for E3-C; one candidate keeps the hypothesis bounded. |
| Jump directly to RRF | High | Confounds embedding, threshold, fusion, and score-depth variables | Rejected until E3-C proves complementary ordered Evidence. |

## Scope Decisions

Accepted plan-hardening additions:

1. Candidate-specific negative-result wording.
2. Development residual-miss audit before dense scoring.
3. `e3d_status` means experiment eligibility only; runtime promotion remains not evaluated.
4. Threshold plateau and leave-one-query-out sensitivity reporting.
5. Provider-neutral versus local-runtime contract separation.
6. Stable document-locator identity rather than runtime UUID identity.
7. Separate development and holdout projections.
8. Committed development freeze plus exclusive holdout receipt.
9. Hugging Face cache symlink rules and sqlite-vec cutoff-tie closure.
10. Explicit two-phase CLI, valid-negative artifact/exit behavior, install-network wording, and
    manual cleanup guidance.

Rejected changes:

- Reorder PR 1 into a development-qrel bakeoff. This would mix model feasibility with candidate
  quality and weaken the approved evidence-isolation boundary.
- Remove sqlite-vec from the compatibility spike. The spike is bounded and provides evidence for a
  likely future SQLite adapter without promoting it into runtime.
- Remove the safety threshold. Dense always returns neighbors; the frozen refusal controls remain
  necessary, with sensitivity now reported honestly.
- Add a second embedding model. A negative result is now explicitly candidate-specific instead.

## Explicit Non-Scope

- Normal Search, Ask, MCP, or owner-startup dense behavior.
- Runtime default change or dense projection activation.
- Embedding API adapter, credentials, rate limits, or user-content upload.
- RRF, reranking, query rewrite, HyDE, or segmentation changes.
- Milvus, Qdrant, pgvector, Redis, external services, or approximate indexes.
- OCR, HTTP, UI, generative Ask, or legacy RAG-OCR code migration.
- Broad Chinese quality, statistical significance, Japanese/Korean, or production-scale claims.

CEO completion summary:

| Area | Result | Product consequence |
|---|---|---|
| Problem | accepted narrowly | E3-C answers one complementarity question, not all retrieval priorities |
| Candidate | accepted as immutable first test | negative applies only to this candidate configuration |
| Delivery | retain compatibility-first two-PR order | qrel scoring cannot mask package/model failure |
| Expansion | only residual audit and sensitivity added | improves interpretation without adding runtime scope |
| Deferral | API, fusion, reranker, rewrite remain separate | no false claim that E3-C ships hybrid retrieval |
| User challenge | none | only one outside voice was available, so no consensus override exists |

## Architecture Review

The amended boundary is coherent:

```text
qrel-free corpus lock                 frozen qrel protocol (PR 2 only)
         |                                      |
         v                                      v
LocalEmbeddingRuntime                     DenseComparisonRunner
  tokenize/readiness                            |
         |                                      +--> current lexical arm
         v                                      |
EmbeddingProvider <-----------------------------+
  project DTOs only                             |
         |                                      v
SentenceTransformers adapter             partition-local projection
         |                               dev 34 rows / holdout 36 rows
         v                                      |
normalized float32 tuples                        v
         +------------------------------> RankedEvidence
                                                |
                                                v
                                   artifact + replay + verdict
```

SDK objects stay inside adapters. Provider-neutral contracts contain query/document roles,
stable locator identity, vector values, and model fingerprint. Token lengths, padding, cache,
dtype, and batch size remain local-runtime concerns.

### Stable Identity

```text
runtime snapshot identity
  evidence_id + publication_id + source_id
             |
             | validate current snapshot only
             v
canonical identity
  document_id | locator_kind | locator_start | locator_end | text_sha256
```

Fresh ingest UUIDs cannot affect cross-workspace vector digests, replay, ordering, or artifacts.

### Partition Isolation

```text
development PDFs -> development SQLite -> 34-row dense projection -> development queries
holdout PDFs     -> holdout SQLite     -> 36-row dense projection -> holdout queries

cross-partition locator in results -> integrity failure
combined 70-row projection          -> compatibility/resource proof only
```

## Data And State Flow

```text
PR 1
  install optional extra
  -> explicit prepare (only networked mke model action)
  -> cache-only doctor
  -> qrel-free tokenize/embed/projection compatibility
  -> Python 3.12/3.13 installed-wheel proof
  -> compatibility artifact

PR 2
  validate PR 1 artifact
  -> audit development misses
  -> build development-only projection
  -> select threshold + sensitivity
  -> write development freeze
  -> commit freeze
  -> build holdout-only projection exactly once
  -> exclusive-create holdout receipt
  -> canonical comparison artifact
  -> model-free validation + cache-ready replay
```

State machine:

```text
UNPREPARED
  -> PREPARED
  -> COMPATIBLE
  -> DEVELOPMENT_AUDITED
  -> DEVELOPMENT_SCORED
       |-> VALID_NEGATIVE (holdout not observed, terminal)
       `-> DEVELOPMENT_FROZEN
              -> HOLDOUT_OBSERVED
              -> ARTIFACT_RECORDED
              -> E3D_ELIGIBLE | E3D_NOT_ELIGIBLE

Any identity/integrity failure -> FAILED (no fallback, no promotion)
```

## Error And Rescue Registry

| Codepath | Failure | Public result | Rescue | Test |
|---|---|---|---|---|
| optional adapter import | dependency missing | `embedding_dependency_missing` | install `embedding` extra | unit + wheel core/extra |
| prepare | unsupported model/revision | usage exit 2 | use allowlisted default | CLI unit |
| prepare | download failure | redacted operational error | check network, request bounded retry | adapter + CLI |
| doctor | cache absent/incomplete | `not_ready`, exit 1 | run exact prepare | adapter + CLI |
| snapshot manifest | cross-cache/dangling link or mutation | integrity failure | restore exact snapshot | symlink/tamper tests |
| tokenizer preflight | Evidence exceeds 8192 | stop condition | amend plan/model/input | cache-ready proof |
| embedding adapter | count/dimension/dtype/norm/non-finite failure | stable adapter error | inspect exact model/runtime | fake-adapter unit |
| projection build | partial/identity mismatch | discard temporary projection | rebuild from snapshot | transaction test |
| sqlite-vec | unavailable/incompatible | structured compatibility rejection | select exact reference only if its gates pass | Python 3.12/3.13 proof |
| threshold selection | no safe threshold | valid negative, exit 0 | no holdout; record artifact | comparison/CLI |
| development freeze | identity mismatch or existing conflicting file | integrity failure | restore committed freeze | protocol/CLI |
| holdout receipt | receipt already exists | refuse rerun | preserve first receipt | exclusive-create test |
| artifact validate | derived inconsistency | exit 1 | restore/regenerate through workflow | adversarial mutations |
| replay | model/vector/order/score mismatch | exit 1 | inspect cache/runtime/projection | cache-ready tamper tests |

No mapped error is silent. Absolute paths, raw SDK errors, cache internals, URLs with query data,
and tracebacks remain redacted from public output.

## Security And Trust Review

- Supply chain is limited to pinned dependency versions plus an exact allowlisted model revision.
- `trust_remote_code` is prohibited.
- Model cache symlinks may resolve only to regular files under the same model cache `blobs/`
  directory; cross-cache, chained, dangling, device, and directory links fail.
- Search/Ask/MCP do not accept model, cache, endpoint, credential, or adapter inputs.
- Only explicit prepare may download model files after installation.
- Evaluation never uploads fixture or user content.
- Cache deletion is manual; MKE never deletes operator model caches.

## Test Coverage Diagram

```text
model spec/contracts
  -> unit: scalar/type/count/dimension/norm/identity
readiness + cache manifest
  -> unit: allowlist/network/symlink/hash/incomplete/mutation
SentenceTransformers adapter
  -> fake unit + cache-ready integration
exact cosine + sqlite-vec
  -> synthetic unit + cutoff tie + transaction + cross-version wheel
compatibility runner
  -> qrel-free integration + installed-wheel 3.12/3.13 + resource ceilings
protocol + residual audit
  -> strict schema + dev-only + frozen identity
threshold selection
  -> pure unit + plateau + leave-one-out + valid-negative
comparison state machine
  -> partition isolation + freeze-before-holdout + exclusive receipt
artifact validator
  -> model-free derivation/tamper/shallow-squash tests
cache-ready replay
  -> actual model/vector/order/score/coordinated-tamper tests
CLI/docs
  -> usage/error/exit/help/copy-paste/link/install-path tests
```

The test pyramid is unit-heavy, with bounded integration and two installed-wheel proofs. No test
may depend on a live model host after preparation. Cache-ready tests require the exact pre-authorized
snapshot and remain outside required model-free CI.

## Performance Review

The principal slow paths are model load, document embedding, and one query embedding. The plan
records load duration, projection build duration, median/p95 query latency, peak RSS, snapshot
bytes, and projection bytes. The ceilings remain feasibility limits, not production claims.

The sqlite-vec adapter retrieves all 34 or 36 partition distances before project-owned rounding,
tie-breaking, and top-10 truncation. This closes the rank-10/rank-11 portable-score tie without a
material performance cost at the frozen scale.

## Observability And Debuggability

Canonical artifacts provide the durable diagnostics: exact package/model/projection identity,
threshold trace, sensitivity, ordered results, complementarity IDs, resource measurements, gates,
and limitations. Public CLI JSON is the automation surface. Internal logs may retain exception
class and phase but must not expose cache paths or model contents publicly.

No production dashboard or alert is justified because E3-C does not add a production runtime
path. Cache doctor, artifact validator, and replay are the required operator diagnostics.

## Delivery, Rollback, And Cleanup

```text
planning docs merge
  -> PR 1 prerequisites merge
  -> fresh PR 2 from main
  -> development freeze commit
  -> one holdout receipt + artifact
  -> authoritative pre-PR review
  -> Ready PR + CI
```

Rollback is deletion of the evaluation-only PR before merge or a later normal revert. No database
migration, runtime strategy, or active Publication changes. If the candidate is negative, the
optional extra and CLI remain comparison-only unless a separate removal PR is approved. Operators
may uninstall the extra and manually delete the cache; MKE performs neither action automatically.

Reversibility: 4/5. The dependency lock and public comparison CLI are durable once released, but
they remain optional and off the normal runtime path.

Engineering completion summary:

| Area | Result | Remaining action |
|---|---|---|
| Architecture | clear after provider/local split and stable locator identity | implement by TDD |
| Evidence integrity | clear after partition isolation, freeze/receipt, and replay boundary | implement adversarial tests |
| Performance | bounded by exact corpus size and explicit resource gates | measure PR 1 before qrels |
| Security | clear after exact revision, no remote code, cache-link, and redaction rules | verify installed wheel |
| Delivery | two independent PRs with stop conditions | merge PR 1 before PR 2 |

## DX Review

Primary persona: a Python developer or Agent-tool integrator reproducing local retrieval evidence.

Developer empathy narrative:

> I need to know whether I am installing packages, downloading a model, checking readiness, or
> running a comparison. Each command must do one of those things. If evaluation finishes but the
> candidate is negative, the shell should tell me the run was trustworthy while JSON tells my
> automation not to continue to E3-D. I should never discover that an “offline” command contacted
> the network or that a rerun overwrote the first holdout result.

### Developer Journey

| Stage | Expected path | Main friction | Required mitigation |
|---|---|---|---|
| Discover | README/docs index | comparison versus runtime ambiguity | first-screen comparison-only statement |
| Install | checkout, `wheel[embedding]`, or offline wheelhouse | large transitive runtime | exact commands and size warning |
| Prepare | `mke embedding prepare --allow-model-download` | ~1.19 GB model and authorization | exact revision/default, progress, bounded retry policy |
| Diagnose | `mke embedding doctor --json` | incomplete cache or dependency mismatch | stable checks and next step |
| Development | `retrieval-dense --development-only` | threshold interpretation | full trace, plateau, sensitivity |
| Freeze | record and commit development freeze | sequencing error | command-enforced phase flags |
| Holdout | consume freeze, exclusive receipt | accidental rerun | existing-receipt refusal |
| Validate | model-free validate + cache-ready replay | different oracle capabilities | docs state which tampering each catches |
| Clean up | uninstall optional extra / manual cache removal | negative candidate leaves large cache | package-specific and manual cleanup guide |

Estimated first cache-ready proof is dominated by package/model acquisition rather than CLI steps.
After an offline wheelhouse and model cache are populated, target TTHW is under 5 minutes for
doctor plus compatibility proof and under 10 minutes for a bounded comparison replay, subject to
the measured CPU model-load ceiling.

### DX Scorecard

| Dimension | Initial | After amendment | Evidence |
|---|---:|---:|---|
| Getting started | 6 | 8 | Three installation paths and exact lifecycle order are required. |
| CLI/API consistency | 7 | 9 | `embedding prepare/doctor` mirrors transcription; eval uses two explicit phases. |
| Error/debugging | 8 | 9 | Stable error registry, doctor, validator, and replay. |
| Documentation/findability | 7 | 9 | README, docs index, CLI reference, how-to, and architecture coverage. |
| Upgrade/removal | 4 | 8 | New candidate revision rule, uninstall guidance, manual cache cleanup. |
| Environment/tooling | 6 | 8 | Core/extra isolation and Python 3.12/3.13 wheel proof. |
| Ecosystem fit | 7 | 8 | Standard optional extra, HF cache, SQLite-local adapter boundary. |
| Feedback loop | 8 | 9 | Canonical artifact, sensitivity, model-free CI, cache-ready replay. |
| **Overall** | **6.6** | **8.5** | No unresolved DX blocker. |

### DX Implementation Checklist

- [ ] Document checkout, online wheel-extra, and offline wheelhouse installs.
- [ ] Show prepare/doctor/development/freeze/holdout/validate/replay in exact order.
- [ ] Reject repository-local caches and document OS default/environment override.
- [ ] Make phase flags mutually exclusive and required.
- [ ] Explain exit `0` versus `e3d_status` with a JSON automation example.
- [ ] Document candidate versioning, uninstall, and manual cache cleanup.
- [ ] Keep Search/Ask/MCP help and schemas unchanged.

DX completion summary: initial completeness `6.6/10`, amended target `8.5/10`. Cache-ready TTHW
after package and model acquisition targets under five minutes for doctor plus compatibility proof;
the one-time model acquisition remains an explicit prerequisite rather than hidden setup time.

## Cross-Phase Themes

Three concerns appeared independently across strategy, engineering, and DX review:

1. **A trustworthy negative is a product result.** The artifact, exit contract, and documentation
   must distinguish completed/not-eligible from an operational failure.
2. **Offline claims need phase boundaries.** Package installation, explicit model preparation,
   cache-only operation, and manual cleanup are separate user journeys.
3. **Stable evidence beats runtime identity.** Partition ownership, locator identity, freeze state,
   and replay must remain valid across fresh ingests and squash-landed clones.

These are high-confidence themes because each affects both evidence integrity and the operator
experience. All three are represented in the amended plan and acceptance checklist.

## Failure Modes Registry

| Codepath | Failure mode | Rescued | Test | User sees | Logged |
|---|---|---:|---:|---|---:|
| install | missing optional package | yes | yes | install extra | yes |
| prepare | invalid model/revision/cache | yes | yes | usage/recovery | yes |
| prepare | network/download failure | yes | yes | redacted recovery | yes |
| doctor | incomplete/mutated cache | yes | yes | not-ready checks | yes |
| embed | truncation/shape/norm/non-finite | yes | yes | stable failure | yes |
| projection | partial/cross-partition/identity mismatch | yes | yes | integrity failure | yes |
| development | no safe threshold | yes | yes | valid negative | artifact |
| holdout | no freeze or existing receipt | yes | yes | usage/integrity failure | yes |
| artifact | false derived verdict | yes | yes | invalid artifact | yes |
| replay | coordinated observation substitution | yes | yes | replay mismatch | yes |

Critical silent gaps after amendment: zero.

## Review Conclusion

The amended E3-C design is implementable and bounded. It preserves the current runtime, isolates
model feasibility from quality scoring, closes partition and stable-identity gaps, makes the
single-holdout sequence auditable, and defines honest positive and negative terminal outcomes.

The plan remains deliberately rigorous for a small corpus because prior retrieval stages exposed
artifact-integrity gaps only after adversarial replay. This review applies that prior learning by
separating model-free derivation validation from cache-ready retrieval replay.

No unresolved architecture, product, security, engineering, or DX decision remains in the amended
plan. Final approval was recorded on 2026-06-28; the implementation handoff may proceed.
