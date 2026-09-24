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

For a complete producer workflow, first follow [Export A Compiled Library](./export-compiled-library.md)
with `--format-version v2`, then run the command above. Repository PDF/video fixtures are synthetic
test material; a local walkthrough using them demonstrates the data route only and does not imply
enterprise or real-user use.
