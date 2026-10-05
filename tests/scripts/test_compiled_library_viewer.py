from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from mke.adapters.filesystem import publish_compiled_library
from mke.domain import (
    ActivePublicationObservation,
    CompiledEvidenceSnapshot,
    CompiledLibrarySnapshotV2,
    CompiledSourceSnapshotV2,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build_compiled_library_viewer.py"
_MIB = 1024 * 1024
MALICIOUS_TEXT = "<script>fetch('https://evil.invalid')</script>\n中文\t保留空白"


def _source(
    tmp_path: Path, index: int, text: str, *, evidence_count: int = 1
) -> CompiledSourceSnapshotV2:
    tmp_path.mkdir(parents=True, exist_ok=True)
    raw = tmp_path / f"input-{index}.pdf"
    raw.write_bytes(f"fixture source {index}\n".encode())
    fingerprint = f"sha256:{hashlib.sha256(raw.read_bytes()).hexdigest()}"
    identity = f"{index:032x}"
    evidence = tuple(
        CompiledEvidenceSnapshot(
            evidence_id=f"ev_{index * 10_000 + row:032x}",
            source_id=f"src_{identity}",
            content_fingerprint=fingerprint,
            publication_id=f"pub_{identity}",
            publication_revision=3,
            run_id=f"run_{identity}",
            locator_kind="page",
            locator_start=row + 1,
            locator_end=row + 1,
            text=text if evidence_count == 1 else f"evidence {index}-{row}",
        )
        for row in range(evidence_count)
    )
    return CompiledSourceSnapshotV2(
        source_id=f"src_{identity}",
        display_name=("<b>资料</b>" if index == 1 else f"fixture-{index}") + ".pdf",
        content_fingerprint=fingerprint,
        media_type="application/pdf",
        publication_id=f"pub_{identity}",
        publication_revision=3,
        run_id=f"run_{identity}",
        extractor_fingerprint="pymupdf-text-v1",
        required_stages=("candidate_evidence", "pdf_text_extraction"),
        evidence=evidence,
    )


def _timestamp_source(
    tmp_path: Path,
    index: int,
    texts: tuple[str, ...],
) -> CompiledSourceSnapshotV2:
    tmp_path.mkdir(parents=True, exist_ok=True)
    raw = tmp_path / f"input-{index}.mp3"
    raw.write_bytes(f"fixture audio {index}\n".encode())
    fingerprint = f"sha256:{hashlib.sha256(raw.read_bytes()).hexdigest()}"
    identity = f"{index:032x}"
    evidence = tuple(
        CompiledEvidenceSnapshot(
            evidence_id=f"ev_{index:016x}{row:016x}",
            source_id=f"src_{identity}",
            content_fingerprint=fingerprint,
            publication_id=f"pub_{identity}",
            publication_revision=3,
            run_id=f"run_{identity}",
            locator_kind="timestamp_ms",
            locator_start=row * 1000,
            locator_end=(row + 1) * 1000,
            text=text,
        )
        for row, text in enumerate(texts)
    )
    return CompiledSourceSnapshotV2(
        source_id=f"src_{identity}",
        display_name=f"fixture-{index}.mp3",
        content_fingerprint=fingerprint,
        media_type="audio/mpeg",
        publication_id=f"pub_{identity}",
        publication_revision=3,
        run_id=f"run_{identity}",
        extractor_fingerprint=f"faster-whisper-audio-v1:{'a' * 64}",
        required_stages=("audio_transcription", "candidate_evidence"),
        evidence=evidence,
    )


def _publish(
    tmp_path: Path,
    sources: tuple[CompiledSourceSnapshotV2, ...],
    *,
    name: str = "compiled-library-v2",
) -> Path:
    snapshot = CompiledLibrarySnapshotV2(
        observation=ActivePublicationObservation(
            "local",
            "active",
            len(sources),
            len(sources),
            sum(len(source.evidence) for source in sources),
        ),
        sources=tuple(sorted(sources, key=lambda source: source.content_fingerprint)),
    )
    publish_compiled_library(
        snapshot,
        format_version="v2",
        output_name=name,
        parent=tmp_path,
    )
    return tmp_path / name


def _valid_export(tmp_path: Path) -> Path:
    return _publish(tmp_path, (_source(tmp_path, 1, MALICIOUS_TEXT),))


def test_public_builder_imports_from_repository_root(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "compiled_library_viewer", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    export = _valid_export(tmp_path)
    result = module.build_viewer(export, tmp_path / "viewer.html")

    assert result.source_count == 1
    assert result.evidence_count == 1


def _run(export: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--export", str(export), "--output", str(output)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_viewer_binds_actual_export_and_escapes_untrusted_text(tmp_path: Path) -> None:
    export = _valid_export(tmp_path)
    before = {
        path.relative_to(export).as_posix(): path.read_bytes()
        for path in export.rglob("*")
        if path.is_file()
    }
    output = tmp_path / "library-viewer.html"

    result = _run(export, output)

    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout == "compiled_library_viewer=passed source_count=1 evidence_count=1\n"
    assert output.is_file()
    html = output.read_text(encoding="utf-8")
    assert "资料与引用" in html
    assert "筛选导出内容" in html
    assert "<script>fetch('https://evil.invalid')</script>" not in html
    assert "\\u003cscript\\u003efetch" in html
    assert "eval(" not in html
    assert "fetch(" not in html.split("</script>", 1)[1]
    assert "selected.source." not in html
    marker = '<script type="application/json" id="viewer-data">'
    payload = html.split(marker, 1)[1].split("</script>", 1)[0]
    data = json.loads(payload)
    assert data["sources"][0]["display_name"] == "<b>资料</b>.pdf"
    assert data["sources"][0]["evidence"][0]["text"] == MALICIOUS_TEXT
    assert data["sources"][0]["evidence"][0]["locator"] == {
        "kind": "page",
        "start": 1,
        "end": 1,
    }
    assert data["sources"][0]["evidence"][0]["publication_revision"] == 3
    after = {
        path.relative_to(export).as_posix(): path.read_bytes()
        for path in export.rglob("*")
        if path.is_file()
    }
    assert after == before


def _data(html: str) -> dict[str, Any]:
    marker = '<script type="application/json" id="viewer-data">'
    return json.loads(html.split(marker, 1)[1].split("</script>", 1)[0])


def test_v2_pdf_viewer_observation_is_unknown(tmp_path: Path) -> None:
    export = _valid_export(tmp_path)
    output = tmp_path / "v2.html"
    assert _run(export, output).returncode == 0
    data = _data(output.read_text())
    source = data["sources"][0]
    assert source["pdf_extraction_observation"]["status"] == "not_observed"
    assert source["pdf_extraction_observation"]["mixed_text_raster_pages"] is None
    assert source["evidence"][0]["text"] == MALICIOUS_TEXT


def test_v3_viewer_binds_native_observations_and_preserves_text(tmp_path: Path) -> None:
    from tests.interfaces.test_pdf_observation_export_v3 import export as native_export
    from tests.interfaces.test_pdf_observation_source_v2 import browse, library, selected

    config = library(tmp_path)
    source = selected(config)
    observation = browse(config, source)["source"]["pdf_extraction_observation"]
    directory = native_export(config.db_path, tmp_path, "native-v3", "v3")
    output = tmp_path / "v3.html"
    result = _run(directory, output)
    assert result.returncode == 0, result.stdout + result.stderr
    data = _data(output.read_text())
    assert data["export_schema"] == "mke.compiled_library_export.v3"
    rendered = data["sources"][0]
    assert rendered["pdf_extraction_observation"] == observation
    assert [row["text"] for row in rendered["evidence"]] == [
        "text on page 1", "text on page 2", "text on page 3",
    ]
    assert rendered["source_id"] == source["source_id"]
    assert rendered["publication_id"] == source["publication_id"]
    assert rendered["run_id"] == source["run_id"]


def test_viewer_rejects_v1_or_mutated_input_without_success_artifact(tmp_path: Path) -> None:
    export = _valid_export(tmp_path)
    manifest_path = export / "export-manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["schema_version"] = "mke.compiled_library_export.v1"
    manifest_path.write_bytes(
        (
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode()
    )
    output = tmp_path / "invalid.html"

    result = _run(export, output)

    assert result.returncode == 1
    assert result.stderr == ""
    assert "compiled Library Export v2" in result.stdout
    assert str(tmp_path) not in result.stdout
    assert not output.exists()


def test_viewer_rejects_existing_output_and_output_inside_input(tmp_path: Path) -> None:
    export = _valid_export(tmp_path)
    collision = tmp_path / "collision.html"
    collision.write_text("keep", encoding="utf-8")

    collision_result = _run(export, collision)

    assert collision_result.returncode == 1
    assert "already exists" in collision_result.stdout
    assert collision.read_text(encoding="utf-8") == "keep"

    nested = export / "viewer.html"
    nested_result = _run(export, nested)

    assert nested_result.returncode == 1
    assert "outside the export" in nested_result.stdout
    assert not nested.exists()


def test_viewer_enforces_source_and_evidence_count_budgets(tmp_path: Path) -> None:
    exact_sources = tuple(
        _source(tmp_path / "exact-sources", index + 1, f"source {index}")
        for index in range(64)
    )
    exact_export = _publish(tmp_path / "exact-sources", exact_sources, name="export")
    exact_result = _run(exact_export, tmp_path / "exact-sources.html")
    assert exact_result.returncode == 0

    over_sources = tuple(
        _source(tmp_path / "over-sources", index + 1, f"source {index}")
        for index in range(65)
    )
    over_export = _publish(tmp_path / "over-sources", over_sources, name="export")
    over_result = _run(over_export, tmp_path / "over-sources.html")
    assert over_result.returncode == 1
    assert "64 Sources" in over_result.stdout

    exact_evidence = _timestamp_source(
        tmp_path / "exact-evidence",
        1,
        tuple(f"evidence {index}" for index in range(2_000)),
    )
    exact_evidence_export = _publish(
        tmp_path / "exact-evidence",
        (exact_evidence,),
        name="export",
    )
    exact_evidence_result = _run(
        exact_evidence_export,
        tmp_path / "exact-evidence.html",
    )
    assert exact_evidence_result.returncode == 0

    over_evidence = _timestamp_source(
        tmp_path / "over-evidence",
        1,
        tuple(f"evidence {index}" for index in range(2_001)),
    )
    over_evidence_export = _publish(
        tmp_path / "over-evidence",
        (over_evidence,),
        name="export",
    )
    over_evidence_result = _run(
        over_evidence_export,
        tmp_path / "over-evidence.html",
    )
    assert over_evidence_result.returncode == 1
    assert "2,000 Evidence" in over_evidence_result.stdout


@pytest.mark.parametrize("extra_bytes", [0, 1])
def test_viewer_enforces_aggregate_utf8_budget(tmp_path: Path, extra_bytes: int) -> None:
    base = (8 * _MIB) // 9
    remainder = (8 * _MIB) - (base * 9)
    texts = tuple(
        "x" * (base + (remainder if index == 8 else 0))
        for index in range(9)
    )
    if extra_bytes:
        texts = texts[:-1] + (texts[-1] + "x",)
    export_root = tmp_path / f"aggregate-{extra_bytes}"
    export = _publish(
        export_root,
        (_timestamp_source(export_root, 1, texts),),
        name="export",
    )

    result = _run(export, export_root.with_suffix(".html"))

    if extra_bytes == 0:
        assert result.returncode == 0
    else:
        assert result.returncode == 1
        assert "8 MiB" in result.stdout


def _run_dom_harness(html: str) -> subprocess.CompletedProcess[str]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the compiled Viewer DOM regression")
    harness = r'''
const fs = require("node:fs");
const vm = require("node:vm");

const html = fs.readFileSync(0, "utf8");
const marker = '<script type="application/json" id="viewer-data">';
const payload = html.split(marker)[1].split("</script>")[0];
const scriptStart = html.indexOf("    (() => {");
const scriptEnd = html.lastIndexOf("    })();") + "    })();".length;
const viewerScript = html.slice(scriptStart, scriptEnd);
const data = JSON.parse(payload);

class Element {
  constructor(tagName, ownerDocument) {
    this.tagName = tagName.toUpperCase();
    this.ownerDocument = ownerDocument;
    this.children = [];
    this.parentNode = null;
    this.attributes = {};
    this.listeners = {};
    this._textContent = "";
    this.hidden = false;
    this.value = "";
    this.dataset = new Proxy({}, {
      set: (target, key, value) => {
        target[key] = String(value);
        const attribute = String(key).replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`);
        this.attributes[`data-${attribute}`] = String(value);
        return true;
      }
    });
  }

  set id(value) { this._id = String(value); }
  get id() { return this._id || ""; }
  set textContent(value) {
    this._textContent = String(value);
    this.replaceChildren();
  }
  get textContent() {
    return this._textContent + this.children.map((child) => child.textContent).join("");
  }
  set className(value) { this._className = String(value); }
  get className() { return this._className || ""; }
  append(...items) {
    items.forEach((item) => {
      if (!item) return;
      item.parentNode = this;
      this.children.push(item);
    });
  }
  replaceChildren(...items) {
    this.children.forEach((child) => { child.parentNode = null; });
    this.children = [];
    this.append(...items);
  }
  after(...items) {
    if (!this.parentNode) return;
    const index = this.parentNode.children.indexOf(this);
    items.forEach((item, offset) => {
      item.parentNode = this.parentNode;
      this.parentNode.children.splice(index + 1 + offset, 0, item);
    });
  }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) {
    const present = Object.prototype.hasOwnProperty.call(this.attributes, name);
    return present ? this.attributes[name] : null;
  }
  addEventListener(type, handler) {
    (this.listeners[type] ||= []).push(handler);
  }
  dispatchEvent(event) {
    const next = typeof event === "string" ? { type: event } : event;
    next.target ||= this;
    (this.listeners[next.type] || []).forEach((handler) => handler(next));
  }
  click() {
    this.focus();
    this.dispatchEvent({ type: "click", target: this });
  }
  focus() { this.ownerDocument.activeElement = this; }
  select() { this.selected = true; }
  remove() {
    if (!this.parentNode) return;
    this.parentNode.children = this.parentNode.children.filter((child) => child !== this);
    this.parentNode = null;
  }
  scrollIntoView() { this.ownerDocument.scrolledIds.push(this.id); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  querySelectorAll(selector) {
    const result = [];
    const visit = (element) => {
      element.children.forEach((child) => {
        if (matchesSelector(child, selector)) result.push(child);
        visit(child);
      });
    };
    visit(this);
    return result;
  }
}

function matchesSelector(element, selector) {
  if (selector.startsWith(".")) return element.className.split(/\s+/).includes(selector.slice(1));
  if (selector.startsWith("#")) return element.id === selector.slice(1);
  const attribute = selector.match(/^(?:([a-z]+))?\[([^=]+)="([^"]*)"\]$/i);
  if (attribute) {
    return (!attribute[1] || element.tagName.toLowerCase() === attribute[1].toLowerCase())
      && element.getAttribute(attribute[2]) === attribute[3];
  }
  return element.tagName.toLowerCase() === selector.toLowerCase();
}

function createDocument() {
  const document = {
    activeElement: null,
    roots: [],
    scrolledIds: [],
    createElement(tagName) { return new Element(tagName, document); },
    getElementById(id) {
      const visit = (element) => {
        if (element.id === id) return element;
        for (const child of element.children) {
          const match = visit(child);
          if (match) return match;
        }
        return null;
      };
      for (const root of document.roots) {
        const match = visit(root);
        if (match) return match;
      }
      return null;
    },
    querySelector(selector) {
      for (const root of document.roots) {
        const match = matchesSelector(root, selector) ? root : root.querySelector(selector);
        if (match) return match;
      }
      return null;
    }
  };
  const roots = [
    ["viewer-data", "script"],
    ["filter-input", "input"],
    ["clear-filter", "button"],
    ["filter-summary", "p"],
    ["source-count", "span"],
    ["source-list", "div"],
    ["reader-content", "section"],
    ["snapshot-summary", "p"]
  ];
  roots.forEach(([id, tagName]) => {
    const root = new Element(tagName, document);
    root.id = id;
    document.roots.push(root);
  });
  document.getElementById("viewer-data").textContent = payload;
  return document;
}

function boot(initialHash) {
  const document = createDocument();
  const listeners = {};
  let hashchangeCount = 0;
  let replaceStateCount = 0;
  const location = {
    hash: initialHash,
    pathname: "/viewer.html",
    search: "",
    href: `/viewer.html${initialHash}`
  };
  const history = {
    replaceState(_state, _title, url) {
      replaceStateCount += 1;
      const replacement = String(url);
      const hashIndex = replacement.indexOf("#");
      location.hash = hashIndex >= 0 ? replacement.slice(hashIndex) : "";
      location.href = replacement;
    }
  };
  const window = {
    location,
    history,
    addEventListener(type, handler) { (listeners[type] ||= []).push(handler); }
  };
  const context = {
    document,
    location,
    navigator: { clipboard: null },
    window,
    console,
    CSS: { escape: (value) => String(value) },
    requestAnimationFrame: (callback) => callback(),
    setTimeout: (callback) => { callback(); return 1; },
    queueMicrotask,
  };
  context.globalThis = context;
  vm.runInNewContext(viewerScript, context, { filename: "compiled-library-viewer.js" });
  return {
    document,
    filter: document.getElementById("filter-input"),
    clear: document.getElementById("clear-filter"),
    sourceList: document.getElementById("source-list"),
    reader: document.getElementById("reader-content"),
    location,
    hashchangeCount: () => hashchangeCount,
    replaceStateCount: () => replaceStateCount,
    setHash(value) {
      if (location.hash === value) return;
      location.hash = value;
      location.href = `${location.pathname}${location.search}${value}`;
      hashchangeCount += 1;
      (listeners.hashchange || []).forEach((handler) => handler({ type: "hashchange" }));
    }
  };
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function sourceButton(app, sourceId) {
  return app.sourceList.children.find((button) => button.dataset.sourceId === sourceId) || null;
}

function assertSelection(app, sourceId) {
  const buttons = app.sourceList.children.filter((child) => child.tagName === "BUTTON");
  const selected = sourceButton(app, sourceId);
  assert(selected, `missing Source button for ${sourceId}`);
  assert(selected.getAttribute("aria-pressed") === "true", "selected Source is not pressed");
  assert(
    selected.getAttribute("aria-selected") === null,
    "native button still exposes aria-selected"
  );
  buttons.filter((button) => button !== selected).forEach((button) => {
    assert(button.getAttribute("aria-pressed") === "false", "unselected Source is pressed");
  });
}

const first = data.sources[0];
const second = data.sources[1];
const targetId = `evidence-${second.evidence[0].evidence_id}`;

const defaultApp = boot("");
assertSelection(defaultApp, first.source_id);

const initialHashApp = boot(`#${targetId}`);
assertSelection(initialHashApp, second.source_id);
assert(initialHashApp.document.getElementById(targetId), "initial fragment target is not rendered");
assert(
  initialHashApp.document.scrolledIds.includes(targetId),
  "initial fragment target was not revealed"
);

const app = boot("");
app.setHash(`#${targetId}`);
assertSelection(app, second.source_id);
assert(app.document.getElementById(targetId), "hashchange target is not rendered");
assert(app.document.scrolledIds.includes(targetId), "hashchange target was not revealed");
const hashChangesBeforeRepeat = app.hashchangeCount();
app.setHash(`#${targetId}`);
assert(
  app.hashchangeCount() === hashChangesBeforeRepeat,
  "same hash emitted a synthetic hashchange"
);

sourceButton(app, first.source_id).click();
assert(app.location.hash === "", "known fragment survived a cross-Source activation");
assert(app.replaceStateCount() === 1, "cross-Source activation added an unexpected history entry");

app.filter.focus();
app.filter.value = first.evidence[0].text;
app.filter.dispatchEvent({ type: "input", target: app.filter });
assert(app.document.activeElement === app.filter, "filter input lost focus while filtering");
assert(app.location.hash === "", "filtered Source state retained a hidden known fragment");
app.setHash(`#${targetId}`);
assertSelection(app, second.source_id);
assert(app.document.getElementById(targetId), "filtered-out fragment target was not revealed");
app.filter.value = first.evidence[0].text;
app.filter.dispatchEvent({ type: "input", target: app.filter });
assert(app.location.hash === "", "filtering hid the current known fragment without clearing it");
app.setHash(`#${targetId}`);
assertSelection(app, second.source_id);

app.setHash("#unknown-fragment");
assertSelection(app, second.source_id);
assert(app.location.hash === "#unknown-fragment", "unknown fragment was rewritten");

const beforeClick = sourceButton(app, second.source_id);
beforeClick.click();
const afterClick = sourceButton(app, second.source_id);
assert(
  afterClick && app.document.activeElement === afterClick,
  "Source focus was not restored after render"
);
assert(afterClick !== beforeClick, "Source click did not rebuild the Source controls");

const malformedFragment = "#%E0%A4%A";
app.setHash(malformedFragment);
assertSelection(app, second.source_id);
assert(app.location.hash === malformedFragment, "malformed fragment was rewritten");

app.filter.focus();
app.filter.value = first.evidence[0].text;
app.filter.dispatchEvent({ type: "input", target: app.filter });
app.clear.click();
assert(app.document.activeElement === app.filter, "clear-filter did not restore filter focus");

process.stdout.write("compiled_library_viewer_dom=passed\n");
'''
    return subprocess.run(
        [node, "-e", harness],
        input=html,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_viewer_resolves_fragments_and_preserves_native_source_focus(tmp_path: Path) -> None:
    first = _timestamp_source(tmp_path / "first", 1, ("first unique", "first other"))
    second = _timestamp_source(tmp_path / "second", 2, ("second unique", "second other"))
    export_root = tmp_path / "export-root"
    export_root.mkdir()
    export = _publish(export_root, (first, second))
    output = tmp_path / "library-viewer.html"

    result = _run(export, output)
    assert result.returncode == 0
    assert result.stderr == ""

    harness_result = _run_dom_harness(output.read_text(encoding="utf-8"))

    assert harness_result.returncode == 0, harness_result.stderr
    assert harness_result.stderr == ""
    assert harness_result.stdout == "compiled_library_viewer_dom=passed\n"
