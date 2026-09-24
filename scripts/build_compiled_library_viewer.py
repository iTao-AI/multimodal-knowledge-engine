#!/usr/bin/env python3
"""Build a self-contained, read-only HTML viewer for a v2 Library export."""

# The embedded HTML is kept readable as a single self-contained template.
# ruff: noqa: E501

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path
from typing import NamedTuple, cast

# The public entry point is also useful when imported from the repository root
# in a test or a small local automation, where Python does not put scripts/ on
# sys.path automatically.
_SCRIPT_DIRECTORY = str(Path(__file__).resolve().parent)
if _SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, _SCRIPT_DIRECTORY)

from compiled_library_export_consumer_v2 import (  # noqa: E402
    ValidatedExport,
    ValidationError,
    load_validated_export,
)

_VIEWER_SCHEMA = "mke.compiled_library_viewer.v1"
_MAX_SOURCES = 64
_MAX_EVIDENCE = 2_000
_MAX_EVIDENCE_UTF8_BYTES = 8 * 1024 * 1024
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


class ViewerError(Exception):
    """A public-safe viewer build failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ViewerBuildResult(NamedTuple):
    source_count: int
    evidence_count: int


_HTML_TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>资料与引用 · Compiled Library Export v2</title>
  <style>
    :root {
      color-scheme: light;
      --paper: #f7f3eb;
      --paper-strong: #fffdf8;
      --ink: #18302e;
      --muted: #61716d;
      --line: #d8ddd6;
      --teal: #0d6961;
      --teal-dark: #084d49;
      --teal-soft: #e1efeb;
      --warn: #8a5c28;
      --shadow: 0 18px 50px rgba(24, 48, 46, .08);
    }
    *, *::before, *::after { box-sizing: border-box; }
    html { min-width: 0; background: var(--paper); }
    body {
      min-width: 0;
      margin: 0;
      overflow-x: hidden;
      background: var(--paper);
      color: var(--ink);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.55;
    }
    button, input, textarea { font: inherit; }
    button { cursor: pointer; }
    :focus-visible { outline: 3px solid rgba(13, 105, 97, .35); outline-offset: 3px; }
    .shell { width: min(1440px, 100%); margin: 0 auto; padding: 36px clamp(18px, 4vw, 64px) 56px; }
    .hero { display: flex; align-items: flex-start; justify-content: space-between; gap: 28px; margin-bottom: 28px; }
    .eyebrow { margin: 0 0 8px; color: var(--teal); font-size: .78rem; font-weight: 750; letter-spacing: .12em; text-transform: uppercase; }
    h1, h2, h3, p { margin-top: 0; }
    h1 { margin-bottom: 8px; font-family: Georgia, "Times New Roman", serif; font-size: clamp(2.25rem, 5vw, 4.2rem); font-weight: 600; letter-spacing: -.045em; line-height: 1.02; }
    .subtitle { max-width: 660px; margin-bottom: 0; color: var(--muted); font-size: 1.05rem; }
    .snapshot-status { min-width: 220px; padding: 16px 18px; border: 1px solid var(--line); border-radius: 14px; background: rgba(255, 253, 248, .76); box-shadow: var(--shadow); }
    .status-line { display: flex; align-items: center; gap: 9px; font-weight: 750; }
    .status-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--teal); box-shadow: 0 0 0 4px var(--teal-soft); }
    .snapshot-summary { display: block; margin-top: 5px; color: var(--muted); font-size: .88rem; }
    .toolbar { margin-bottom: 24px; padding: 18px; border: 1px solid var(--line); border-radius: 14px; background: var(--paper-strong); }
    .toolbar label { display: block; margin-bottom: 8px; font-weight: 750; }
    .filter-row { display: flex; gap: 10px; min-width: 0; }
    .filter-row input { min-width: 0; flex: 1; border: 1px solid #bdc9c4; border-radius: 9px; padding: 11px 13px; background: #fff; color: var(--ink); }
    .filter-row button, .copy-button { border: 1px solid var(--teal); border-radius: 9px; padding: 10px 13px; background: var(--teal); color: white; font-weight: 700; }
    .filter-row button { background: transparent; color: var(--teal-dark); }
    .filter-summary { min-height: 1.5em; margin: 8px 0 0; color: var(--muted); font-size: .88rem; }
    .layout { display: grid; grid-template-columns: minmax(220px, 280px) minmax(0, 1fr); align-items: start; gap: 24px; }
    .source-nav, .reader { min-width: 0; border: 1px solid var(--line); border-radius: 14px; background: var(--paper-strong); box-shadow: var(--shadow); }
    .source-nav { position: sticky; top: 20px; padding: 16px; }
    .section-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
    .section-heading h2 { margin-bottom: 0; font-size: 1rem; }
    .count { color: var(--muted); font-size: .8rem; }
    .source-list { display: grid; gap: 8px; }
    .source-option { width: 100%; min-width: 0; border: 1px solid transparent; border-radius: 10px; padding: 12px; background: transparent; color: var(--ink); text-align: left; }
    .source-option:hover { border-color: var(--line); background: #fbfaf5; }
    .source-option[aria-pressed="true"] { border-color: #9dc8c1; background: var(--teal-soft); }
    .source-name { display: block; overflow-wrap: anywhere; font-weight: 750; }
    .source-meta { display: block; margin-top: 4px; color: var(--muted); font-size: .8rem; }
    .reader { padding: clamp(18px, 3vw, 34px); }
    .reader-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 22px; padding-bottom: 18px; border-bottom: 1px solid var(--line); }
    .reader-header h2 { margin-bottom: 5px; overflow-wrap: anywhere; font-family: Georgia, "Times New Roman", serif; font-size: clamp(1.65rem, 3vw, 2.5rem); line-height: 1.1; }
    .reader-meta, .record-count { color: var(--muted); font-size: .9rem; }
    .record-count { flex: 0 0 auto; padding-top: 5px; text-align: right; }
    .evidence-list { display: grid; gap: 16px; }
    .evidence-card { min-width: 0; scroll-margin-top: 20px; border: 1px solid var(--line); border-radius: 12px; padding: 18px; background: #fffefa; }
    .record-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 14px; margin-bottom: 11px; }
    .record-heading h3 { margin-bottom: 0; font-size: 1rem; }
    .anchor-link { color: var(--teal); font-size: .82rem; white-space: nowrap; }
    .evidence-text { margin: 0 0 16px; overflow-wrap: anywhere; white-space: pre-wrap; word-break: break-word; }
    .record-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
    .copy-status { min-height: 1.5em; color: var(--muted); font-size: .84rem; }
    .copy-status.success { color: var(--teal-dark); font-weight: 700; }
    .copy-status.fallback { color: var(--warn); font-weight: 700; }
    .citation-details { margin-top: 15px; border-top: 1px solid var(--line); padding-top: 12px; }
    .citation-details summary { color: var(--teal-dark); cursor: pointer; font-weight: 700; }
    .citation-grid { display: grid; grid-template-columns: minmax(120px, max-content) minmax(0, 1fr); gap: 5px 14px; margin: 12px 0 0; font-size: .82rem; }
    .citation-grid dt { color: var(--muted); }
    .citation-grid dd { min-width: 0; margin: 0; overflow-wrap: anywhere; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    .copy-fallback { margin-top: 12px; }
    .copy-fallback textarea { display: block; width: 100%; min-height: 130px; resize: vertical; border: 1px solid #c7b98c; border-radius: 8px; padding: 10px; background: #fffdf2; color: var(--ink); white-space: pre-wrap; }
    .copy-hint { margin: 7px 0 0; color: var(--warn); font-size: .84rem; }
    .empty-state { padding: 32px 10px; color: var(--muted); text-align: center; }
    .no-match { margin: 10px 0 0; color: var(--muted); font-size: .88rem; }
    @media (max-width: 760px) {
      .shell { padding-top: 24px; }
      .hero { display: block; }
      .snapshot-status { min-width: 0; margin-top: 18px; }
      .layout { grid-template-columns: minmax(0, 1fr); }
      .source-nav { position: static; }
      .reader-header { display: block; }
      .record-count { padding-top: 0; text-align: left; }
      .citation-grid { grid-template-columns: 1fr; gap: 2px; }
      .citation-grid dd { margin-bottom: 7px; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header class="hero">
      <div>
        <p class="eyebrow">Compiled Library Export v2</p>
        <h1>资料与引用</h1>
        <p class="subtitle">浏览本次导出的资料，沿页码或时间戳核对证据。</p>
      </div>
      <div class="snapshot-status" aria-label="导出快照状态">
        <div class="status-line"><span class="status-dot" aria-hidden="true"></span><span>导出快照</span></div>
        <span class="snapshot-summary" id="snapshot-summary"></span>
      </div>
    </header>

    <section class="toolbar" aria-label="筛选导出内容">
      <label for="filter-input">筛选导出内容</label>
      <div class="filter-row">
        <input id="filter-input" type="search" autocomplete="off" spellcheck="false" placeholder="按资料名称或 Evidence 文本筛选" aria-describedby="filter-summary">
        <button id="clear-filter" type="button" hidden>清空</button>
      </div>
      <p class="filter-summary" id="filter-summary" aria-live="polite"></p>
    </section>

    <main class="layout">
      <aside class="source-nav" aria-label="资料列表">
        <div class="section-heading"><h2>资料</h2><span class="count" id="source-count"></span></div>
        <div class="source-list" id="source-list"></div>
      </aside>
      <section class="reader" aria-label="证据阅读区">
        <div id="reader-content"></div>
      </section>
    </main>
  </div>

  <script type="application/json" id="viewer-data">__VIEWER_DATA__</script>
  <script>
    (() => {
      "use strict";
      const data = JSON.parse(document.getElementById("viewer-data").textContent);
      const filterInput = document.getElementById("filter-input");
      const clearFilter = document.getElementById("clear-filter");
      const filterSummary = document.getElementById("filter-summary");
      const sourceCount = document.getElementById("source-count");
      const sourceList = document.getElementById("source-list");
      const readerContent = document.getElementById("reader-content");
      const snapshotSummary = document.getElementById("snapshot-summary");
      const state = { selectedSourceId: data.sources.length ? data.sources[0].source_id : null, query: "" };
      const totalEvidence = data.sources.reduce((sum, source) => sum + source.evidence.length, 0);

      const node = (tag, className, value) => {
        const result = document.createElement(tag);
        if (className) result.className = className;
        if (value !== undefined) result.textContent = String(value);
        return result;
      };

      const mediaLabels = {
        "application/pdf": "PDF 文档",
        "video/mp4": "MP4 视频",
        "audio/mpeg": "MP3 音频",
        "audio/wav": "WAV 音频",
        "audio/mp4": "M4A 音频"
      };

      const formatMilliseconds = (value) => {
        const milliseconds = Number(value);
        const hours = Math.floor(milliseconds / 3600000);
        const minutes = Math.floor((milliseconds % 3600000) / 60000);
        const seconds = Math.floor((milliseconds % 60000) / 1000);
        const remainder = milliseconds % 1000;
        const prefix = hours ? `${String(hours).padStart(2, "0")}:` : "";
        return `${prefix}${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}.${String(remainder).padStart(3, "0")}`;
      };

      const locatorLabel = (locator) => locator.kind === "page"
        ? `第 ${locator.start} 页`
        : `时间 ${formatMilliseconds(locator.start)} – ${formatMilliseconds(locator.end)}`;

      const citationFor = (source, evidence) => [
        evidence.text,
        "",
        `资料：${source.display_name}`,
        `定位：${locatorLabel(evidence.locator)}`,
        `content_fingerprint：${evidence.content_fingerprint}`,
        `source_id：${evidence.source_id}`,
        `publication_id：${evidence.publication_id}`,
        `publication_revision：${evidence.publication_revision}`,
        `run_id：${evidence.run_id}`,
        `evidence_id：${evidence.evidence_id}`
      ].join("\n");

      const matchingSources = () => {
        const query = state.query.trim().toLocaleLowerCase();
        if (!query) return data.sources.map((source) => ({ source, evidence: source.evidence }));
        return data.sources.map((source) => {
          const nameMatches = source.display_name.toLocaleLowerCase().includes(query);
          const evidence = nameMatches
            ? source.evidence
            : source.evidence.filter((item) => item.text.toLocaleLowerCase().includes(query));
          return { source, evidence };
        }).filter((item) => item.evidence.length);
      };

      const evidenceForFragment = () => {
        const rawFragment = window.location.hash || "";
        if (!rawFragment.startsWith("#") || rawFragment.length < 2) return null;
        let targetId;
        try {
          targetId = decodeURIComponent(rawFragment.slice(1));
        } catch (_error) {
          return null;
        }
        for (const source of data.sources) {
          const evidence = source.evidence.find((item) => `evidence-${item.evidence_id}` === targetId);
          if (evidence) return { source, evidence };
        }
        return null;
      };

      const clearFragmentIfHidden = (fragment) => {
        if (!fragment || !window.history || typeof window.history.replaceState !== "function") return;
        const replacement = `${window.location.pathname || ""}${window.location.search || ""}`;
        try {
          window.history.replaceState(null, "", replacement);
        } catch (_error) {
          // A restricted document URL must not make ordinary rendering fail.
        }
      };

      const renderFallback = (card, citation, status) => {
        card.querySelectorAll(".copy-fallback").forEach((item) => item.remove());
        const wrapper = node("div", "copy-fallback");
        const textarea = node("textarea", null);
        textarea.value = citation;
        textarea.rows = 7;
        textarea.setAttribute("aria-label", "可选择的引用文本");
        const hint = node("p", "copy-hint", "浏览器未允许自动复制，请选择上方文本后按 ⌘/Ctrl+C。");
        wrapper.append(textarea, hint);
        card.querySelector(".record-actions").after(wrapper);
        status.className = "copy-status fallback";
        status.textContent = "请完成选择并复制";
        textarea.focus();
        textarea.select();
      };

      const addCitationDetails = (card, source, evidence) => {
        const details = node("details", "citation-details");
        const summary = node("summary", null, "引用详情");
        const grid = node("dl", "citation-grid");
        const fields = [
          ["content_fingerprint", evidence.content_fingerprint],
          ["source_id", evidence.source_id],
          ["publication_id", evidence.publication_id],
          ["publication_revision", evidence.publication_revision],
          ["run_id", evidence.run_id],
          ["evidence_id", evidence.evidence_id]
        ];
        fields.forEach(([label, value]) => {
          grid.append(node("dt", null, label), node("dd", null, value));
        });
        details.append(summary, grid);
        card.append(details);
      };

      const renderEvidence = (source, evidence) => {
        const card = node("article", "evidence-card");
        card.id = `evidence-${evidence.evidence_id}`;
        const heading = node("div", "record-heading");
        heading.append(node("h3", null, locatorLabel(evidence.locator)));
        const anchor = node("a", "anchor-link", "本地锚点");
        anchor.href = `#${card.id}`;
        anchor.setAttribute("aria-label", `${locatorLabel(evidence.locator)}本地锚点`);
        heading.append(anchor);
        const text = node("p", "evidence-text", evidence.text);
        const actions = node("div", "record-actions");
        const copy = node("button", "copy-button", "复制引用");
        copy.type = "button";
        const status = node("span", "copy-status");
        status.setAttribute("aria-live", "polite");
        copy.addEventListener("click", async () => {
          const citation = citationFor(source, evidence);
          try {
            if (!navigator.clipboard || typeof navigator.clipboard.writeText !== "function") throw new Error("clipboard unavailable");
            await navigator.clipboard.writeText(citation);
            status.className = "copy-status success";
            status.textContent = "已复制引用";
          } catch (_error) {
            renderFallback(card, citation, status);
          }
        });
        actions.append(copy, status);
        card.append(heading, text, actions);
        addCitationDetails(card, source, evidence);
        return card;
      };

      const renderSources = (matches, selected, focusSourceId) => {
        sourceList.replaceChildren();
        if (!matches.length) {
          sourceList.append(node("p", "no-match", "未找到匹配的资料或证据。"));
          return null;
        }
        let focusTarget = null;
        matches.forEach(({ source, evidence }) => {
          const button = node("button", "source-option");
          button.type = "button";
          button.dataset.sourceId = source.source_id;
          button.setAttribute("aria-pressed", String(source.source_id === selected.source_id));
          button.setAttribute("aria-label", `选择资料 ${source.display_name}`);
          const name = node("span", "source-name", source.display_name);
          const count = evidence.length === source.evidence.length
            ? `${source.evidence.length} 条 Evidence`
            : `${evidence.length}/${source.evidence.length} 条 Evidence`;
          const meta = node("span", "source-meta", `${mediaLabels[source.media_type] || source.media_type} · ${count}`);
          button.append(name, meta);
          button.addEventListener("click", () => {
            state.selectedSourceId = source.source_id;
            render({ focusSourceId: source.source_id });
          });
          sourceList.append(button);
          if (source.source_id === focusSourceId) focusTarget = button;
        });
        return focusTarget;
      };

      const renderReader = (matches, selected) => {
        readerContent.replaceChildren();
        if (!selected) {
          readerContent.append(node("div", "empty-state", "未找到匹配的资料或证据。"));
          return;
        }
        const header = node("div", "reader-header");
        const title = node("div");
        title.append(node("h2", null, selected.display_name));
        title.append(node("p", "reader-meta", `${mediaLabels[selected.media_type] || selected.media_type} · Publication revision ${selected.publication_revision}`));
        const selectedEvidence = matches.find((item) => item.source.source_id === selected.source_id).evidence;
        header.append(title, node("div", "record-count", `${selectedEvidence.length}/${selected.evidence.length} 条 Evidence`));
        const list = node("div", "evidence-list");
        selectedEvidence.forEach((evidence) => list.append(renderEvidence(selected, evidence)));
        readerContent.append(header, list);
      };

      const render = ({ fragment = null, focusSourceId = null } = {}) => {
        let matches = matchingSources();
        if (fragment) {
          const targetVisible = matches.some(({ source, evidence }) =>
            source.source_id === fragment.source.source_id
              && evidence.some((item) => item.evidence_id === fragment.evidence.evidence_id)
          );
          if (!targetVisible) {
            state.query = "";
            filterInput.value = "";
            matches = matchingSources();
          }
        }
        const selectedMatch = fragment
          ? matches.find((item) => item.source.source_id === fragment.source.source_id) || null
          : matches.find((item) => item.source.source_id === state.selectedSourceId) || matches[0] || null;
        state.selectedSourceId = selectedMatch ? selectedMatch.source.source_id : null;
        const visibleEvidence = matches.reduce((sum, item) => sum + item.evidence.length, 0);
        sourceCount.textContent = `${matches.length}/${data.sources.length} 个资料`;
        filterSummary.textContent = state.query.trim()
          ? `显示 ${visibleEvidence}/${totalEvidence} 条 Evidence，${matches.length}/${data.sources.length} 个资料`
          : `共 ${totalEvidence} 条 Evidence`;
        clearFilter.hidden = !state.query;
        const focusTarget = renderSources(matches, selectedMatch ? selectedMatch.source : null, focusSourceId);
        renderReader(matches, selectedMatch ? selectedMatch.source : null);
        if (focusTarget) focusTarget.focus();
        if (fragment) {
          const target = document.getElementById(`evidence-${fragment.evidence.evidence_id}`);
          if (target) requestAnimationFrame(() => target.scrollIntoView({ block: "start" }));
        } else {
          const currentFragment = evidenceForFragment();
          const target = currentFragment
            ? document.getElementById(`evidence-${currentFragment.evidence.evidence_id}`)
            : null;
          if (currentFragment && !target) clearFragmentIfHidden(currentFragment);
        }
      };

      snapshotSummary.textContent = `${data.source_count} 个资料 · ${data.evidence_count} 条 Evidence`;
      filterInput.addEventListener("input", (event) => {
        state.query = event.target.value;
        render();
      });
      clearFilter.addEventListener("click", () => {
        filterInput.value = "";
        state.query = "";
        filterInput.focus();
        render();
      });
      window.addEventListener("hashchange", () => render({ fragment: evidenceForFragment() }));
      render({ fragment: evidenceForFragment() });
    })();
  </script>
</body>
</html>
"""


