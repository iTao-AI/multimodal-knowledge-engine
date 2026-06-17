"""Proof report DTOs and deterministic renderers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

ProofStatus = Literal["passed", "failed"]
ObservedValue = int | bool | str


@dataclass(frozen=True)
class ObservedField:
    key: str
    value: ObservedValue


@dataclass(frozen=True)
class ProofCaseResult:
    case: str
    status: ProofStatus
    summary: str
    observed: tuple[ObservedField, ...] = ()
    duration_ms: int = 0
    reason: str | None = None


@dataclass(frozen=True)
class ProofReport:
    proof: str
    results: tuple[ProofCaseResult, ...]
    duration_ms: int

    @property
    def cases(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for result in self.results if result.status == "passed")

    @property
    def failed(self) -> int:
        return sum(1 for result in self.results if result.status == "failed")

    @property
    def status(self) -> ProofStatus:
        return "failed" if self.failed else "passed"


def render_human_report(report: ProofReport) -> str:
    lines = [
        "mke proof run",
        (
            f"proof={report.proof} status={report.status} cases={report.cases} "
            f"passed={report.passed} failed={report.failed} "
            f"duration_ms={report.duration_ms}"
        ),
    ]
    for result in report.results:
        parts = [f"case={result.case}", f"status={result.status}"]
        if result.reason is not None:
            parts.append(f"reason={result.reason}")
        parts.extend(f"{field.key}={field.value}" for field in result.observed)
        lines.append(" ".join(parts))
    return "\n".join(lines)


def render_json_report(report: ProofReport) -> str:
    return json.dumps(_report_payload(report), indent=2, sort_keys=False)


def _report_payload(report: ProofReport) -> dict[str, object]:
    return {
        "proof": report.proof,
        "status": report.status,
        "cases": report.cases,
        "passed": report.passed,
        "failed": report.failed,
        "duration_ms": report.duration_ms,
        "results": [_case_payload(result) for result in report.results],
    }


def _case_payload(result: ProofCaseResult) -> dict[str, object]:
    payload: dict[str, object] = {
        "case": result.case,
        "status": result.status,
        "summary": result.summary,
        "observed": {field.key: field.value for field in result.observed},
        "duration_ms": result.duration_ms,
    }
    if result.reason is not None:
        payload["reason"] = result.reason
    return payload
