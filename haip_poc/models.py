"""Pydantic models for interview scenario definitions."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Trigger definitions (discriminated union, extensible)
# ---------------------------------------------------------------------------


class TimeTrigger(BaseModel):
    """Fire after a fixed delay."""

    type: Literal["time"] = "time"
    delay_seconds: int = Field(..., gt=0, description="Seconds to wait before triggering")


# Add new trigger types here and include them in the union below.
Trigger = TimeTrigger


# ---------------------------------------------------------------------------
# Question / follow-up
# ---------------------------------------------------------------------------


class FollowUp(BaseModel):
    id: str
    text: str


class Question(BaseModel):
    id: str
    text: str
    listen_seconds: int = Field(default=30, gt=0, description="Max seconds to listen for answer")
    follow_ups: list[FollowUp] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Voice configuration
# ---------------------------------------------------------------------------


class VoiceConfig(BaseModel):
    language_code: str = "en-US"
    name: str = "en-US-Neural2-D"


# ---------------------------------------------------------------------------
# Top-level scenario
# ---------------------------------------------------------------------------


class Scenario(BaseModel):
    name: str
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    trigger: Trigger
    questions: list[Question] = Field(..., min_length=1)