def _load_snapshot(export: Path) -> ValidatedExport:
    try:
        return load_validated_export(export)
    except (OSError, ValueError, TypeError, ValidationError) as exc:
        raise ViewerError(
            "export_invalid",
            "a validated compiled Library Export v2 is required",
        ) from exc


def _check_budget(snapshot: ValidatedExport) -> tuple[int, int]:
    source_count = len(snapshot.sources)
    evidence_count = sum(len(source.evidence) for source in snapshot.sources)
    text_bytes = sum(
        len(cast(str, row["text"]).encode("utf-8"))
        for source in snapshot.sources
        for row in source.evidence
    )
    if source_count > _MAX_SOURCES:
        raise ViewerError(
            "viewer_budget_exceeded",
            "viewer budget exceeded: 64 Sources maximum",
        )
    if evidence_count > _MAX_EVIDENCE:
        raise ViewerError(
            "viewer_budget_exceeded",
            "viewer budget exceeded: 2,000 Evidence records maximum",
        )
    if text_bytes > _MAX_EVIDENCE_UTF8_BYTES:
        raise ViewerError(
            "viewer_budget_exceeded",
            "viewer budget exceeded: 8 MiB aggregate Evidence UTF-8 text maximum",
        )
    return source_count, evidence_count


def _viewer_data(
    snapshot: ValidatedExport, source_count: int, evidence_count: int
) -> dict[str, object]:
    sources: list[dict[str, object]] = []
    for validated_source in snapshot.sources:
        entry = validated_source.descriptor
        evidence: list[dict[str, object]] = []
        for row in validated_source.evidence:
            evidence.append(
                {
                    "schema_version": row["schema_version"],
                    "evidence_id": row["evidence_id"],
                    "source_id": row["source_id"],
                    "content_fingerprint": row["content_fingerprint"],
                    "publication_id": row["publication_id"],
                    "publication_revision": row["publication_revision"],
                    "run_id": row["run_id"],
                    "locator": row["locator"],
                    "text": row["text"],
                }
            )
        sources.append(
            {
                "source_id": entry["source_id"],
                "display_name": entry["display_name"],
                "content_fingerprint": entry["content_fingerprint"],
                "media_type": entry["media_type"],
                "publication_id": entry["publication_id"],
                "publication_revision": entry["publication_revision"],
                "run_id": entry["run_id"],
                "evidence": evidence,
            }
        )
    return {
        "schema_version": _VIEWER_SCHEMA,
        "export_schema": "mke.compiled_library_export.v2",
        "source_count": source_count,
        "evidence_count": evidence_count,
        "sources": sources,
    }


