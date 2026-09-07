"""Domain model for an interactive troubleshooting walkthrough.

A TroubleshootingSession tracks the user's progress through Sherlock's
recommendations without changing the investigation itself. The
Investigation owns the session; this model owns the step-by-step state
transition rules.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class StepResult(str, Enum):
    """How the user answered a troubleshooting step."""

    DONE = "done"
    COULD_NOT_COMPLETE = "could_not_complete"


class SessionStatus(str, Enum):
    """Lifecycle state of a troubleshooting session."""

    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    EXHAUSTED = "exhausted"


@dataclass
class StepAnswer:
    """A recorded answer for one troubleshooting step."""

    recommendation_index: int
    step_index: int
    result: StepResult
    answered_at: datetime


@dataclass
class TroubleshootingSession:
    """Tracks progress through an investigation report's recommendations.

    Intermediate steps always advance regardless of whether the user
    completed them. Only the final verification step determines whether
    the recommendation resolved the problem or Sherlock should move to
    the next recommendation.
    """

    case_id: str
    status: SessionStatus
    current_recommendation_index: int
    current_step_index: int
    answers: list[StepAnswer] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def start(
        cls,
        case_id: str,
        recommendation_index: int,
    ) -> "TroubleshootingSession":
        """Create a new troubleshooting session at the first step."""

        now = datetime.now(timezone.utc)

        return cls(
            case_id=case_id,
            status=SessionStatus.IN_PROGRESS,
            current_recommendation_index=recommendation_index,
            current_step_index=0,
            started_at=now,
            updated_at=now,
        )

    def record_step_answer(
        self,
        result: StepResult,
        *,
        is_final_step: bool,
        has_next_recommendation: bool,
    ) -> None:
        """Record the user's answer and transition the session.

        Rules:

        - Intermediate steps always advance, regardless of the answer.
        - A successful final step resolves the session.
        - An unsuccessful final step moves to the next recommendation
          when one exists.
        - If the unsuccessful final step belongs to the last available
          recommendation, the session becomes exhausted.
        """

        if self.status is not SessionStatus.IN_PROGRESS:
            raise ValueError(
                f"Cannot answer a step when troubleshooting session is "
                f"{self.status.value}."
            )

        now = datetime.now(timezone.utc)

        self.answers.append(
            StepAnswer(
                recommendation_index=self.current_recommendation_index,
                step_index=self.current_step_index,
                result=result,
                answered_at=now,
            )
        )

        if not is_final_step:
            self.current_step_index += 1

        elif result is StepResult.DONE:
            self.status = SessionStatus.RESOLVED

        elif has_next_recommendation:
            self.current_recommendation_index += 1
            self.current_step_index = 0

        else:
            self.status = SessionStatus.EXHAUSTED

        self.updated_at = now