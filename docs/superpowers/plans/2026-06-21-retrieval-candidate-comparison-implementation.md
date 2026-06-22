# Numeric Retrieval Candidate Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze an independent numeric development/holdout challenge set, compare the off-default
`numeric-grouping-v1` query policy with current behavior, and promote it only in a separate PR if
every invariant and regression gate passes.

**Architecture:** Reuse the strict E1 manifest, snapshot, ingestion, metrics, report, and
determinism path. Add one project-owned query-policy compiler and a narrow comparator that runs
development, holdout, and E1 under both allowlisted policies. Normal CLI/MCP composition keeps the
`current` policy until an ADR-backed promotion PR changes only the default identifier.

**Tech Stack:** Python 3.12/3.13, stdlib dataclasses/JSON/hashlib/tempfile/re, SQLite FTS5,
PyMuPDF, pytest, argparse, GitHub Actions.

**Approved design:**
`docs/superpowers/specs/2026-06-21-retrieval-candidate-comparison-design.md`

**Approved review:**
`docs/superpowers/reviews/2026-06-21-retrieval-candidate-comparison-autoplan-review.md`

**Implementation boundary:** Do not change E1 fixtures, queries, qrels, metric definitions, normal
report schema, Publication semantics, Evidence segmentation, FTS5 schema/tokenizer/ranking SQL,
Search/Ask DTOs, transcription behavior, or the runtime default in PR 1. Do not add a dependency,
model, network call, migration, arbitrary query rewriter, second Search query, CJK slice, semantic
slice, or video fixture.

---

## Delivery Sequence

| PR | Result | Runtime default |
|---|---|---|
| PR 1 | Frozen numeric protocol, off-default candidate, comparison artifact | `current` |
| PR 2 | Conditional ADR-backed promotion and rollback proof | `numeric-grouping-v1` only if all gates passed |

PR 2 is conditional. A valid rejected-candidate artifact completes E2 without promotion.

## File Map

### PR 1: Comparison

- Create `tests/fixtures/retrieval-numeric-v1/development.pdf`.
- Create `tests/fixtures/retrieval-numeric-v1/holdout.pdf`.
- Create `tests/fixtures/retrieval-numeric-v1/development.json`.
- Create `tests/fixtures/retrieval-numeric-v1/holdout.json`.
- Create `tests/fixtures/retrieval-numeric-v1/protocol-lock.json`.
- Create `tests/fixtures/retrieval-numeric-v1/README.md`.
- Create `src/mke/retrieval/__init__.py`.
- Create `src/mke/retrieval/query_policy.py`.
- Modify `src/mke/adapters/sqlite/__init__.py`.
- Modify `src/mke/application/__init__.py`.
- Modify `src/mke/evaluation/runner.py`.
- Create `src/mke/evaluation/numeric_comparison.py`.
- Create `src/mke/evaluation/numeric_artifact.py`.
- Modify `src/mke/evaluation/baseline.py` to share a private source-content identity helper.
- Modify `src/mke/evaluation/__init__.py`.
- Modify `src/mke/cli.py`.
- Create `tests/retrieval/test_query_policy.py`.
- Modify `tests/adapters/test_sqlite_fts.py`.
- Create `tests/evaluation/test_numeric_fixture_corpus.py`.
- Create `tests/evaluation/test_numeric_comparison.py`.
- Create `tests/evaluation/test_numeric_artifact.py`.
- Modify `tests/evaluation/test_runner.py`.
- Modify `tests/interfaces/test_cli_evaluation.py`.
- Create `benchmarks/retrieval/numeric-grouping-v1-comparison.json`.
- Refresh only the complete source identity in
  `benchmarks/retrieval/retrieval-eval-v1-baseline.json`.
- Modify `.github/workflows/ci.yml`.
- Create `docs/how-to/evaluate-numeric-retrieval.md`.
- Modify `docs/how-to/run-retrieval-evaluation.md`.
- Modify `docs/reference/cli.md`, `docs/explanation/architecture.md`, `docs/README.md`,
  `README.md`, and `README_CN.md`.
- Update the E2 spec, plan, and durable review.

### PR 2: Conditional Promotion

- Create `docs/decisions/0007-numeric-grouping-query-policy.md`.
- Modify `src/mke/retrieval/query_policy.py`.
- Modify `src/mke/runtime.py` and `src/mke/cli.py`; MCP reuses `RuntimeConfig`.
- Create `scripts/numeric_retrieval_deployment_proof.py`.
- Add promotion/rollback contract tests.
- Update Search/Ask references and architecture documentation.
- Refresh E1 and numeric comparison artifact source identities.

---

## PR 1: Frozen Protocol And Off-Default Candidate

### Task 1: Add Frozen Development And Holdout PDF Fixtures

**Files:**
- Create: `tests/fixtures/retrieval-numeric-v1/development.pdf`
- Create: `tests/fixtures/retrieval-numeric-v1/holdout.pdf`
- Create: `tests/fixtures/retrieval-numeric-v1/README.md`
- Create: `tests/evaluation/test_numeric_fixture_corpus.py`