def _safe_json(value: object) -> str:
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    for source, replacement in (
        ("&", r"\u0026"),
        ("<", r"\u003c"),
        (">", r"\u003e"),
        ("\u2028", r"\u2028"),
        ("\u2029", r"\u2029"),
    ):
        serialized = serialized.replace(source, replacement)
    return serialized


def _render(snapshot: ValidatedExport, source_count: int, evidence_count: int) -> bytes:
    data = _safe_json(_viewer_data(snapshot, source_count, evidence_count))
    return _HTML_TEMPLATE.replace("__VIEWER_DATA__", data).encode("utf-8", errors="strict")


def _output_path(export: Path, output: Path) -> Path:
    try:
        os.lstat(output)
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise ViewerError("output_unavailable", "output path is unavailable") from exc
    else:
        raise ViewerError("output_exists", "output already exists")
    try:
        export_root = export.resolve(strict=False)
        output_root = output.resolve(strict=False)
    except OSError as exc:
        raise ViewerError("output_unavailable", "output path is unavailable") from exc
    try:
        output_root.relative_to(export_root)
    except ValueError:
        pass
    else:
        raise ViewerError("output_inside_export", "output must be outside the export directory")
    try:
        parent = os.stat(output_root.parent)
    except OSError as exc:
        raise ViewerError("output_unavailable", "output parent is unavailable") from exc
    if not stat.S_ISDIR(parent.st_mode):
        raise ViewerError("output_unavailable", "output parent is unavailable")
    return output_root


