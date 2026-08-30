#!/usr/bin/env python3
# ruff: noqa: E501
"""Generate and verify the static, provider-free Evidence workspace projection."""

from __future__ import annotations

import argparse
import functools
import hashlib
import html
import http.server
import json
import os
import re
import shutil
import subprocess
import threading
from collections.abc import Generator, Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
SHOWCASE_RELATIVE = Path("docs/evidence-workspace")
STYLE_NAME = "showcase.css"
INDEX_NAME = "index.html"
FRAME_NAMES = (
    "evidence-workspace-overview",
    "evidence-publication-search",
    "evidence-insufficient-recovery",
)
FRAME_FILES = tuple(f"{name}.html" for name in FRAME_NAMES)
PNG_NAMES = tuple(f"{name}.png" for name in FRAME_NAMES)
ASSET_SPECS = (
    (PNG_NAMES[0], FRAME_FILES[0], "overview"),
    (PNG_NAMES[1], FRAME_FILES[1], "publication_search"),
    (PNG_NAMES[2], FRAME_FILES[2], "failed_or_insufficient_recovery"),
)
STATIC_FILES = (INDEX_NAME, STYLE_NAME, *FRAME_FILES)
VIEWPORT = {"width": 1600, "height": 1000}
LOCALE = "en-US"
MANIFEST_SCHEMA = "mke.evidence_showcase_manifest.v1"
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")

FIXTURE_STATE = {
    "compiled_export": "mke.compiled_library_export.v2",
    "local_knowledge": "local-knowledge-v1",
    "product_proof": "mke proof run",
    "video_fixture": "short-audio.mp4.mke-transcript.json",
}
SYNTHETIC_DISCLOSURE = (
    "Synthetic/demo documentation projection only; identifiers are illustrative and are not "
    "runtime records or production data."
)
SOURCE_TREE_FILES = (
    "scripts/generate_evidence_workspace.py",
    "scripts/generate_local_knowledge_fixtures.py",
    "tests/fixtures/local-knowledge-v1/manifest.json",
    "tests/fixtures/consumer-source-pack-v1/manifest.json",
    "tests/fixtures/video/short-audio.mp4",
    "tests/fixtures/video/short-audio.mp4.mke-transcript.json",
    f"{SHOWCASE_RELATIVE}/{STYLE_NAME}",
    *(f"{SHOWCASE_RELATIVE}/{name}" for name in FRAME_FILES),
    f"{SHOWCASE_RELATIVE}/{INDEX_NAME}",
)


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    source_id: str
    publication_id: str
    run_id: str
    source_name: str
    content_fingerprint: str
    publication_revision: int
    locator_kind: str
    locator_start: int
    locator_end: int
    text: str


@dataclass(frozen=True)
class FrameSpec:
    slug: str
    title: str
    kicker: str
    description: str
    source_label: str
    source_meta: str
    kind: str


FRAME_SPECS = (
    FrameSpec(
        slug=FRAME_NAMES[0],
        title="The Evidence workspace",
        kicker="Overview / active Publication",
        description=(
            "Raw material becomes consumable only after a Run validates Evidence into an "
            "active Publication."
        ),
        source_label="local Library · three Sources",
        source_meta="operations-guide.pdf · incident-guide.pdf · short-audio.mp4",
        kind="overview",
    ),
    FrameSpec(
        slug=FRAME_NAMES[1],
        title="Search returns a traceable result",
        kicker="Search / Ask Evidence",
        description=(
            "Search and Ask return Evidence with a Source fingerprint, Publication revision, "
            "Run, and page or timestamp locator."
        ),
        source_label="short-audio.mp4 · active Publication",
        source_meta="content_fingerprint=sha256:fixture-bound",
        kind="search",
    ),
    FrameSpec(
        slug=FRAME_NAMES[2],
        title="Incomplete work stops safely",
        kicker="Recovery / failed Run",
        description=(
            "A failed or partial Run does not switch the active Publication, and insufficient "
            "Evidence stays an explicit closed result."
        ),
        source_label="previous active Publication · revision 1",
        source_meta="candidate Run failed before activation",
        kind="failure",
    ),
)


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _id(prefix: str, number: int) -> str:
    return f"{prefix}_{number:032x}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fixture_fingerprints(root: Path) -> dict[str, str]:
    manifest_path = root / "tests/fixtures/local-knowledge-v1/manifest.json"
    raw_value = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw_value, dict):
        raise ValueError("local knowledge fixture manifest is invalid")
    raw = cast(dict[str, object], raw_value)
    if raw.get("format") != "mke.local_knowledge_fixture.v1":
        raise ValueError("local knowledge fixture manifest is invalid")
    files_value = raw.get("files")
    if not isinstance(files_value, list):
        raise ValueError("local knowledge fixture files are invalid")
    files = cast(list[object], files_value)
    result: dict[str, str] = {}
    for item_value in files:
        if not isinstance(item_value, dict):
            raise ValueError("local knowledge fixture entry is invalid")
        item = cast(dict[str, object], item_value)
        name = item.get("name")
        digest = item.get("sha256")
        if not isinstance(name, str) or not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise ValueError("local knowledge fixture identity is invalid")
        result[name] = f"sha256:{digest}"
    if set(result) != {"operations-guide.pdf", "incident-guide.pdf"}:
        raise ValueError("local knowledge fixture set is invalid")
    return result


