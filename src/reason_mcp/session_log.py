"""Request session logger — writes one Markdown file per MCP request.

Activated via ``REASON_LOG_REQUESTS=1`` (or ``true`` / ``yes``).
Files are written to the directory configured via ``REASON_OUTPUT_DIR``
(defaults to ``./output`` relative to CWD, resolved to absolute path).

Filename format::

    <YYYYMMDDTHHMMSSZ>_<tool-slug>_<req-id-prefix>.md

    e.g.  20260310T142301Z_reasoning-analyze-context_a1b2c3d4.md

The Markdown document covers:
    1. Request parameters
    2. Every pipeline step (pruner, normaliser, semantic retrieval, compressor …)
    3. Decisions & rationale recorded during processing
    4. The full response payload returned to the host LLM
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class SessionLog:
    """Collects telemetry during a single MCP tool call and serialises it to Markdown.

    Usage::

        slog = SessionLog("reasoning_analyze_context", request_id, timestamp)
        slog.record_request({"observations": ..., "keywords": ...})
        slog.record_step("Path A — Deterministic", {"hits": [...], "count": 2})
        slog.record_decision("2 rules matched via keyword overlap; 1 additional via semantic.")
        slog.record_result(response_dict)
        path = slog.write(output_dir)   # → Path to written .md file
    """

    def __init__(self, tool_name: str, request_id: str, timestamp: str) -> None:
        self.tool_name = tool_name
        self.request_id = request_id
        self.timestamp = timestamp
        self._steps: list[dict[str, Any]] = []
        self._request_params: dict[str, Any] = {}
        self._decisions: list[str] = []
        self._result: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Collection API
    # ------------------------------------------------------------------

    def record_request(self, params: dict[str, Any]) -> None:
        """Store all input parameters for the incoming MCP request."""
        self._request_params = params

    def record_step(self, step_name: str, detail: Any) -> None:
        """Append a named pipeline step with arbitrary detail (dict, list, or string)."""
        self._steps.append({"step": step_name, "detail": detail})

    def record_decision(self, text: str) -> None:
        """Append a human-readable reasoning / decision note."""
        self._decisions.append(text)

    def record_result(self, result: dict[str, Any]) -> None:
        """Store the final response payload that is returned to the host LLM."""
        self._result = result

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write(self, output_dir: Path | str) -> Path:
        """Render and write the Markdown file; returns the path that was written."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        slug = self.tool_name.replace("_", "-")
        req_prefix = self.request_id[:8] if len(self.request_id) >= 8 else self.request_id
        filename = output_dir / f"{ts}_{slug}_{req_prefix}.md"

        filename.write_text(self._render(), encoding="utf-8")
        return filename

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self) -> str:
        lines: list[str] = []

        # ── Header ────────────────────────────────────────────────────
        lines += [
            f"# Session Log — `{self.tool_name}`",
            "",
            "| Field | Value |",
            "|---|---|",
            f"| **Request ID** | `{self.request_id}` |",
            f"| **Timestamp** | `{self.timestamp}` |",
            f"| **Tool** | `{self.tool_name}` |",
            f"| **Written** | `{datetime.now(timezone.utc).isoformat()}` |",
            "",
        ]

        # ── 1. Request Parameters ──────────────────────────────────────
        lines += [
            "---",
            "",
            "## 1. Request Parameters",
            "",
            "```json",
            json.dumps(self._request_params, indent=2, ensure_ascii=False, default=str),
            "```",
            "",
        ]

        # ── 2. Pipeline Steps ─────────────────────────────────────────
        lines += [
            "---",
            "",
            "## 2. Pipeline Steps",
            "",
        ]
        for i, s in enumerate(self._steps, 1):
            step_name = s["step"]
            detail = s["detail"]
            lines.append(f"### Step {i}: {step_name}")
            lines.append("")
            if isinstance(detail, (dict, list)):
                lines += [
                    "```json",
                    json.dumps(detail, indent=2, ensure_ascii=False, default=str),
                    "```",
                ]
            else:
                lines.append(str(detail))
            lines.append("")

        # ── 3. Decisions & Rationale ──────────────────────────────────
        lines += [
            "---",
            "",
            "## 3. Decisions & Rationale",
            "",
        ]
        if self._decisions:
            for dec in self._decisions:
                lines.append(f"- {dec}")
        else:
            lines.append("*(no decisions recorded)*")
        lines.append("")

        # ── 4. Result ─────────────────────────────────────────────────
        lines += [
            "---",
            "",
            "## 4. Result — Returned to Host LLM",
            "",
            "```json",
            json.dumps(self._result, indent=2, ensure_ascii=False, default=str),
            "```",
            "",
        ]

        return "\n".join(lines)
