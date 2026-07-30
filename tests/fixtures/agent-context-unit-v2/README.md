# Diagnostic-first context mechanism v2 fixtures

These fixtures freeze the public scientific inputs for the provider-free context comparison.
The development partition contains seven Source files and eleven label-blind observer cases. The
holdout partition contains two public, nonblind Source files and two metadata-only observer cases;
its labels are empty and no development loader opens holdout payloads.

`scientific-input-lock.json` is the immutable normalized scientific projection authority. Source
receipts record exact byte counts, SHA-256 content fingerprints, page counts, text-layer counts,
PyMuPDF version, and—where applicable—official download and rights-basis URLs. The v2 protocol
changes evaluator schemas and source inventories only; the scientific values and Source bytes are
identical to the independently reviewed import authority.

PDF files are treated as binary. Their exact byte counts and SHA-256 values are recorded in the
corresponding source receipts.