def _evidence_items(root: Path) -> tuple[EvidenceItem, ...]:
    fingerprints = _fixture_fingerprints(root)
    video = root / "tests/fixtures/video/short-audio.mp4"
    video_fingerprint = f"sha256:{_sha256(video)}"
    return (
        EvidenceItem(
            evidence_id=_id("ev", 1),
            source_id=_id("src", 1),
            publication_id=_id("pub", 1),
            run_id=_id("run", 1),
            source_name="operations-guide.pdf",
            content_fingerprint=fingerprints["operations-guide.pdf"],
            publication_revision=1,
            locator_kind="page",
            locator_start=1,
            locator_end=1,
            text=(
                "Cedar Relay maintenance window begins Tuesday at 14:00 UTC. Operators "
                "complete checklist KITE-17 before restart."
            ),
        ),
        EvidenceItem(
            evidence_id=_id("ev", 2),
            source_id=_id("src", 2),
            publication_id=_id("pub", 2),
            run_id=_id("run", 2),
            source_name="incident-guide.pdf",
            content_fingerprint=fingerprints["incident-guide.pdf"],
            publication_revision=1,
            locator_kind="page",
            locator_start=1,
            locator_end=1,
            text=(
                "When Cedar Relay telemetry turns amber, pause intake and review the Evidence "
                "log before restarting the relay."
            ),
        ),
        EvidenceItem(
            evidence_id=_id("ev", 3),
            source_id=_id("src", 3),
            publication_id=_id("pub", 3),
            run_id=_id("run", 3),
            source_name="short-audio.mp4",
            content_fingerprint=video_fingerprint,
            publication_revision=1,
            locator_kind="timestamp_ms",
            locator_start=0,
            locator_end=1200,
            text="Video evidence introduces timestamp search.",
        ),
        EvidenceItem(
            evidence_id=_id("ev", 4),
            source_id=_id("src", 3),
            publication_id=_id("pub", 3),
            run_id=_id("run", 3),
            source_name="short-audio.mp4",
            content_fingerprint=video_fingerprint,
            publication_revision=1,
            locator_kind="timestamp_ms",
            locator_start=1200,
            locator_end=2200,
            text="Active publication search finds spoken timestamp proof.",
        ),
    )


def _field(label: str, value: str, *, wide: bool = False) -> str:
    class_name = "field field-wide" if wide else "field"
    return (
        f'<div class="{class_name}"><span class="field-label">{_esc(label)}</span>'
        f'<code>{_esc(value)}</code></div>'
    )


def _locator(item: EvidenceItem) -> str:
    if item.locator_kind == "page":
        return f"Page {item.locator_start}"
    return f"Timestamp {item.locator_start:,}–{item.locator_end:,} ms"


def _evidence_card(item: EvidenceItem, *, emphasis: bool = False) -> str:
    card_class = "evidence-card evidence-card-emphasis" if emphasis else "evidence-card"
    return f"""
<article class="{card_class}">
  <div class="card-topline">
    <span class="eyebrow">Evidence</span>
    <span class="locator-kind">locator.kind={_esc(item.locator_kind)}</span>
  </div>
  <div class="evidence-heading">
    <div>
      <h3>{_esc(_locator(item))}</h3>
      <p class="source-name">{_esc(item.source_name)}</p>
    </div>
    <span class="verified-mark" aria-label="active Publication Evidence">✓</span>
  </div>
  <p class="evidence-quote">{_esc(item.text)}</p>
  <div class="field-grid">
    {_field("evidence_id", item.evidence_id)}
    {_field("source_id", item.source_id)}
    {_field("publication_id", item.publication_id)}
    {_field("run_id", item.run_id)}
    {_field("publication_revision", str(item.publication_revision))}
    {_field("content_fingerprint", item.content_fingerprint, wide=True)}
  </div>
</article>
"""


def _lifecycle_step(label: str, value: str, number: str, *, active: bool = False) -> str:
    class_name = "lifecycle-step lifecycle-step-active" if active else "lifecycle-step"
    return f"""
<div class="{class_name}">
  <span class="step-number">{_esc(number)}</span>
  <div><span class="step-label">{_esc(label)}</span><code>{_esc(value)}</code></div>
</div>
"""


def _lifecycle(kind: str) -> str:
    run_state = "failed" if kind == "failure" else "published"
    publication = "active Publication" if kind != "failure" else "active Publication unchanged"
    return f"""
<section class="lifecycle-rail" aria-label="Source to consumer Evidence lifecycle">
  {_lifecycle_step("Source", "immutable input", "01", active=kind != "failure")}
  <span class="rail-arrow" aria-hidden="true">→</span>
  {_lifecycle_step("Run", f"run_state={run_state}", "02", active=kind != "failure")}
  <span class="rail-arrow" aria-hidden="true">→</span>
  {_lifecycle_step("Publication", publication, "03", active=kind != "failure")}
  <span class="rail-arrow" aria-hidden="true">→</span>
  {_lifecycle_step("Evidence", "page | timestamp_ms", "04", active=kind != "failure")}
  <span class="rail-arrow" aria-hidden="true">→</span>
  {_lifecycle_step("Consumer", "CLI · stdio MCP · Export", "05", active=kind != "failure")}
</section>
"""


def _source_strip(frame: FrameSpec) -> str:
    if frame.kind == "failure":
        status = "active_publication_impact=unchanged"
        status_label = "Prior active Publication"
        status_note = "candidate Run did not switch it"
    else:
        status = "state=active · revision=1"
        status_label = "Active Publication"
        status_note = "3 active Publications · 4 active Evidence"
    return f"""
<section class="source-strip">
  <div class="source-strip-main">
    <span class="eyebrow">Source / Publication</span>
    <strong>{_esc(frame.source_label)}</strong>
    <span class="muted">{_esc(frame.source_meta)}</span>
  </div>
  <div class="publication-pill">
    <span class="status-dot" aria-hidden="true"></span>
    <div><span class="eyebrow">{_esc(status_label)}</span><strong>{_esc(status)}</strong></div>
    <span class="muted">{_esc(status_note)}</span>
  </div>
</section>
"""


def _observation_card(kind: str) -> str:
    if kind == "failure":
        return """
<section class="side-card completeness-card">
  <div class="side-card-heading"><span class="eyebrow">Completeness / refusal</span><span class="mini-icon">!</span></div>
  <div class="refusal-metric"><strong>0</strong><span>candidate Evidence exposed</span></div>
  <code>schema_version=mke.active_publication_observation.v1</code>
  <code>answer_status=insufficient_evidence</code>
  <p class="side-note">The empty Evidence list is a valid closed result, not a guessed answer.</p>
</section>
"""
    returned = 1 if kind == "search" else 4
    return f"""
<section class="side-card completeness-card">
  <div class="side-card-heading"><span class="eyebrow">Completeness</span><span class="mini-icon">✓</span></div>
  <div class="refusal-metric"><strong>complete</strong><span>selection.status</span></div>
  <code>schema_version=mke.active_publication_observation.v1</code>
  <code>returned={returned} · active_evidence_count=4</code>
  <div class="completion-bar"><span></span></div>
  <p class="side-note">The consumer can see which active Evidence set the result came from.</p>
</section>
"""