- [x] **Step 1: Write the failing fixture test**

Create a test with the exact page text from the approved design:

```python
EXPECTED_PAGES = {
    "development.pdf": (
        "Grouped daily withdrawal total: 410,000 million gallons.",
        "Compact inventory total: 730000 storage units.",
        "Non-adjacent ledger values: 410 units were accepted; after review, 000 units were rejected.",
        "Identifiers: postal district 02139; equipment model ZX410000; reporting year 2005.",
    ),
    "holdout.pdf": (
        "Grouped reserve capacity: 57,600 cubic meters.",
        "Compact shipment count: 880000 sealed packages.",
        "Non-adjacent audit values: 57 samples passed; later, 600 samples failed.",
        "Identifiers: postal district 00701; sensor model AB57600; reporting year 1997.",
    ),
}
```

The test must require:

- exactly four pages per PDF;
- exact normalized extracted page text;
- exact byte size and SHA-256 from the fixture README;
- different PDF bytes and no shared exact page text.

- [x] **Step 2: Run the fixture test to verify RED**

Run:

```bash
uv run pytest tests/evaluation/test_numeric_fixture_corpus.py -q
```

Expected: FAIL because both fixtures are absent.

- [x] **Step 3: Generate both PDFs outside the repository**

Create `/tmp/mke-retrieval-numeric-v1/generate.py` using the installed `fitz` package:

```python
from pathlib import Path

import fitz

PAGES = {
    "development.pdf": (
        "Grouped daily withdrawal total: 410,000 million gallons.",
        "Compact inventory total: 730000 storage units.",
        "Non-adjacent ledger values: 410 units were accepted; after review, 000 units were rejected.",
        "Identifiers: postal district 02139; equipment model ZX410000; reporting year 2005.",
    ),
    "holdout.pdf": (
        "Grouped reserve capacity: 57,600 cubic meters.",
        "Compact shipment count: 880000 sealed packages.",
        "Non-adjacent audit values: 57 samples passed; later, 600 samples failed.",
        "Identifiers: postal district 00701; sensor model AB57600; reporting year 1997.",
    ),
}

root = Path("/tmp/mke-retrieval-numeric-v1")
root.mkdir(parents=True, exist_ok=True)
for name, pages in PAGES.items():
    document = fitz.open()
    for text in pages:
        page = document.new_page(width=612, height=792)
        written = page.insert_textbox(
            fitz.Rect(72, 72, 540, 720),
            text,
            fontsize=12,
            fontname="helv",
        )
        if written < 0:
            raise RuntimeError(f"page text did not fit: {name}")
    document.set_metadata(
        {
            "title": f"MKE numeric retrieval fixture: {name}",
            "author": "Multimodal Knowledge Engine",
            "subject": "Deterministic numeric retrieval evaluation",
        }
    )
    document.save(root / name, garbage=4, deflate=True, clean=True)
    document.close()
```

Run the script with `uv run python`, then inspect exact extracted text, page count, byte size, and
SHA-256. This uses an existing pinned dependency and performs no network access.

- [x] **Step 4: Copy only verified PDFs and add provenance**

Copy both PDFs after verification. Record the exact generator, PyMuPDF version, pages, byte sizes,
SHA-256 values, public holdout limitation, and narrow claim in the README.

- [x] **Step 5: Run fixture verification**

Run:

```bash
uv run pytest tests/evaluation/test_numeric_fixture_corpus.py -q
git diff --check
```

Expected: all fixture tests pass.

- [x] **Step 6: Commit the frozen fixture task**

Stage only the fixture directory and fixture test. Commit:

```text
test(eval): add frozen numeric retrieval fixtures
```

### Task 2: Add Development, Holdout, And Protocol-Lock Manifests

**Files:**
- Create: `tests/fixtures/retrieval-numeric-v1/development.json`
- Create: `tests/fixtures/retrieval-numeric-v1/holdout.json`
- Create: `tests/fixtures/retrieval-numeric-v1/protocol-lock.json`
- Modify: `tests/evaluation/test_numeric_fixture_corpus.py`

- [x] **Step 1: Write failing inventory and lock tests**

Use the existing `mke.retrieval_eval.v1` manifest schema. Require the exact seven queries and qrels
per partition from the design.

Add tests that require:

```python
assert development["manifest_id"] == "retrieval-numeric-v1-development"
assert holdout["manifest_id"] == "retrieval-numeric-v1-holdout"
assert {query["query_id"] for query in development["queries"]}.isdisjoint(
    query["query_id"] for query in holdout["queries"]
)
assert {query["text"] for query in development["queries"]}.isdisjoint(
    query["text"] for query in holdout["queries"]
)
```

The protocol lock must bind both manifest hashes, both PDF identities, E1 manifest SHA-256,
candidate ID, semantic candidate revision `1`, and protocol claim. Resolve its three exact paths
against `protocol_path.parent.parent`; reject absolute paths, `..`, symlink escape, and alternate
layouts before engine construction.

