"""Per-run, per-thread stage events for live Colab diagnostics.

ContextVar isolation prevents accessory/avatar jobs from interleaving progress.
Event sinks are optional, and pipeline code remains usable without Gradio.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Callable, Iterator, Optional

_SINK: ContextVar[Optional[Callable[[str, str, str], None]]] = ContextVar(
    "vtuber_stage_sink", default=None
)


@contextmanager
def stage_reporter(
    callback: Callable[[str, str, str], None],
) -> Iterator[None]:
    token = _SINK.set(callback)
    try:
        yield
    finally:
        _SINK.reset(token)


def report_stage(name: str, status: str, detail: str = "") -> None:
    callback = _SINK.get()
    if callback is not None:
        callback(name, status, detail)


def current_reporter() -> Optional[Callable[[str, str, str], None]]:
    """Return the active sink for forwarding output from child reader threads."""
    return _SINK.get()