def _consumer_card(kind: str) -> str:
    if kind == "failure":
        entries = (
            ("CLI", "error contract · unchanged", "#cli"),
            ("stdio MCP", "same failure fields", "#mcp"),
            ("Compiled Library Export", "no Publication switch", "#export"),
        )
    else:
        entries = (
            ("CLI", "Search / Ask", "#cli"),
            ("stdio MCP", "search_library_v1 · ask_library_v1", "#mcp"),
            ("Compiled Library Export", "mke.evidence_ref.v1 JSONL", "#export"),
        )
    rows = "".join(
        f'<a id="{_esc(anchor.removeprefix("#"))}" class="consumer-entry" href="{_esc(anchor)}">'
        f'<span class="consumer-name">{_esc(name)}</span><code>{_esc(value)}</code>'
        '<span class="entry-arrow" aria-hidden="true">↗</span></a>'
        for name, value, anchor in entries
    )
    return f"""
<section class="side-card consumer-card">
  <div class="side-card-heading"><span class="eyebrow">Consumers</span><span class="mini-icon">→</span></div>
  <p class="side-note">One active Publication, three bounded read paths.</p>
  <div class="consumer-list">{rows}</div>
</section>
"""


def _provenance_card(items: Iterable[EvidenceItem], *, kind: str) -> str:
    item = next(iter(items))
    if kind == "failure":
        body = """
  <div class="provenance-empty">
    <span class="empty-line"></span><span class="empty-line short"></span>
    <strong>No candidate Evidence enters the active set.</strong>
  </div>
  <code>active_publication_impact=unchanged</code>
"""
    else:
        body = f"""
  {_field("schema_version", "mke.evidence_ref.v1", wide=True)}
  {_field("content_fingerprint", item.content_fingerprint, wide=True)}
  {_field("publication_revision", str(item.publication_revision))}
  {_field("locator", f"{item.locator_kind}:{item.locator_start}-{item.locator_end}")}
"""
    return f"""
<section class="side-card provenance-card">
  <div class="side-card-heading"><span class="eyebrow">Provenance</span><span class="mini-icon">⌁</span></div>
  <p class="side-note">Source bytes, Run, active Publication, and locator stay connected.</p>
  {body}
</section>
"""


def _normal_surface(kind: str, items: tuple[EvidenceItem, ...]) -> str:
    if kind == "overview":
        cards = _evidence_card(items[0], emphasis=True) + _evidence_card(items[1])
        query = "Cedar Relay · active Publication"
        summary = "Search / Ask Evidence"
    else:
        cards = _evidence_card(items[3], emphasis=True)
        query = "timestamp proof"
        summary = "Search / Ask Evidence · one complete result"
    return f"""
<section class="surface-card evidence-surface" aria-labelledby="evidence-surface-heading">
  <div class="surface-heading">
    <div><span class="eyebrow">Evidence work surface</span><h2 id="evidence-surface-heading">{_esc(summary)}</h2></div>
    <span class="surface-state">active Publication only</span>
  </div>
  <div class="query-bar" aria-label="Search query">
    <span class="query-icon" aria-hidden="true">⌕</span><span class="muted">query</span>
    <code>{_esc(query)}</code><span class="query-status">Evidence-backed</span>
  </div>
  <div class="result-count"><span>Results from the active set</span><strong>{"2" if kind == "overview" else "1"}</strong></div>
  <div class="evidence-list">{cards}</div>
</section>
"""


def _failure_surface() -> str:
    return """
<section class="surface-card failure-surface" aria-labelledby="failure-surface-heading">
  <div class="surface-heading">
    <div><span class="eyebrow">Recovery boundary</span><h2 id="failure-surface-heading">Nothing incomplete becomes searchable</h2></div>
    <span class="surface-state surface-state-danger">fail closed</span>
  </div>
  <div class="failure-grid">
    <article class="failure-card">
      <div class="card-topline"><span class="eyebrow">Run</span><span class="run-state">run_state=failed</span></div>
      <h3>Publication activation stopped</h3>
      <p class="failure-lede">The input failure is visible as a stable operator contract; the previous active Publication remains authoritative.</p>
      <div class="error-contract">
        <div><span>problem</span><code>pdf_ingest_failed</code></div>
        <div><span>cause</span><code>PDF cannot be opened</code></div>
        <div><span>active_publication_impact</span><code>unchanged</code></div>
        <div><span>next_step</span><code>fix_input_or_retry</code></div>
      </div>
    </article>
    <article class="refusal-card">
      <div class="card-topline"><span class="eyebrow">Agent consumer</span><span class="run-state run-state-muted">3 decisions</span></div>
      <h3>Consumer decisions stay distinct</h3>
      <p class="failure-lede">The same active-authority boundary keeps empty Search, capped Search, and stale Evidence recovery separate.</p>
      <div class="ask-result recovery-decisions">
        <div class="recovery-decision">
          <strong>selection.status=complete · matches=[]</strong>
          <span>Normal no-match: stop this search branch.</span>
        </div>
        <div class="recovery-decision">
          <strong>selection.status=capped</strong>
          <span>Terminal but non-exhaustive: do not claim corpus completeness.</span>
        </div>
        <div class="recovery-decision">
          <strong>problem=evidence_not_found</strong>
          <code>next_step=search_current_active_evidence</code>
          <span>Search the current active Evidence instead of retrying the stale identity.</span>
        </div>
      </div>
    </article>
  </div>
  <div class="recovery-strip">
    <span class="status-dot status-dot-danger" aria-hidden="true"></span>
    <strong>Active Publication is unchanged.</strong>
    <span class="muted">The failed Run and the three consumer decisions are independent closed results under the same safety boundary.</span>
    <span class="muted">Retry creates a new immutable Run; only a validated successful Run can switch the active set.</span>
  </div>
</section>
"""