- [x] **Step 2: Run the inventory test to verify RED**

Run:

```bash
uv run pytest tests/evaluation/test_numeric_fixture_corpus.py -q
```

Expected: FAIL because the manifests and lock are absent.

- [x] **Step 3: Add exact manifests**

Each manifest contains one PDF document. Query categories remain E1-compatible:

- positive controls use `answerable`;
- non-adjacent-token controls use `lexical_confuser`;
- unrelated controls use `out_of_corpus`.

Every answerable query has exactly one relevant page.

- [x] **Step 4: Add strict protocol-lock validation tests**

Mutate each manifest, fixture, E1 manifest identity, candidate ID, candidate revision, protocol
claim, and lock field. Add path tests for absolute paths, `..`, symlink escape, and wrong layout.
Every mutation must fail with a stable redacted cause.

- [x] **Step 5: Run E1 parser and fixture suites**

Run:

```bash
uv run pytest \
  tests/evaluation/test_manifest.py \
  tests/evaluation/test_fixture_corpus.py \
  tests/evaluation/test_numeric_fixture_corpus.py -q
```

Expected: all tests pass and E1 remains unchanged.

- [x] **Step 6: Commit the frozen protocol task**

Commit:

```text
test(eval): freeze numeric retrieval protocol
```

### Task 3: Extract The Current Query Compiler Without Behavior Change

**Files:**
- Create: `src/mke/retrieval/__init__.py`
- Create: `src/mke/retrieval/query_policy.py`
- Modify: `src/mke/adapters/sqlite/__init__.py`
- Modify: `src/mke/application/__init__.py`
- Create: `tests/retrieval/test_query_policy.py`
- Modify: `tests/adapters/test_sqlite_fts.py`

- [x] **Step 1: Write current-policy characterization tests**

Require exact current compilation:

```python
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("", ""),
        ("hello world", '"hello" "world"'),
        ("410000 withdrawals", '"410000" "withdrawals"'),
        ("410,000 withdrawals", '"410" "000" "withdrawals"'),
        ("02139 postal district", '"02139" "postal" "district"'),
        ("ZX410000 equipment model", '"zx410000" "equipment" "model"'),
        ("火山灰 航空安全", ""),
        ("* : ( ) NEAR", '"near"'),
    ],
)
def test_current_policy_preserves_existing_compilation(query: str, expected: str) -> None:
    assert compile_fts5_query(query, policy="current") == expected
```

- [x] **Step 2: Run characterization tests to verify RED**

Run:

```bash
uv run pytest tests/retrieval/test_query_policy.py -q
```

- [x] **Step 3: Implement allowlisted policy types**

Implement:

```python
RetrievalQueryPolicy = Literal["current", "numeric-grouping-v1"]
DEFAULT_RETRIEVAL_QUERY_POLICY: RetrievalQueryPolicy = "current"


def compile_fts5_query(
    query: str,
    *,
    policy: RetrievalQueryPolicy = DEFAULT_RETRIEVAL_QUERY_POLICY,
) -> str:
    if policy == "current":
        return _compile_current(query)
    if policy == "numeric-grouping-v1":
        return _compile_numeric_grouping(query)
    raise ValueError("retrieval query policy is unsupported")
```

- [x] **Step 4: Inject policy at composition**

Add a keyword-only `query_policy` to `SQLiteStore` and `KnowledgeEngine`. Store the validated
literal and use it only when compiling `MATCH`. Normal runtime callers omit it and retain
`current`.

- [x] **Step 5: Prove behavior equivalence**

Run:

```bash
uv run pytest \
  tests/retrieval/test_query_policy.py \
  tests/adapters/test_sqlite_fts.py \
  tests/application/test_ask.py \
  tests/application/test_pdf_publication.py \
  tests/application/test_video_publication.py \
  tests/interfaces/test_mcp_contract.py -q
uv run mke eval retrieval \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --json > /tmp/e1-current-after-extraction.json
```

Expected: all tests pass and the semantic E1 result matches the canonical observation.

- [x] **Step 6: Commit compiler extraction**

Commit:

```text
refactor(retrieval): expose explicit query policy
```

### Task 4: Implement The Bounded Numeric Disjunction

**Files:**
- Modify: `src/mke/retrieval/query_policy.py`
- Modify: `tests/retrieval/test_query_policy.py`
- Modify: `tests/adapters/test_sqlite_fts.py`

- [x] **Step 1: Write failing candidate compiler tests**

Require:

```python
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            "410000 million gallons",
            '("410000" OR "410 000") AND "million" AND "gallons"',
        ),
        (
            "25600 public supply",
            '("25600" OR "25 600") AND "public" AND "supply"',
        ),
        ("02139 postal district", '"02139" "postal" "district"'),
        ("ZX410000 equipment model", '"zx410000" "equipment" "model"'),
        ("2005 reporting year", '"2005" "reporting" "year"'),
        ("火山灰 航空安全", ""),
    ],
)
def test_numeric_grouping_policy(query: str, expected: str) -> None:
    assert compile_fts5_query(query, policy="numeric-grouping-v1") == expected
```

