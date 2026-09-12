from __future__ import annotations

from typing import Protocol

from civiclens.modules.analysis.schemas import InterpretationEnvelope, InterpretationRequest


class AIInterpreter(Protocol):
    """Narrow port: the model may structure evidence and nothing else."""

    def interpret(self, request: InterpretationRequest) -> InterpretationEnvelope: ...