def _cleanup_created_output(path: Path, identity: tuple[int, int]) -> None:
    try:
        current = os.lstat(path)
        if (
            not stat.S_ISREG(current.st_mode)
            or (current.st_dev, current.st_ino) != identity
        ):
            raise OSError
        os.unlink(path)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise ViewerError("cleanup_failed", "viewer output cleanup failed") from exc


def _publish(path: Path, content: bytes) -> None:
    try:
        fd = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW,
            0o644,
        )
    except FileExistsError as exc:
        raise ViewerError("output_exists", "output already exists") from exc
    except OSError as exc:
        raise ViewerError("output_write_failed", "could not write viewer output") from exc
    identity = os.fstat(fd)
    closed = False
    try:
        view = memoryview(content)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("short write")
            view = view[written:]
        os.fsync(fd)
        os.close(fd)
        closed = True
    except OSError as exc:
        if not closed:
            try:
                os.close(fd)
            except OSError:
                pass
        _cleanup_created_output(path, (identity.st_dev, identity.st_ino))
        raise ViewerError("output_write_failed", "could not write viewer output") from exc


def build_viewer(export: Path, output: Path) -> ViewerBuildResult:
    output_path = _output_path(export, output)
    snapshot = _load_snapshot(export)
    source_count, evidence_count = _check_budget(snapshot)
    content = _render(snapshot, source_count, evidence_count)
    _publish(output_path, content)
    return ViewerBuildResult(source_count, evidence_count)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = build_viewer(args.export, args.output)
    except ViewerError as exc:
        print(f"compiled_library_viewer=failed code={exc.code} message={exc.message}")
        return 1
    print(
        "compiled_library_viewer=passed "
        f"source_count={result.source_count} evidence_count={result.evidence_count}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