For every query without an eligible token, assert the candidate compiler equals the current
compiler exactly.

- [x] **Step 2: Write failing SQLite adversarial tests**

Insert rows containing:

- adjacent grouped text using comma, space, hyphen, and slash separators;
- compact text `410000`;
- non-adjacent text with another token between `410` and `000`;
- leading-zero `02139`;
- alphanumeric `ZX410000`.

Require one candidate `MATCH` query to:

- hit all tokenizer-adjacent grouped variants and compact positives;
- reject non-adjacent text when context targets that row;
- preserve leading-zero and identifier behavior.

- [x] **Step 3: Run tests to verify RED**

Run:

```bash
uv run pytest \
  tests/retrieval/test_query_policy.py \
  tests/adapters/test_sqlite_fts.py -q
```

- [x] **Step 4: Implement minimal grouping**

Use right grouping only for eligible ASCII digit-only tokens:

```python
def _group_compact_integer(token: str) -> tuple[str, ...] | None:
    if (
        not token.isascii()
        or not token.isdigit()
        or len(token) < 5
        or token.startswith("0")
    ):
        return None
    first = len(token) % 3 or 3
    return (
        token[:first],
        *(token[index : index + 3] for index in range(first, len(token), 3)),
    )
```

Compile an eligible token as:

```text
("<original>" OR "<grouped phrase>")
```

If no eligible token exists, return `_compile_current(query)` directly. Otherwise join clauses with
explicit `AND`. Do not add a new compiled-query length exception in E2; record worst-case expansion
in tests instead so promotion cannot introduce an unhandled public Search error.

Add boundary cases for 5/6/7/9 digits, multiple eligible integers, underscore/alphanumeric forms,
Unicode digits, decimals, signs, dates, scientific notation, and the 1000-character manifest query
limit.

- [x] **Step 5: Run targeted tests**

Run:

```bash
uv run pytest \
  tests/retrieval/test_query_policy.py \
  tests/adapters/test_sqlite_fts.py \
  tests/application/test_ask.py \
  tests/application/test_pdf_publication.py \
  tests/application/test_video_publication.py \
  tests/interfaces/test_cli_pdf.py \
  tests/interfaces/test_cli_ask.py \
  tests/interfaces/test_mcp_contract.py -q
```

Expected: all candidate invariants pass and current behavior remains identical.

- [x] **Step 6: Commit the candidate**

Commit:

```text
feat(retrieval): add numeric grouping candidate
```

### Task 5: Reuse E1 Evaluation For Allowlisted Policies

**Files:**
- Modify: `src/mke/evaluation/runner.py`
- Modify: `tests/evaluation/test_runner.py`

- [x] **Step 1: Write failing policy-injection tests**

Keep the public function signature unchanged and require:

```python
current = run_retrieval_evaluation(MANIFEST)
explicit_current = _run_retrieval_evaluation(MANIFEST, query_policy="current")
candidate = _run_retrieval_evaluation(MANIFEST, query_policy="numeric-grouping-v1")

assert current.results == explicit_current.results
assert current.metrics == explicit_current.metrics
assert candidate.status == "passed"
```

Unknown policy must fail before engine construction. Public E1 CLI output and schema must remain
unchanged.

- [x] **Step 2: Run runner tests to verify RED**

Run:

```bash
uv run pytest tests/evaluation/test_runner.py -q
```

- [x] **Step 3: Add a private policy-aware evaluator**

Keep the exported function exact and delegate internally:

```diff
 def run_retrieval_evaluation(manifest_path: Path) -> RetrievalEvaluationReport:
+    return _run_retrieval_evaluation(manifest_path, query_policy="current")
+
+
+def _run_retrieval_evaluation(
+    manifest_path: Path,
+    *,
+    query_policy: RetrievalQueryPolicy,
+) -> RetrievalEvaluationReport:

-            first = _run_workspace(staged)
-            second = _run_workspace(staged)
+            first = _run_workspace(staged, query_policy=query_policy)
+            second = _run_workspace(staged, query_policy=query_policy)

-def _run_workspace(manifest: RetrievalEvaluationManifest) -> _WorkspaceResult:
+def _run_workspace(
+    manifest: RetrievalEvaluationManifest,
+    *,
+    query_policy: RetrievalQueryPolicy,
+) -> _WorkspaceResult:

-        engine = KnowledgeEngine(Path(workspace) / "mke.sqlite")
+        engine = KnowledgeEngine(
+            Path(workspace) / "mke.sqlite",
+            query_policy=query_policy,
+        )
```

Pass the policy only to evaluator-owned `KnowledgeEngine` instances. Do not export the private
entry point from `mke.evaluation`; the numeric comparator imports it from the runner module. Do not
add the policy to the public E1 CLI.

