# Compiled Library Viewer

## Outcome

Turn an actual Compiled Library Export v2 into a portable, self-contained HTML viewer. A reader can choose a Source, read exact Evidence text, inspect its page or timestamp locator, and copy a traceable reference. Generation and browsing work offline, without a model, server, database write, or new dependency.

This is a downstream read-only artifact viewer. It is not the planned HTTP/workspace application and does not alter Library, Run, Publication, Search, Ask, CLI export, or MCP authority.

## Input and generation contract

Add a repository script with the following public entry point:

```sh
python scripts/build_compiled_library_viewer.py --export compiled-library-v2 --output library-viewer.html
```

Input is an existing `mke.compiled_library_export.v2` directory. The output is a new local HTML file outside the export directory; reject an existing destination or a destination inside the input tree. Do not change the input, database or original Sources. Finish the complete validated artifact before publishing the output, with exclusive creation and task-owned cleanup on failure. Provide readable errors without leaking a traceback or local absolute paths.

Use the existing v2 consumer's validation logic. Its `validate()` and CLI outputs must remain compatible. A small helper returning the validated manifest and exact Evidence rows from the same in-memory bytes is acceptable; do not validate a path and then silently reread unchecked replacement content. Do not copy the validator into a second independent implementation. Do not broaden v1 proof semantics; v1/unsupported input should explain that a v2 export is required.

Keep a separate documented viewer budget of 64 Sources, 2,000 Evidence records and 8 MiB aggregate Evidence UTF-8 text. These are presentation limits, not changes to producer export limits or performance claims. Exceeding the budget must fail clearly before rendering; do not silently omit data or label partial data as complete. Bound manifest/file reads using the existing safe-reading rules, and reject malformed input, unsafe paths, symlinks and mismatched hashes under the current contract. Preserve source and Evidence ordering.

## User flow and visual design

Use a restrained editorial layout: warm light background, dark readable text, one deep teal accent, clear spacing and borders. No external fonts, icon libraries, network assets, decorative charts or animated counters. Reuse small compatible style conventions from `docs/evidence-workspace` without recreating its fabricated state data. UI default is natural simplified Chinese; keep public identifiers and schema literals intact.

At desktop width, show a narrow Source list to the left and a large reading pane to the right. At mobile width, stack them without horizontal overflow. Heading: “资料与引用”; subtitle: “浏览本次导出的资料，沿页码或时间戳核对证据。” Show exact Source/Evidence totals and “导出快照” status. Do not display live/connected/production badges or imply the snapshot is still the current database state.

1. Open the generated HTML directly. First Source is selected; no dummy loading screen.
2. Source list shows display name, human-readable media type and exact Evidence count. Clicking one changes the reading pane and selection state.
3. Reading pane shows the source title, publication revision and Evidence records in stable order. A record leads with “第 N 页” or a readable timestamp range, followed by unmodified extracted text with preserved whitespace. This is extracted text, not a reconstructed PDF layout or media player.
4. Add a plain text filter for names and Evidence within the loaded snapshot. Label it “筛选导出内容”; show visible/total counts and a useful no-match state. It is not MKE semantic Search and must not show a retrieval-quality score. Clearing it restores the full view. Search highlights, if implemented, must preserve exact copyable text and remain escaped.
5. Each Evidence has “复制引用” and a stable local anchor. The copied text includes the exact Evidence text plus display name, locator, content fingerprint, source_id, publication_id/revision, run_id and evidence_id; identity fields are never inferred from display names. Provide a collapsible “引用详情” for these identifiers so the default reading experience stays clear.
6. Copy success appears only after successful clipboard completion. For browser permission/file-origin restrictions, show a selectable reference with “选择并复制” guidance; do not falsely report success. Accessible labels, keyboard focus and selected state are required.

Use escaped text nodes for all source names and content. Never interpret Evidence Markdown/HTML as executable markup, instructions, script or a navigable URL. Safely embed any serialized data against `</script>` breakouts; no `eval`, dynamic script injection or external fetch. Keep script/template data separate. Hashes prove export integrity, not source truth or answer quality.

## Demonstration data and authority

Provide a reproducible provider-free walkthrough using the existing real ingestion/export path and repository PDF/video fixtures in a task-owned temporary Library. Export as v2, build the viewer, and open the output. Evidence text and displayed identifiers must come from that actual exported manifest/JSONL, not a hand-authored UI dataset. The fixture material remains synthetic/test material, explicitly labeled in the walkthrough; actual pipeline execution does not imply real users or enterprise adoption.

Keep the existing synthetic Evidence workspace and historical proof artifacts unchanged. The viewer is usable on other valid v2 exports within its stated budget. No fake Run history, failure status or “insufficient evidence” state may be invented from an export that does not contain it. Original Source files are not required to view the exported text.

## Implementation sequence

1. Read current AGENTS, the v2 consumer, export contracts and their tests. Confirm clean isolated worktree based on `d3d801bb776480516f3062673a43a592ea99b581` or a freshly verified compatible main. Persist this specification in the project's existing spec/plan location; keep private orchestration text out.
2. Add focused failing tests for actual export-to-viewer data binding, exact Unicode/locator/citation preservation, invalid/mutated input, existing output, output inside input, safe untrusted text, unsupported v1 and budget boundaries. Test relevant behaviors, not a long list of incidental HTML strings.
3. Implement the smallest validated snapshot helper, script and self-contained template assets. Preserve the current v2 validation/CLI result and all public export schemas. Do not modify domain storage, retrievers, model providers, installed package surface or dependency lockfiles.
4. Produce an example with the actual provider-free ingestion and v2 export. Verify both exact content/identity and reader interactions. Keep any generated local example outside authoritative historical proof directories.
5. Add a short how-to and link it from the existing export guide plus English/Chinese README. Lead with the concrete reading workflow. Identify the actual data route and offline snapshot scope concisely; leave unrelated release wording and older unmerged documentation work untouched.
6. Run focused new tests plus existing v2 consumer and affected export contract tests, appropriate static checks, and browser checks. If shared helper changes widen the impact, run the relevant broader suites before final handoff. Use existing runtime/cache and prove imports come from this worktree. No dependency installation or remote provider calls.

## Acceptance and stopping point

- Actual export v2 -> validated snapshot -> HTML -> exact Evidence/citation can be followed end to end.
- Source switching, text filtering/no-match/reset, local evidence anchors, details and copy/fallback are verified in a browser; desktop 1440 and mobile 390 render without horizontal overflow. A malicious-looking Evidence string renders as text and does not execute or initiate a network request.
- Invalid or altered inputs do not produce a success artifact; output collision and read-only input guarantees hold. Copy results never claim success on rejection. Existing v2 consumer behavior stays compatible.
- Documentation matches commands that actually ran. Local HTML, fixture provenance, checks, exact HEAD and remaining limitations are reported. No new quality, production or adoption claims.
- Complete a single coherent local implementation, commit intentional files and return clean local READY for independent visual/content review. Do not push, open PR, merge, release, install dependencies, run paid providers, or expand into a second feature.
