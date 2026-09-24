# Compiled Library Viewer bounded repair review

Date: 2026-09-23
Base commit: `ad44b990bc4fa6333aed4f716578722b506cca14`
Scope: repair the two bounded findings from the independent Viewer review. Export contracts, data budgets, visual design, and producer behavior remain unchanged.

## Decision

The two review findings and their fragment-consistency follow-up are repaired locally with executable regression coverage. This is a local review gate; publication, pull-request creation, and additional product work remain outside scope.

## Findings and resolution

### Evidence fragments resolve to their owning Source

The self-contained Viewer now resolves a known `#evidence-<id>` fragment against the validated payload on initial load and on `hashchange`. It selects the owning Source, renders the Evidence card, and scrolls the stable card id into view. If a valid target is hidden by the current filter, the fragment navigation clears that filter so the target is visible. If ordinary rendering later hides a known current target—for example, after switching Source or filtering—`history.replaceState` clears only the fragment without adding a history entry. Visible known targets remain addressable; unknown or malformed fragments leave the current selection and URL unchanged and do not raise an error.

### Source selection preserves focus and uses native-button semantics

Source controls now expose their identity through `data-source-id`, use `aria-pressed` for the selected native button, and no longer use `aria-selected` without a selection-widget role. After Source activation rebuilds the list, focus is restored to the newly rendered selected button. Filtering and clear-filter keep their existing input-focus behavior.

## Verification

Commands run from the repository worktree. Public command paths are normalized: `python`, `ruff`, and `pyright` refer to the existing matching project tools, and the Pyright `--pythonpath` points to that same interpreter.

```text
python -m pytest -q tests/scripts/test_compiled_library_viewer.py tests/scripts/test_compiled_library_export_consumer_v2.py tests/interfaces/test_cli_library_export.py tests/application/test_library_export.py tests/adapters/test_library_export_filesystem.py tests/evaluation/test_compiled_library_export_documentation.py
146 passed, 5 warnings

ruff check scripts/build_compiled_library_viewer.py tests/scripts/test_compiled_library_viewer.py
All checks passed!

pyright --pythonpath python
0 errors, 0 warnings, 0 informations

git diff --check
passed
```

The new regression executes the generated HTML's actual inline Viewer script in a Node DOM harness without adding a project dependency. It covers default first-Source behavior, a non-first Source initial fragment, fragment changes, a filtered-out target, an unknown fragment, Source focus restoration, selected-button semantics, filter focus, and clear-filter focus.

## Remaining limits

No live browser verification was added in this repair. The existing desktop/mobile screenshots and prior local evidence remain unchanged; the independent review had already recorded that its browser rejected local-file navigation under its URL policy, and this repair did not introduce a URL workaround or alternate browser path. The unrelated full-project test identity/environment mismatch from the prior review was not repeated or changed in this bounded repair.

The four task-owned `.gstack` runtime files were inspected by name and retained because their terminal-agent process was still active; credential contents were not read. An ignored disposable environment created by the initial baseline command was moved outside the worktree and is not part of the diff; its machine-specific path is intentionally omitted here. No remote operation, publication, or PR operation was performed as part of this repair.