- [x] **Step 4: Run E1 equivalence tests**

Add a runner regression test that loads the canonical E1 artifact and compares results, metrics,
category counts, Ask status, and integrity fields while excluding duration and source identity.
Then run:

```bash
uv run pytest \
  tests/evaluation/test_runner.py \
  tests/evaluation/test_metrics.py \
  tests/evaluation/test_report.py \
  tests/evaluation/test_baseline.py -q
uv run mke eval retrieval \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --json > /tmp/e1-current-policy.json
```

Expected: the public wrapper and private `current` path have identical semantic results, and those
results match the canonical E1 observation. Duration may differ.

- [x] **Step 5: Commit evaluator reuse**

Commit:

```text
refactor(eval): evaluate allowlisted query policies
```

### Task 6: Add Numeric Comparison, Gates, And CLI

**Files:**
- Create: `src/mke/evaluation/numeric_comparison.py`
- Modify: `src/mke/evaluation/__init__.py`
- Modify: `src/mke/cli.py`
- Create: `tests/evaluation/test_numeric_comparison.py`
- Modify: `tests/interfaces/test_cli_evaluation.py`

- [x] **Step 1: Write failing comparison tests**

Cover:

- protocol-lock validation before engine construction;
- current/candidate execution for development, holdout, and E1;
- grouped-document improvement;
- compact-document preservation;
- non-adjacent-token rejection and adjacent punctuation equivalence;
- leading-zero, identifier, short-number, and unrelated-query equivalence;
- full-E1 per-query and aggregate gates;
- trustworthy candidate rejection versus integrity failure;
- deterministic semantic human/JSON fields with duration excluded from equality;
- protocol candidate mismatch prevention and explicit `--db` usage errors;
- exact `mke.retrieval_numeric_comparison.v1` JSON fields, human header/status lines, help text,
  exit codes, empty stderr, and redaction behavior.
- failure injection for every development/holdout/E1 policy run, protocol parsing, engine
  construction/close, gate calculation, and rendering.

- [x] **Step 2: Run comparison tests to verify RED**

Run:

```bash
uv run pytest \
  tests/evaluation/test_numeric_comparison.py \
  tests/interfaces/test_cli_evaluation.py -q
```

- [x] **Step 3: Implement the narrow comparator**

Use the private E1 runner:

```python
development_current = _run_retrieval_evaluation(development, query_policy="current")
development_candidate = _run_retrieval_evaluation(
    development, query_policy="numeric-grouping-v1"
)
holdout_current = _run_retrieval_evaluation(holdout, query_policy="current")
holdout_candidate = _run_retrieval_evaluation(
    holdout, query_policy="numeric-grouping-v1"
)
e1_current = _run_retrieval_evaluation(E1_MANIFEST, query_policy="current")
e1_candidate = _run_retrieval_evaluation(
    E1_MANIFEST, query_policy="numeric-grouping-v1"
)
```

Compare semantic fields only. For every E1 query whose compiled text is unchanged, require exact
ordered locator tuples, Ask status, and all per-query fields. The only allowlisted E1 delta is
`water-answerable-01`, which must improve from no hit to rank 1. Do not compare duration or
temporary paths.

- [x] **Step 4: Implement explicit gate records**

Each gate contains:

```json
{
  "gate_id": "holdout_grouped_rank_1",
  "status": "passed",
  "observed": "rank_1",
  "required": "rank_1",
  "next_step": "none"
}
```

Use separate:

```text
integrity_status = passed | failed
candidate_status = passed | rejected | not_recorded
```

Map every invalid input or execution exception to `failed/not_recorded`; map trustworthy gate
failure to `passed/rejected`; map all gates passing to `passed/passed`. Convert all causes to fixed
public-safe values without absolute paths or tracebacks.

- [x] **Step 5: Add CLI**

Add:

```text
mke eval retrieval-numeric --protocol PATH [--json]
```

Read candidate ID and semantic revision only from the strict protocol. Reject missing
`--protocol`, explicit `--db`, candidate override attempts, and unexpected arguments with usage
exit `2`. A supplied missing/invalid protocol is `failed/not_recorded`, exit `1`. Rendering
failures use fixed redacted output and exit `1`.

Require the schema, fields, human header, status lines, and `--help` wording from the design.
Evaluation failures produce empty stderr and contain no traceback or absolute path.

- [x] **Step 6: Run the comparison**

Run:

```bash
set +e
uv run mke eval retrieval-numeric \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --json > /tmp/numeric-grouping-v1-comparison.json
comparison_status=$?
set -e
case "$comparison_status" in
  0|1) ;;
  *) exit "$comparison_status" ;;
esac
COMPARISON_STATUS="$comparison_status" uv run python -c \
  'import json, os; p=json.load(open("/tmp/numeric-grouping-v1-comparison.json")); assert p["integrity_status"] == "passed"; assert (p["candidate_status"] == "passed") == (int(os.environ["COMPARISON_STATUS"]) == 0)'
```