def _frame_html(root: Path, frame: FrameSpec) -> str:
    items = _evidence_items(root)
    if frame.kind == "failure":
        surface = _failure_surface()
    else:
        surface = _normal_surface(frame.kind, items)
    provenance_items = (items[3],) if frame.kind == "search" else items
    return f"""<!doctype html>
<html lang="{LOCALE}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{_esc(frame.description)}">
  <link rel="icon" href="data:,">
  <title>{_esc(frame.title)} · MKE Evidence workspace</title>
  <link rel="stylesheet" href="{STYLE_NAME}">
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  <div class="frame-page">
    <header class="topbar app-width">
      <a class="brand" href="{INDEX_NAME}" aria-label="MKE showcase home">
        <span class="brand-mark">MKE</span>
        <span><span class="brand-kicker">Multimodal Knowledge Engine</span><strong>Evidence workspace</strong></span>
      </a>
      <div class="topbar-meta"><span class="demo-badge">SYNTHETIC / DEMO</span><span class="topbar-version">showcase v1</span></div>
    </header>
    <main id="main" class="app-width frame-main">
      <div class="frame-heading">
        <div><span class="eyebrow">{_esc(frame.kicker)}</span><h1>{_esc(frame.title)}</h1><p>{_esc(frame.description)}</p></div>
        <a class="back-link" href="{INDEX_NAME}">All frames <span aria-hidden="true">↗</span></a>
      </div>
      {_lifecycle(frame.kind)}
      {_source_strip(frame)}
      <div class="content-grid">
        <div class="main-column">{surface}</div>
        <aside class="sidebar" aria-label="Provenance and consumer state">
          {_observation_card(frame.kind)}
          {_provenance_card(provenance_items, kind=frame.kind)}
          {_consumer_card(frame.kind)}
        </aside>
      </div>
    </main>
    <footer class="footer app-width"><span>{_esc(SYNTHETIC_DISCLOSURE)}</span><span>1600×1000 · {LOCALE}</span></footer>
  </div>
</body>
</html>
"""


def _index_html() -> str:
    cards = "".join(
        f"""
<a class="gallery-card" href="{_esc(name)}.html">
  <div class="gallery-card-top"><span class="frame-number">0{index}</span><span class="gallery-format">1600×1000 PNG</span></div>
  <h2>{_esc(frame.title)}</h2>
  <p>{_esc(frame.description)}</p>
  <span class="gallery-asset">{_esc(name)}.png <span aria-hidden="true">↗</span></span>
</a>
"""
        for index, (name, frame) in enumerate(zip(FRAME_NAMES, FRAME_SPECS, strict=True), start=1)
    )
    return f"""<!doctype html>
<html lang="{LOCALE}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Static Evidence workspace showcase for MKE.">
  <link rel="icon" href="data:,">
  <title>MKE Evidence workspace showcase</title>
  <link rel="stylesheet" href="{STYLE_NAME}">
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  <div class="frame-page index-page">
    <header class="topbar app-width">
      <a class="brand" href="{INDEX_NAME}" aria-label="MKE showcase home">
        <span class="brand-mark">MKE</span>
        <span><span class="brand-kicker">Multimodal Knowledge Engine</span><strong>Evidence workspace</strong></span>
      </a>
      <div class="topbar-meta"><span class="demo-badge">SYNTHETIC / DEMO</span><span class="topbar-version">showcase v1</span></div>
    </header>
    <main id="main" class="app-width index-main">
      <div class="index-hero"><span class="eyebrow">Documentation projection</span><h1>From source material to trusted Evidence</h1><p>Three static frames make the existing MKE contract legible: a Run validates candidate output, an active Publication becomes consumable, and incomplete work stops without changing the active set.</p></div>
      <div class="gallery-grid">{cards}</div>
      <section class="index-note"><span class="mini-icon">i</span><p>{_esc(SYNTHETIC_DISCLOSURE)} The frames reuse repository-authored proof/export fixture state and current contract field names; they do not add a runtime surface.</p></section>
    </main>
    <footer class="footer app-width"><span>Source → Run → active Publication → Evidence → Consumer</span><span>1600×1000 canonical frames</span></footer>
  </div>
</body>
</html>
"""


