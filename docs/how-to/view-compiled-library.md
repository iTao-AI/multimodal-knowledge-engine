# View A Compiled Library Export Offline

Use the Viewer only with a complete `mke.compiled_library_export.v2` directory. It validates the
manifest, sidecar hashes, inventory, provenance, and exact Evidence JSONL before creating one
self-contained HTML file:

```bash
python scripts/build_compiled_library_viewer.py \
  --export compiled-library-v2 \
  --output library-viewer.html
```

The output must be new and outside the export directory. The command never changes the export,
database, or original Source files. Open `library-viewer.html` directly in a browser; it has no
server, model, network asset, or external font dependency.

The page starts with the first Source selected. Choose another Source, use `筛选导出内容` to filter
names or exact Evidence text, clear the filter to restore the snapshot, and follow the page or
timestamp locator. Each record keeps its extracted whitespace, has a stable local anchor, and
contains a collapsible `引用详情` section. `复制引用` includes the exact Evidence text and the
display name, locator, content fingerprint, `source_id`, `publication_id`/revision, `run_id`, and
`evidence_id`. If the browser blocks clipboard access for a file-origin page, the Viewer shows a
selectable reference and `选择并复制` guidance instead of claiming success.

The Viewer has a separate presentation budget of 64 Sources, 2,000 Evidence records, and 8 MiB of
aggregate Evidence UTF-8 text. These limits do not change producer export limits or make quality,
latency, production, or adoption claims. Invalid, altered, v1, over-budget, colliding, and
in-tree output cases fail before a success HTML artifact is published.

## Source-Checkout Walkthrough

From the repository root, prepare the locked development environment with `uv sync --locked` if it
is not already ready. This walkthrough uses the repository's text-layer PDF and the short video
fixture with its transcript sidecar; it makes no provider calls or model downloads:

```bash
set -eu
MKE_REPO_ROOT="$PWD"
TASK_DIR="$(mktemp -d)"
MKE_DB="$TASK_DIR/library.sqlite3"

uv run --project "$MKE_REPO_ROOT" mke --db "$MKE_DB" ingest tests/fixtures/pdf/text-layer.pdf
uv run --project "$MKE_REPO_ROOT" mke --db "$MKE_DB" ingest tests/fixtures/video/short-audio.mp4

(
  cd "$TASK_DIR"
  uv run --project "$MKE_REPO_ROOT" mke --db "$MKE_DB" library export \
    --output compiled-library-v2 --format-version v2 --json
  uv run --project "$MKE_REPO_ROOT" python \
    "$MKE_REPO_ROOT/scripts/compiled_library_export_consumer_v2.py" \
    --export compiled-library-v2 --json
  uv run --project "$MKE_REPO_ROOT" python \
    "$MKE_REPO_ROOT/scripts/build_compiled_library_viewer.py" \
    --export compiled-library-v2 --output library-viewer.html
)

open "$TASK_DIR/library-viewer.html"
```

The export and viewer are new children of `TASK_DIR`; neither command overwrites an existing
destination. Keep the directory while viewing the page. The consumer validates the complete v2
snapshot before the viewer is built, and the viewer validates it again. The generated page reads
only the validated display names, provenance, and exact Evidence text. It does not reopen, execute,
or modify the original PDF or video, the database, or the export. The output is a snapshot, not a
live database view.

The repository fixtures are synthetic/test material. Their actual ingest and export demonstrate the
data route only and do not imply enterprise use or real-user adoption. The Viewer renders extracted
Evidence text as plain text; it does not execute HTML or scripts or follow URLs. Treat that text as
untrusted content. If a browser blocks clipboard access for a local file, use the selectable
citation and `选择并复制` guidance.
