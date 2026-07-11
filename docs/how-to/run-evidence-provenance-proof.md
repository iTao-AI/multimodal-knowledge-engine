# Run The Evidence Provenance Proof

Run the model-free, strictly local real-stdio consumer proof:

```bash
UV_OFFLINE=1 uv run python scripts/evidence_provenance_proof.py
```

The proof uses the official MCP Python SDK and temporary SQLite stores. It checks the unchanged
legacy tool schemas, all three strict v1 tools, `empty` / `no_active_publication` / `active`
observations, page and timestamp locators, identical Search/Ask `mke.evidence_ref.v1` projections,
same-store reingest identity, and fresh-store source-byte fingerprint identity.

The report contains schema names, state names, counts, and booleans only. It does not render local
paths, credentials, environment values, stderr, tracebacks, transient IDs, internal metadata, or
Evidence text. Child processes and temporary stores are closed by bounded context managers on
success, transport failure, cancellation, or timeout.

