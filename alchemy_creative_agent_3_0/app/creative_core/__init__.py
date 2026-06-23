"""V3 Creative Core orchestration package."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .central_brain import CentralCreativeBrain
    from .pipeline import run_creative_planning, run_generation_loop

__all__ = ["CentralCreativeBrain", "run_creative_planning", "run_generation_loop"]


def __getattr__(name: str):
    if name == "CentralCreativeBrain":
        from .central_brain import CentralCreativeBrain

        return CentralCreativeBrain
    if name in {"run_creative_planning", "run_generation_loop"}:
        from . import pipeline

        return getattr(pipeline, name)
    raise AttributeError(name)