Expected: `integrity_status=passed`. Continue to Task 7 for either `passed` or `rejected`; create
PR 2 only if `candidate_status=passed`.

- [x] **Step 7: Commit comparison**

Commit:

```text
feat(eval): compare numeric retrieval candidate
```

### Task 7: Persist Artifact, CI, Documentation, And Review Evidence

**Files:**
- Create: `src/mke/evaluation/numeric_artifact.py`
- Create: `tests/evaluation/test_numeric_artifact.py`
- Create: `benchmarks/retrieval/numeric-grouping-v1-comparison.json`
- Modify: `benchmarks/retrieval/retrieval-eval-v1-baseline.json`
- Modify: `.github/workflows/ci.yml`
- Create: `docs/how-to/evaluate-numeric-retrieval.md`
- Modify: `docs/how-to/run-retrieval-evaluation.md`
- Modify: `docs/reference/cli.md`
- Modify: `docs/explanation/architecture.md`
- Modify: `docs/README.md`
- Modify: `README.md`
- Modify: `README_CN.md`
- Update: E2 spec, plan, and durable review

- [x] **Step 1: Write failing artifact tests**

The validator must bind:

- protocol, development, holdout, and E1 identities;
- candidate ID and semantic revision `1`;
- complete sorted `src/mke/**/*.py` content identity, using a private helper shared with E1;
- environment;
- current/candidate compiled queries;
- current/candidate ordered per-query results and metrics;
- every gate and final status.

Mutating any bound field or source file fails validation. A self-consistent rejected candidate
artifact remains structurally valid. Add a squash-landed depth-1 fresh-clone test that validates
without requiring feature commits in `HEAD` ancestry.

- [x] **Step 2: Run artifact tests to verify RED**

Run:

```bash
uv run pytest tests/evaluation/test_numeric_artifact.py -q
```

- [x] **Step 3: Implement artifact record/validate and reach GREEN**

Implement `record` and `validate` subcommands using the exact nested schema, gate order, fixed
errors, limitations, canonical semantic payload, and shared source-content identity from the
design. Then run:

```bash
uv run pytest \
  tests/evaluation/test_numeric_artifact.py \
  tests/evaluation/test_baseline.py -q
```

Expected: mutation, source-identity, observed-comparison, rejected-candidate, and depth-1
squash-landed tests pass.

- [x] **Step 4: Review and persist the comparison**

After all PR 1 Python source changes are complete, rerun the comparison. Add a project-owned
artifact command and use it instead of manual JSON editing:

```bash
set +e
uv run mke eval retrieval-numeric \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --json > /tmp/numeric-grouping-v1-comparison.json
comparison_status=$?
set -e
case "$comparison_status" in
  0|1) ;;
  *) exit "$comparison_status" ;;
esac
COMPARISON_STATUS="$comparison_status" uv run python -c \
  'import json, os; p=json.load(open("/tmp/numeric-grouping-v1-comparison.json")); assert p["integrity_status"] == "passed"; assert (p["candidate_status"] == "passed") == (int(os.environ["COMPARISON_STATUS"]) == 0)'
uv run python -m mke.evaluation.numeric_artifact record \
  --observed /tmp/numeric-grouping-v1-comparison.json \
  --artifact benchmarks/retrieval/numeric-grouping-v1-comparison.json \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --repository .
```

The command writes the canonical semantic payload, excludes duration, and binds final source
content identity. Review the generated artifact, then refresh only E1's complete source identity;
preserve its historical metrics and per-query results.

- [x] **Step 5: Add CI**

CI reruns:

```bash
set +e
uv run mke eval retrieval-numeric \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --json > /tmp/numeric-comparison.json
comparison_status=$?
set -e
case "$comparison_status" in
  0|1) ;;
  *) exit "$comparison_status" ;;
esac
COMPARISON_STATUS="$comparison_status" uv run python -c \
  'import json, os; p=json.load(open("/tmp/numeric-comparison.json")); assert p["integrity_status"] == "passed"; assert (p["candidate_status"] == "passed") == (int(os.environ["COMPARISON_STATUS"]) == 0)'
uv run python -m mke.evaluation.numeric_artifact \
  validate \
  --artifact benchmarks/retrieval/numeric-grouping-v1-comparison.json \
  --observed /tmp/numeric-comparison.json \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --repository .
```

CI evaluates semantic gates and requires the fresh observed canonical semantic payload to match
the reviewed artifact. A trustworthy rejection is an allowed recorded outcome; integrity or
rendering failure still fails CI. Duration and explicitly non-semantic environment fields are
excluded.

- [x] **Step 6: Update public documentation**

Document:

- the E1-observed mismatch;
- exact eligible-token rules;
- public holdout limitation;
- comparison versus promotion responsibilities;
- integrity failure versus candidate rejection;
- no default behavior change in PR 1;
- rollback and conditional ADR path.

