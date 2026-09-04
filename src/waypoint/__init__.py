"""Waypoint - a hands-free dispatch copilot for delivery drivers.

The public surface is deliberately small. The two ideas worth importing are
the turn fence and the heard-not-said tracker; everything else is wiring.
"""

from .fencing import (
    Disposition,
    FenceDecision,
    FenceRecord,
    ReanchorPolicy,
    ToolTicket,
    TurnFence,
)
from .heard import HeardResult, HeardTracker, Method, WordMark

__version__ = "1.0.0"

__all__ = [
    "TurnFence",
    "ToolTicket",
    "FenceDecision",
    "FenceRecord",
    "Disposition",
    "ReanchorPolicy",
    "HeardTracker",
    "HeardResult",
    "WordMark",
    "Method",
    "__version__",
]