CSS = r""":root {
  color-scheme: light;
  --ink: #12243a;
  --ink-soft: #43546a;
  --muted: #66758a;
  --line: #d9e2ec;
  --line-strong: #c5d3e1;
  --paper: #ffffff;
  --canvas: #eef3f7;
  --navy: #102e4a;
  --teal: #087f78;
  --teal-soft: #e6f5f2;
  --amber: #a86712;
  --amber-soft: #fff4df;
  --danger: #a93b38;
  --danger-soft: #fff0ee;
  --shadow: 0 18px 42px rgba(28, 52, 78, 0.09);
}

* { box-sizing: border-box; }

html { min-width: 0; background: var(--canvas); }

body {
  min-width: 0;
  margin: 0;
  background: var(--canvas);
  color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 15px;
  line-height: 1.45;
  text-rendering: optimizeLegibility;
}

a { color: inherit; text-decoration: none; }

a:focus-visible,
button:focus-visible {
  outline: 3px solid #f2b84b;
  outline-offset: 4px;
}

code {
  color: var(--navy);
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 0.78rem;
  overflow-wrap: anywhere;
}

.skip-link {
  position: fixed;
  z-index: 5;
  top: 12px;
  left: 12px;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--navy);
  color: #fff;
  transform: translateY(-160%);
}

.skip-link:focus { transform: translateY(0); }

.frame-page { min-height: 100vh; }

.app-width {
  width: min(100% - 96px, 1504px);
  margin-right: auto;
  margin-left: auto;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 88px;
  border-bottom: 1px solid var(--line);
}

.brand { display: inline-flex; align-items: center; gap: 13px; }

.brand-mark {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border-radius: 12px;
  background: var(--navy);
  color: #fff;
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.brand span:last-child { display: grid; gap: 2px; }

.brand-kicker,
.eyebrow,
.field-label,
.step-label {
  color: var(--muted);
  font-size: 0.67rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  line-height: 1.2;
  text-transform: uppercase;
}

.brand strong { font-size: 1rem; letter-spacing: -0.01em; }

.topbar-meta { display: inline-flex; align-items: center; gap: 15px; }

.demo-badge {
  padding: 5px 8px;
  border: 1px solid #9accc6;
  border-radius: 999px;
  background: var(--teal-soft);
  color: #09655f;
  font-size: 0.63rem;
  font-weight: 800;
  letter-spacing: 0.11em;
}

.topbar-version { color: var(--muted); font: 0.75rem "SFMono-Regular", Consolas, monospace; }

.frame-main { padding: 45px 0 20px; }

.frame-heading,
.surface-heading,
.side-card-heading,
.card-topline,
.evidence-heading,
.gallery-card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.frame-heading h1,
.index-hero h1 {
  max-width: 780px;
  margin: 8px 0 8px;
  color: var(--navy);
  font-size: clamp(2rem, 3.2vw, 3.2rem);
  letter-spacing: -0.045em;
  line-height: 1.03;
}

.frame-heading p,
.index-hero p {
  max-width: 710px;
  margin: 0;
  color: var(--ink-soft);
  font-size: 1.06rem;
}

.back-link {
  flex: 0 0 auto;
  margin-top: 6px;
  padding: 9px 13px;
  border: 1px solid var(--line-strong);
  border-radius: 9px;
  background: var(--paper);
  color: var(--navy);
  font-size: 0.82rem;
  font-weight: 700;
}

.back-link:hover { border-color: var(--teal); color: var(--teal); }

.lifecycle-rail {
  display: grid;
  grid-template-columns: 1fr auto 1fr auto 1fr auto 1fr auto 1fr;
  align-items: center;
  gap: 10px;
  margin: 33px 0 20px;
  padding: 14px 16px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.72);
}

.lifecycle-step { display: flex; min-width: 0; align-items: center; gap: 9px; }

.step-number {
  display: grid;
  flex: 0 0 auto;
  width: 26px;
  height: 26px;
  place-items: center;
  border: 1px solid var(--line-strong);
  border-radius: 50%;
  color: var(--muted);
  font: 0.68rem "SFMono-Regular", Consolas, monospace;
}

.lifecycle-step-active .step-number { border-color: #8cc9c1; background: var(--teal-soft); color: var(--teal); }
.lifecycle-step > div { display: grid; min-width: 0; gap: 2px; }
.lifecycle-step code { white-space: nowrap; }
.rail-arrow { color: #8b9bad; font-size: 1.1rem; }

.source-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 25px;
  padding: 16px 19px;
  border: 1px solid var(--line-strong);
  border-radius: 14px;
  background: var(--paper);
  box-shadow: 0 8px 22px rgba(28, 52, 78, 0.04);
}

.source-strip-main,
.publication-pill,
.publication-pill > div { display: grid; min-width: 0; gap: 3px; }
.source-strip-main strong { font-size: 1.03rem; }
.muted { color: var(--muted); font-size: 0.78rem; }

.publication-pill {
  grid-template-columns: auto auto;
  align-items: center;
  gap: 10px;
  min-width: 310px;
  padding-left: 21px;
  border-left: 1px solid var(--line);
}

.publication-pill > .muted { grid-column: 2; }
.status-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--teal); box-shadow: 0 0 0 5px var(--teal-soft); }
.status-dot-danger { background: var(--danger); box-shadow: 0 0 0 5px var(--danger-soft); }

.content-grid { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 22px; margin-top: 22px; }
.main-column { min-width: 0; }
.sidebar { display: grid; grid-template-rows: repeat(3, max-content); align-content: start; align-self: start; gap: 14px; min-width: 0; }

.surface-card,
.side-card {
  border: 1px solid var(--line);
  border-radius: 16px;
  background: var(--paper);
  box-shadow: var(--shadow);
}

.surface-card { padding: 24px; }
.surface-heading { align-items: center; margin-bottom: 20px; }
.surface-heading h2 { margin: 4px 0 0; color: var(--navy); font-size: 1.25rem; letter-spacing: -0.02em; }
.surface-state { padding: 6px 9px; border-radius: 999px; background: var(--teal-soft); color: #09655f; font: 0.7rem "SFMono-Regular", Consolas, monospace; white-space: nowrap; }
.surface-state-danger { background: var(--danger-soft); color: var(--danger); }

.query-bar {
  display: flex;
  min-height: 47px;
  align-items: center;
  gap: 10px;
  padding: 0 13px;
  border: 1px solid var(--line-strong);
  border-radius: 10px;
  background: #f8fafc;
}

.query-icon { color: var(--teal); font-size: 1.25rem; line-height: 1; }
.query-bar code { flex: 1 1 auto; font-size: 0.88rem; }
.query-status { padding: 4px 7px; border-radius: 6px; background: var(--teal-soft); color: #09655f; font-size: 0.68rem; font-weight: 800; }
.result-count { display: flex; justify-content: space-between; margin: 18px 0 9px; color: var(--muted); font-size: 0.74rem; }
.result-count strong { color: var(--navy); font: 0.8rem "SFMono-Regular", Consolas, monospace; }
.evidence-list { display: grid; gap: 12px; }

.evidence-card { padding: 17px; border: 1px solid var(--line); border-radius: 12px; background: #fbfcfd; }
.evidence-card-emphasis { border-color: #9dcfc9; background: linear-gradient(135deg, #ffffff, #f0faf8); }
.card-topline { align-items: center; }
.locator-kind { padding: 4px 7px; border-radius: 6px; background: var(--amber-soft); color: var(--amber); font: 0.68rem "SFMono-Regular", Consolas, monospace; }
.evidence-heading { align-items: center; margin-top: 13px; }
.evidence-heading h3 { margin: 0; color: var(--navy); font-size: 1.03rem; letter-spacing: -0.015em; }
.source-name { margin: 2px 0 0; color: var(--muted); font-size: 0.75rem; }
.verified-mark { display: grid; width: 27px; height: 27px; place-items: center; border-radius: 50%; background: var(--teal); color: #fff; font-weight: 900; }
.evidence-quote { margin: 14px 0 15px; color: var(--ink-soft); font-size: 0.9rem; }
.field-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 13px; padding-top: 13px; border-top: 1px solid var(--line); }
.field { display: grid; min-width: 0; gap: 3px; }
.field-wide { grid-column: 1 / -1; }
.field-label { font-size: 0.58rem; letter-spacing: 0.09em; }

.side-card { padding: 17px; box-shadow: 0 9px 24px rgba(28, 52, 78, 0.05); }
.side-card-heading { align-items: center; }
.mini-icon { display: grid; width: 22px; height: 22px; place-items: center; border-radius: 50%; background: var(--teal-soft); color: var(--teal); font-weight: 900; }
.side-note { margin: 9px 0 13px; color: var(--ink-soft); font-size: 0.78rem; }
.refusal-metric { display: flex; align-items: baseline; gap: 8px; margin: 15px 0 9px; }
.refusal-metric strong { color: var(--navy); font-size: 1.7rem; letter-spacing: -0.04em; }
.refusal-metric span { color: var(--muted); font-size: 0.76rem; }
.completion-bar { height: 6px; margin: 12px 0 4px; overflow: hidden; border-radius: 9px; background: #dcebe8; }
.completion-bar span { display: block; width: 100%; height: 100%; border-radius: inherit; background: var(--teal); }
.provenance-card .field-grid { gap: 9px; margin-top: 14px; padding-top: 13px; border-top: 1px solid var(--line); }
.provenance-empty { display: grid; gap: 5px; margin: 15px 0; }
.empty-line { display: block; width: 100%; height: 8px; border-radius: 4px; background: #f2d7d2; }
.empty-line.short { width: 62%; }
.provenance-empty strong { margin-top: 4px; color: var(--danger); font-size: 0.78rem; }

.consumer-list { display: grid; gap: 7px; }
.consumer-entry { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: center; gap: 8px; padding: 9px; border: 1px solid var(--line); border-radius: 9px; background: #fbfcfd; }
.consumer-entry:hover { border-color: #8cc9c1; background: var(--teal-soft); }
.consumer-name { min-width: 0; color: var(--navy); font-size: 0.75rem; font-weight: 800; }
.consumer-entry code { min-width: 0; color: var(--muted); font-size: 0.62rem; text-align: right; }
.entry-arrow { color: var(--teal); font-size: 0.82rem; }

.failure-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 13px; }
.failure-card,
.refusal-card { min-width: 0; padding: 18px; border: 1px solid #eac3bd; border-radius: 12px; background: var(--danger-soft); }
.refusal-card { border-color: #dfd0a8; background: #fffaf0; }
.run-state { padding: 4px 7px; border-radius: 6px; background: #f8d6d1; color: var(--danger); font: 0.68rem "SFMono-Regular", Consolas, monospace; }
.run-state-muted { background: #f3e8c6; color: var(--amber); }
.failure-card h3,
.refusal-card h3 { margin: 18px 0 7px; color: var(--navy); font-size: 1.05rem; }
.failure-lede { margin: 0 0 16px; color: var(--ink-soft); font-size: 0.82rem; }
.error-contract { display: grid; gap: 7px; }
.error-contract > div { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.25fr); gap: 8px; align-items: baseline; padding-top: 7px; border-top: 1px solid rgba(169, 59, 56, 0.16); }
.error-contract span { color: var(--danger); font: 0.61rem "SFMono-Regular", Consolas, monospace; overflow-wrap: anywhere; }
.error-contract code { color: #7d2724; font-size: 0.68rem; }
.ask-result { display: grid; gap: 8px; padding: 13px; border: 1px solid #ead9aa; border-radius: 9px; background: #fffdf8; }
.ask-result strong { color: #8a5a16; font: 0.74rem "SFMono-Regular", Consolas, monospace; overflow-wrap: anywhere; }
.ask-result span { color: var(--ink-soft); font-size: 0.76rem; }
.recovery-decisions { gap: 0; }
.recovery-decision { display: grid; gap: 4px; padding: 8px 0; border-top: 1px solid #ead9aa; }
.recovery-decision:first-child { padding-top: 0; border-top: 0; }
.recovery-decision:last-child { padding-bottom: 0; }
.recovery-decision code { color: #8a5a16; font-size: 0.68rem; overflow-wrap: anywhere; }
.recovery-strip { display: flex; align-items: center; gap: 11px; margin-top: 15px; padding: 13px 15px; border: 1px solid var(--line); border-radius: 10px; background: #fff; }
.recovery-strip strong { color: var(--navy); font-size: 0.82rem; }

.footer { display: flex; justify-content: space-between; gap: 18px; padding: 19px 0 28px; color: var(--muted); font-size: 0.7rem; }
.footer span:first-child { max-width: 850px; }

.index-main { padding: 80px 0 42px; }
.index-hero { max-width: 900px; }
.gallery-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 17px; margin-top: 42px; }
.gallery-card { display: flex; min-width: 0; min-height: 260px; flex-direction: column; padding: 21px; border: 1px solid var(--line); border-radius: 16px; background: var(--paper); box-shadow: var(--shadow); transition: transform 140ms ease, border-color 140ms ease; }
.gallery-card:hover { border-color: #8cc9c1; transform: translateY(-3px); }
.gallery-card-top { align-items: center; }
.frame-number { color: var(--teal); font: 1.05rem "SFMono-Regular", Consolas, monospace; font-weight: 800; }
.gallery-format { color: var(--muted); font: 0.68rem "SFMono-Regular", Consolas, monospace; }
.gallery-card h2 { margin: 36px 0 8px; color: var(--navy); font-size: 1.2rem; letter-spacing: -0.025em; }
.gallery-card p { margin: 0; color: var(--ink-soft); font-size: 0.82rem; }
.gallery-asset { margin-top: auto; padding-top: 23px; color: var(--teal); font: 0.7rem "SFMono-Regular", Consolas, monospace; }
.index-note { display: flex; gap: 12px; align-items: flex-start; max-width: 850px; margin-top: 28px; padding: 16px 18px; border: 1px solid #c5dedb; border-radius: 12px; background: var(--teal-soft); }
.index-note p { margin: 0; color: #245a57; font-size: 0.8rem; }

@media (min-width: 1101px) {
  .topbar { min-height: 72px; }
  .frame-main { padding-top: 24px; }
  .frame-heading h1 { font-size: 2.8rem; margin-top: 6px; }
  .frame-heading p { font-size: 0.95rem; }
  .lifecycle-rail { margin-top: 18px; margin-bottom: 8px; padding: 10px 14px; }
  .source-strip { padding: 10px 14px; }
  .content-grid { margin-top: 12px; }
  .surface-card { padding: 17px; }
  .side-card { padding: 10px; }
  .sidebar { gap: 10px; }
  .side-card > code { white-space: nowrap; font-size: 0.62rem; letter-spacing: -0.04em; }
  .side-note { margin: 5px 0 7px; font-size: 0.7rem; line-height: 1.25; }
  .refusal-metric { margin: 8px 0 5px; }
  .refusal-metric strong { font-size: 1.35rem; }
  .completion-bar { margin: 7px 0 3px; }
  .provenance-card .field-grid { gap: 6px; margin-top: 8px; padding-top: 8px; }
  .provenance-card .field code { font-size: 0.62rem; }
  .consumer-list { gap: 4px; }
  .consumer-entry { gap: 4px; padding: 4px 6px; }
  .consumer-entry code { overflow: hidden; font-size: 0.54rem; text-overflow: ellipsis; white-space: nowrap; }
  .consumer-card .side-note { margin: 3px 0 5px; }
}

@media (max-width: 1100px) {
  .app-width { width: min(100% - 52px, 100%); }
  .lifecycle-rail { grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 7px; }
  .rail-arrow { display: none; }
  .content-grid { grid-template-columns: minmax(0, 1fr) 280px; }
  .publication-pill { min-width: 275px; }
}

@media (max-width: 820px) {
  .topbar { min-height: 76px; }
  .topbar-meta { gap: 8px; }
  .topbar-version { display: none; }
  .frame-main { padding-top: 32px; }
  .content-grid { grid-template-columns: 1fr; }
  .sidebar { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .source-strip { align-items: stretch; flex-direction: column; gap: 15px; }
  .publication-pill { min-width: 0; padding-top: 14px; padding-left: 0; border-top: 1px solid var(--line); border-left: 0; }
  .gallery-grid { grid-template-columns: 1fr; }
  .gallery-card { min-height: 200px; }
  .index-main { padding-top: 52px; }
}

@media (max-width: 620px) {
  .app-width { width: calc(100% - 32px); }
  .topbar { min-height: 72px; }
  .brand-mark { width: 36px; height: 36px; border-radius: 10px; }
  .brand-kicker { font-size: 0.58rem; }
  .brand strong { font-size: 0.88rem; }
  .demo-badge { padding: 4px 6px; font-size: 0.56rem; }
  .frame-heading { display: block; }
  .frame-heading h1,
  .index-hero h1 { font-size: 2.05rem; }
  .back-link { display: inline-block; margin-top: 18px; }
  .lifecycle-rail { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px 8px; }
  .lifecycle-step:last-child { grid-column: 1 / -1; }
  .source-strip { padding: 14px; }
  .surface-card { padding: 16px; }
  .surface-heading { align-items: flex-start; flex-direction: column; }
  .query-bar { align-items: flex-start; flex-wrap: wrap; padding: 11px; }
  .query-bar code { flex-basis: calc(100% - 28px); }
  .query-status { margin-left: 28px; }
  .field-grid { grid-template-columns: 1fr; }
  .field-wide { grid-column: auto; }
  .sidebar { grid-template-columns: 1fr; }
  .failure-grid { grid-template-columns: 1fr; }
  .recovery-strip { align-items: flex-start; flex-wrap: wrap; }
  .footer { align-items: flex-start; flex-direction: column; }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { scroll-behavior: auto !important; transition-duration: 0.01ms !important; animation-duration: 0.01ms !important; }
}
"""