Link the guide from the existing E1 how-to, `docs/README.md`, `docs/reference/cli.md`, `README.md`,
and `README_CN.md`. Near the first comparison command, state that PR 1 does not change runtime
Search behavior.

- [x] **Step 7: Run complete PR 1 verification**

Run:

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke eval retrieval \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --json > /tmp/e1-current.json
set +e
uv run mke eval retrieval-numeric \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --json > /tmp/numeric-comparison.json
comparison_status=$?
set -e
case "$comparison_status" in
  0|1) ;;
  *) exit "$comparison_status" ;;
esac
COMPARISON_STATUS="$comparison_status" uv run python -c \
  'import json, os; p=json.load(open("/tmp/numeric-comparison.json")); assert p["integrity_status"] == "passed"; assert (p["candidate_status"] == "passed") == (int(os.environ["COMPARISON_STATUS"]) == 0)'
uv run python -m mke.evaluation.baseline \
  --artifact benchmarks/retrieval/retrieval-eval-v1-baseline.json \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --repository . \
  --main-ref main
uv run python -m mke.evaluation.numeric_artifact \
  validate \
  --artifact benchmarks/retrieval/numeric-grouping-v1-comparison.json \
  --observed /tmp/numeric-comparison.json \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --repository .
uv run mke proof run
uv run mke demo --verify
git diff --check
```

- [x] **Step 8: Run documentation audit and authoritative review**

Implementation-window override: `gstack-document-release` was run as a local offline audit.
Per the user request, final review was limited to a lightweight self-check; full `gstack-review`
was intentionally not run.

Run `gstack-document-release`, then hand the clean local branch/worktree to the planning window for
one authoritative pre-PR `gstack-review`. Return findings to the execution window through
`superpowers:receiving-code-review`; use targeted re-review after fixes.

- [x] **Step 9: Commit PR 1 completion**

Commit:

```text
docs(eval): record numeric candidate comparison
```

Stop with a clean local branch. Do not push or create a PR until review is clean and the user
authorizes publication.

---

## PR 2: Promote Only A Passing Candidate

### Task 8: Add ADR, Change The Default, And Prove Rollback

**Precondition:** `benchmarks/retrieval/numeric-grouping-v1-comparison.json` is valid and records
`candidate_status=passed`.

**Files:**
- Create: `docs/decisions/0007-numeric-grouping-query-policy.md`
- Modify: `src/mke/retrieval/query_policy.py`
- Modify: `src/mke/runtime.py`
- Modify: `src/mke/cli.py`
- Create: `scripts/numeric_retrieval_deployment_proof.py`
- Modify: query-policy, Search, Ask, CLI, and MCP tests
- Modify: Search/Ask reference and architecture documentation
- Refresh E1 and numeric comparison source identities

- [ ] **Step 1: Write failing promotion and rollback tests**

Require normal `KnowledgeEngine` composition to use `numeric-grouping-v1`.
`RuntimeConfig(retrieval_query_policy="current")` and installed CLI/MCP startup with
`--retrieval-query-policy current` must reproduce old results with no database migration or index
rebuild. Unknown values must fail as usage errors before engine construction.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
uv run pytest \
  tests/retrieval/test_query_policy.py \
  tests/adapters/test_sqlite_fts.py \
  tests/application/test_ask.py \
  tests/interfaces/test_cli_pdf.py \
  tests/interfaces/test_cli_ask.py \
  tests/interfaces/test_cli_mcp.py \
  tests/interfaces/test_mcp_contract.py \
  tests/interfaces/test_mcp_server.py -q
```

Expected: new default, rollback-selector, and invalid-policy cases fail before implementation.

- [ ] **Step 3: Add ADR-0007**

Record:

- E1 evidence and protocol identities;
- paired development/holdout controls;
- exact eligible-token and OR-phrase behavior;
- candidate gates and reviewed artifact;
- rejected alternatives;
- limitations;
- default and rollback identifiers.

- [ ] **Step 4: Change the default and add the rollback selector**

Set:

```python
DEFAULT_RETRIEVAL_QUERY_POLICY: RetrievalQueryPolicy = "numeric-grouping-v1"
```

Retain `current` for rollback.

Add:

```python
@dataclass(frozen=True)
class RuntimeConfig:
    db_path: Path
    retrieval_query_policy: RetrievalQueryPolicy = DEFAULT_RETRIEVAL_QUERY_POLICY
    ...
```

Pass it through `build_engine`. Add the global owner-controlled option:

```text
--retrieval-query-policy {current,numeric-grouping-v1}
```

Parse the option into `RuntimeConfig` for normal CLI Search/Ask and owner-started MCP composition.
Reject an explicit retrieval-policy option with `mke eval ...`, whose candidate remains
protocol-locked.

- [ ] **Step 5: Update contracts and artifacts**

Document compact/grouped numeric equivalence. Refresh source identities without replacing
historical observations.

- [ ] **Step 6: Run final verification**

Run the complete PR 1 verification set, then:

