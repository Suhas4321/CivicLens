from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DemoSessionCreated(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    access_token: str
    actor_role: Literal["demo_officer"] = "demo_officer"
    expires_at: datetime
    disclosure: str = (
        "This isolated session may change only synthetic demo overlays; seed evidence is immutable."
    )