def _write_static(root: Path) -> Path:
    showcase = root / SHOWCASE_RELATIVE
    showcase.mkdir(parents=True, exist_ok=True)
    (showcase / STYLE_NAME).write_text(CSS.rstrip() + "\n", encoding="utf-8")
    (showcase / INDEX_NAME).write_text(_clean_markup(_index_html()), encoding="utf-8")
    for frame in FRAME_SPECS:
        (showcase / f"{frame.slug}.html").write_text(
            _clean_markup(_frame_html(root, frame)), encoding="utf-8"
        )
    return showcase


def _clean_markup(markup: str) -> str:
    return "\n".join(line.rstrip() for line in markup.splitlines()) + "\n"


def _png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path.name} is not a PNG")
    if data[12:16] != b"IHDR" or int.from_bytes(data[8:12], "big") != 13:
        raise ValueError(f"{path.name} has an invalid PNG header")
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    return width, height


def _source_tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for relative in SOURCE_TREE_FILES:
        path = root / relative
        if not path.is_file():
            raise ValueError(f"showcase source file is missing: {relative}")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _default_source_commit(root: Path) -> str:
    for reference in ("origin/main", "HEAD"):
        result = subprocess.run(
            ["git", "rev-parse", reference],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        commit = result.stdout.strip()
        if result.returncode == 0 and COMMIT_RE.fullmatch(commit):
            return commit
    raise ValueError("unable to resolve a source commit")


def _manifest(root: Path, source_commit: str) -> dict[str, object]:
    if COMMIT_RE.fullmatch(source_commit) is None:
        raise ValueError("source_commit must be a 40-character lowercase commit")
    showcase = root / SHOWCASE_RELATIVE
    assets: dict[str, object] = {}
    for name, route, state in ASSET_SPECS:
        path = showcase / name
        width, height = _png_size(path)
        if (width, height) != (VIEWPORT["width"], VIEWPORT["height"]):
            raise ValueError(f"{name} does not match the canonical viewport")
        assets[name] = {
            "bytes": path.stat().st_size,
            "height": height,
            "locale": LOCALE,
            "route": route,
            "sha256": _sha256(path),
            "source_commit": source_commit,
            "state": state,
            "synthetic_demo_disclosure": SYNTHETIC_DISCLOSURE,
            "viewport": VIEWPORT,
            "width": width,
        }
    return {
        "assets": assets,
        "fixture_state": FIXTURE_STATE,
        "locale": LOCALE,
        "schema_version": MANIFEST_SCHEMA,
        "source_commit": source_commit,
        "source_tree_sha256": _source_tree_sha256(root),
        "static_files": list(STATIC_FILES),
        "synthetic_demo_disclosure": SYNTHETIC_DISCLOSURE,
        "viewport": VIEWPORT,
    }


def _write_manifest(root: Path, source_commit: str) -> dict[str, object]:
    manifest = _manifest(root, source_commit)
    (root / SHOWCASE_RELATIVE / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _resolve_playwright(explicit: Path | None) -> Path:
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(explicit)
    configured = os.environ.get("MKE_PLAYWRIGHT_CLI")
    if configured:
        candidates.append(Path(configured))
    installed = shutil.which("playwright-cli")
    if installed:
        candidates.append(Path(installed))
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise FileNotFoundError("playwright-cli is unavailable; pass --playwright-cli explicitly")


class _QuietStaticHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        del format, args


@contextmanager
def _local_static_server(directory: Path) -> Generator[str, None, None]:
    handler = functools.partial(_QuietStaticHandler, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def render_showcase(root: Path, *, playwright_cli: Path | None = None) -> None:
    cli = _resolve_playwright(playwright_cli)
    showcase = root / SHOWCASE_RELATIVE
    session = f"mke-showcase-{os.getpid()}"
    try:
        with _local_static_server(showcase) as base_url:
            for frame_name, png_name in zip(FRAME_FILES, PNG_NAMES, strict=True):
                asset = showcase / png_name
                command_prefix = [str(cli), "--session", session]
                subprocess.run(
                    [*command_prefix, "open", f"{base_url}/{frame_name}"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                subprocess.run(
                    [
                        *command_prefix,
                        "resize",
                        str(VIEWPORT["width"]),
                        str(VIEWPORT["height"]),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                screenshot_code = (
                    "async page => { await page.screenshot({path: "
                    + json.dumps(str(asset.resolve()))
                    + ", fullPage: false}); return true; }"
                )
                subprocess.run(
                    [*command_prefix, "run-code", screenshot_code],
                    check=True,
                    capture_output=True,
                    text=True,
                )
    finally:
        subprocess.run(
            [str(cli), "--session", session, "close"],
            check=False,
            capture_output=True,
            text=True,
        )


def verify_showcase(root: Path) -> dict[str, object]:
    showcase = root / SHOWCASE_RELATIVE
    if not showcase.is_dir():
        raise AssertionError("docs/showcase is missing")
    expected_files = {"manifest.json", *STATIC_FILES, *PNG_NAMES}
    actual_files = {path.name for path in showcase.iterdir() if path.is_file()}
    if actual_files != expected_files:
        raise AssertionError(
            f"showcase inventory mismatch: expected {sorted(expected_files)}, "
            f"got {sorted(actual_files)}"
        )
    manifest_path = showcase / "manifest.json"
    manifest_value = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest_value, dict):
        raise AssertionError("showcase manifest must be an object")
    manifest = cast(dict[str, object], manifest_value)
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise AssertionError("showcase manifest schema is invalid")
    source_commit = manifest.get("source_commit")
    source_tree = manifest.get("source_tree_sha256")
    if not isinstance(source_commit, str) or COMMIT_RE.fullmatch(source_commit) is None:
        raise AssertionError("showcase source_commit is invalid")
    if not isinstance(source_tree, str) or source_tree != _source_tree_sha256(root):
        raise AssertionError("showcase source tree identity does not match")
    if manifest.get("fixture_state") != FIXTURE_STATE:
        raise AssertionError("showcase fixture state is invalid")
    if manifest.get("viewport") != VIEWPORT or manifest.get("locale") != LOCALE:
        raise AssertionError("showcase viewport or locale is invalid")
    if manifest.get("synthetic_demo_disclosure") != SYNTHETIC_DISCLOSURE:
        raise AssertionError("showcase disclosure is invalid")
    if manifest.get("static_files") != list(STATIC_FILES):
        raise AssertionError("showcase static file inventory is invalid")
    assets_value = manifest.get("assets")
    if not isinstance(assets_value, dict):
        raise AssertionError("showcase asset inventory is invalid")
    assets = cast(dict[str, object], assets_value)
    if set(assets) != set(PNG_NAMES):
        raise AssertionError("showcase asset inventory is invalid")
    for name, route, state in ASSET_SPECS:
        entry_value = assets.get(name)
        path = showcase / name
        if not isinstance(entry_value, dict):
            raise AssertionError(f"showcase asset entry is invalid: {name}")
        entry = cast(dict[str, object], entry_value)
        route_path = showcase / route
        if not route_path.is_file():
            raise AssertionError(f"showcase asset route is missing: {name}")
        width, height = _png_size(path)
        expected = {
            "bytes": path.stat().st_size,
            "height": height,
            "locale": LOCALE,
            "route": route,
            "sha256": _sha256(path),
            "source_commit": source_commit,
            "state": state,
            "synthetic_demo_disclosure": SYNTHETIC_DISCLOSURE,
            "viewport": VIEWPORT,
            "width": width,
        }
        if entry != expected or (width, height) != (VIEWPORT["width"], VIEWPORT["height"]):
            raise AssertionError(f"showcase asset identity is invalid: {name}")
    for name in FRAME_FILES:
        markup = (showcase / name).read_text(encoding="utf-8")
        if 'lang="en-US"' not in markup or f"{STYLE_NAME}" not in markup:
            raise AssertionError(f"showcase frame is not static HTML: {name}")
    return {
        "locale": LOCALE,
        "png_names": sorted(PNG_NAMES),
        "source_commit": source_commit,
        "source_tree_sha256": source_tree,
        "viewport": dict(VIEWPORT),
    }


def generate_showcase(
    root: Path,
    *,
    source_commit: str | None = None,
    render: bool = False,
    playwright_cli: Path | None = None,
) -> dict[str, object]:
    """Write static files, optionally render PNGs, and write the manifest."""

    resolved_root = root.resolve()
    _write_static(resolved_root)
    if render:
        render_showcase(resolved_root, playwright_cli=playwright_cli)
    commit = source_commit or _default_source_commit(resolved_root)
    _write_manifest(resolved_root, commit)
    return verify_showcase(resolved_root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--render", action="store_true", help="render PNGs through Playwright CLI")
    parser.add_argument("--verify", action="store_true", help="verify existing static output")
    parser.add_argument("--source-commit")
    parser.add_argument("--playwright-cli", type=Path)
    args = parser.parse_args()
    if args.verify and (args.render or args.source_commit is not None):
        parser.error("--verify cannot be combined with --render or --source-commit")
    try:
        if args.verify:
            verify_showcase(args.root.resolve())
        else:
            generate_showcase(
                args.root,
                source_commit=args.source_commit,
                render=args.render,
                playwright_cli=args.playwright_cli,
            )
    except (AssertionError, FileNotFoundError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"evidence_showcase status=failed reason={type(error).__name__}")
        return 1
    print(
        "evidence_showcase status=passed "
        f"pngs={len(PNG_NAMES)} viewport={VIEWPORT['width']}x{VIEWPORT['height']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