```bash
uv run pytest \
  tests/retrieval/test_query_policy.py \
  tests/adapters/test_sqlite_fts.py \
  tests/application/test_ask.py \
  tests/interfaces/test_cli_pdf.py \
  tests/interfaces/test_cli_ask.py \
  tests/interfaces/test_cli_mcp.py \
  tests/interfaces/test_mcp_contract.py \
  tests/interfaces/test_mcp_server.py -q
```

Add an offline installed-wheel proof, following the existing isolated deployment-proof pattern,
then run:

```bash
uv build
uv run python scripts/numeric_retrieval_deployment_proof.py \
  --wheel dist/multimodal_knowledge_engine-0.0.0-py3-none-any.whl \
  --python 3.12
uv run python scripts/numeric_retrieval_deployment_proof.py \
  --wheel dist/multimodal_knowledge_engine-0.0.0-py3-none-any.whl \
  --python 3.13
```

The proof installs into an external temporary venv, clears source-tree import variables, and runs
CLI plus stdio MCP Search checks for:

- grouped-document/compact-query success;
- compact-document preservation;
- non-adjacent-token rejection and documented adjacent punctuation equivalence;
- explicit `current` rollback behavior.

- [ ] **Step 7: Run final review and stop before publication**

Run documentation audit and authoritative `gstack-review`, remediate findings, and stop before
push/PR until authorized.

---

## Plan Completion Record

- [x] PR 1 comparison merged through
  [#25](https://github.com/iTao-AI/multimodal-knowledge-engine/pull/25) at
  `1c27afc12eb3a3dd0d1555d52941352177cc434d`.
- [x] Candidate result recorded as passed and validated after squash landing.
- [x] PR 2 promotion explicitly not created; promotion remains outside this implementation.
- [x] Durable review finalized with merge evidence. Dependency PR
  [#22](https://github.com/iTao-AI/multimodal-knowledge-engine/pull/22) refreshed the
  protocol/artifact dependency identities without changing candidate results.

## Authoritative Review Remediation

- [x] All six evaluations, compiled queries, and gates use one protocol-bound immutable snapshot.
- [x] Numeric observed/artifact payloads have independent exact nested schema and consistency
  validation.
- [x] `single_match_per_search` and `scope_fence` are produced from runtime and protocol evidence.
- [x] `retrieval_numeric_nondeterministic` retains its fixed public mapping.
- [x] Completion and durable review records distinguish local completion from merge completion.

## Targeted Re-review Remediation

- [x] Recompute every derivable promotion gate from validated observations, compiled queries, and
  metrics instead of trusting recorded gate status.
- [x] Reject bool-as-int values and enforce explicit ranges for nested counts, ranks, locators,
  revisions, and metric fields.
- [x] Validate every retrieved locator document ID against its frozen manifest inventory.
- [x] Reject boolean protocol candidate revisions before any fixture or evaluation work.
- [x] Replace the stale implementation-window Verdict in the durable review.
- [x] Complete the full requested verification set and record fresh artifact identities for the
  final targeted remediation.
- [x] Targeted re-review cleared.

## Decision Audit Trail

| Decision | Outcome | Basis |
|---|---|---|
| Next E2 validation | `numeric-grouping-v1` only | E1 has one concrete compact-query/grouped-document miss and no evidence for broader retrieval changes. |
| Claim boundary | tokenizer-adjacent right-grouped tokens | FTS5 phrase semantics cannot distinguish comma from equivalent punctuation. |
| Holdout | independent, locked, public | Protects protocol order without claiming statistical blindness. |
| Delivery | comparison PR, then conditional promotion PR | Separates evidence collection from runtime-default change. |
| Candidate selection | protocol-locked, no CLI override | Avoids a generic candidate framework and redundant configuration. |
| Rejected result | valid E2 completion | A trustworthy rejection is evidence; it blocks PR 2 but not artifact validation. |
| Artifact identity | final sorted source-content identity | Survives squash landing and depth-1 validation. |
| Rollback | owner-controlled `current` runtime policy | Makes rollback operable through installed CLI and stdio MCP. |

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope and strategy | 1 | CLEAR | Held scope to one observed numeric failure and removed broad benchmark expansion. |
| Codex Review | `codex exec` | Independent plan voices | 4 | CLEAR | 32 CEO, engineering, DX, and targeted findings were incorporated. |
| Eng Review | `/plan-eng-review` | Architecture and tests | 1 | CLEAR | 14 issues resolved across FTS5 semantics, API boundaries, failures, artifacts, and gates. |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | SKIPPED | No graphical interface or visual surface. |
| DX Review | `/plan-devex-review` | Developer experience | 1 | CLEAR | CLI/report contracts, rejection CI, artifact workflow, rollback, commands, and docs were made executable. |

**CODEX:** Independent Codex voices completed CEO, engineering, DX, and targeted re-review; no
parallel reviewer was used.

**VERDICT:** CEO + ENG + DX CLEARED — ready for a separate implementation window.

NO UNRESOLVED DECISIONS
