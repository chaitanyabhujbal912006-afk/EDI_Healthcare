"""
Batch validation — process multiple EDI files or strings in a single call.

Usage::

    from validedi import batch_validate

    results = batch_validate(["file1.edi", "file2.edi", raw_edi_string])

    for item in results:
        if item["error"]:
            print(f"{item['source']} failed to parse: {item['error']}")
        else:
            vr = item["result"]
            print(vr.summary())
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from validedi.engine.validator import validate
from validedi.engine.models import ValidationResult


# ── Public API ──────────────────────────────────────────────────────────────


def batch_validate(
    sources: list[str | Path],
    *,
    max_workers: int | None = None,
    fail_fast: bool = False,
) -> list[dict[str, Any]]:
    """
    Validate a collection of EDI files or raw strings concurrently.

    Each source is processed in its own thread.  Results are returned in
    the **same order** as the input list regardless of completion order.

    Args:
        sources: A list of file paths (``str`` / :class:`pathlib.Path`) or
            raw EDI strings to validate.
        max_workers: Maximum number of threads.  Defaults to
            ``min(32, cpu_count + 4)`` (Python's :class:`~concurrent.futures.ThreadPoolExecutor`
            default).
        fail_fast: When *True*, raise the first exception encountered
            instead of capturing it in the result dict.  Defaults to
            *False*.

    Returns:
        A list of result dicts in input order, each with keys:

        - ``"source"`` (*str*) — a short label derived from the input
          (filename basename or first 40 chars of raw EDI).
        - ``"result"`` (:class:`~validedi.engine.models.ValidationResult`
          | *None*) — populated on success, *None* on failure.
        - ``"error"`` (*str* | *None*) — error message on failure, *None*
          on success.

    Raises:
        Exception: The first parse/validation exception encountered, only
            when ``fail_fast=True``.

    Example::

        results = batch_validate(["a.edi", "b.edi"])
        valid   = [r for r in results if r["result"] and r["result"].is_valid]
        invalid = [r for r in results if r["error"] or
                   (r["result"] and not r["result"].is_valid)]
    """
    if not sources:
        return []

    # Pre-build ordered result list so we can fill by index later
    output: list[dict[str, Any]] = [
        {"source": _label(src), "result": None, "error": None}
        for src in sources
    ]

    def _run(index: int, src: str | Path) -> tuple[int, ValidationResult | None, str | None]:
        try:
            return index, validate(src), None
        except Exception as exc:
            if fail_fast:
                raise
            return index, None, str(exc)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_run, i, src): i for i, src in enumerate(sources)}
        for future in as_completed(futures):
            idx, result, error = future.result()
            output[idx]["result"] = result
            output[idx]["error"] = error

    return output


# ── Helpers ─────────────────────────────────────────────────────────────────


def _label(source: str | Path) -> str:
    """Return a short human-readable label for a source."""
    if isinstance(source, Path):
        return source.name
    if os.path.sep in source or "/" in source:
        return os.path.basename(source)
    # Raw EDI string
    preview = source.strip()[:40]
    return preview + ("…" if len(source.strip()) > 40 else "")
