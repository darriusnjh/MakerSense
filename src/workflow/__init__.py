from __future__ import annotations

from .state import WorkflowState


def build_workflow(*args, **kwargs):
    # Lazy import avoids circular import during package initialization.
    from .graph import build_workflow as _build_workflow

    return _build_workflow(*args, **kwargs)


__all__ = ["build_workflow", "WorkflowState"]
