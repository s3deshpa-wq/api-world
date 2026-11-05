"""
Meeting rooms: create a meeting, let people join (max 50), no time limit.

This is the *control plane* of a Zoom-like app -- who is allowed in, when the
meeting starts and ends, and where the transcript goes. It does not move any
audio or video. In a real deployment the media (WebRTC audio/video) is handled
by an SFU such as LiveKit, mediasoup or Jitsi; this class decides who gets a
token to join that SFU room. See meeting_app/README.md for the full picture.

Stdlib only, in-memory. Swap the dicts for a database when you build it out.
"""

from __future__ import annotations

import secrets
import string
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Optional

MAX_PARTICIPANTS = 50


class MeetingError(Exception):
    """Base class for meeting errors."""


class MeetingFullError(MeetingError):
    pass


class MeetingNotFoundError(MeetingError):
    pass


class InvalidPasscodeError(MeetingError):
    pass


class MeetingEndedError(MeetingError):
    pass


class MeetingStatus(str, Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    ENDED = "ended"


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Participant:
    participant_id: str
    name: str
    joined_at: datetime
    is_host: bool = False
    left_at: Optional[datetime] = None


@dataclass
class TranscriptSegment:
    """One utterance from the speech-to-text engine."""

    speaker: str
    text: str
    start_seconds: float  # offset from meeting start
    language: str = "unknown"  # e.g. "hi", "en", "hi-en" (code-mixed)


@dataclass
class Meeting:
    meeting_id: str
    title: str
    host_name: str
    passcode: str
    created_at: datetime
    max_participants: int = MAX_PARTICIPANTS
    status: MeetingStatus = MeetingStatus.SCHEDULED
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    # Note: deliberately no "duration_limit" -- meetings run until the host ends them.
    participants: dict[str, Participant] = field(default_factory=dict)
    transcript: list[TranscriptSegment] = field(default_factory=list)

    @property
    def active_participants(self) -> list[Participant]:
        return [p for p in self.participants.values() if p.left_at is None]

    @property
    def join_link(self) -> str:
        return f"https://meet.example.com/j/{self.meeting_id}?pwd={self.passcode}"


def _new_meeting_id() -> str:
    # Zoom-style 11 digit number, formatted 3-4-4 for display.
    return "".join(secrets.choice(string.digits) for _ in range(11))


def _new_passcode() -> str:
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(6))


class MeetingManager:
    """Creates meetings and enforces join rules. Thread-safe."""

    def __init__(self, max_participants: int = MAX_PARTICIPANTS):
        self.max_participants = max_participants
        self._meetings: dict[str, Meeting] = {}
        self._lock = threading.Lock()
        # Hooks so a note taker can subscribe to transcript / end events.
        self._on_segment: list[Callable[[Meeting, TranscriptSegment], None]] = []
        self._on_end: list[Callable[[Meeting], None]] = []

    # --- lifecycle -------------------------------------------------------

    def create_meeting(self, title: str, host_name: str) -> Meeting:
        with self._lock:
            meeting_id = _new_meeting_id()
            while meeting_id in self._meetings:
                meeting_id = _new_meeting_id()
            meeting = Meeting(
                meeting_id=meeting_id,
                title=title,
                host_name=host_name,
                passcode=_new_passcode(),
                created_at=_now(),
                max_participants=self.max_participants,
            )
            self._meetings[meeting_id] = meeting
            return meeting

    def get(self, meeting_id: str) -> Meeting:
        try:
            return self._meetings[meeting_id]
        except KeyError:
            raise MeetingNotFoundError(meeting_id) from None

    def join(self, meeting_id: str, name: str, passcode: str) -> Participant:
        """Admit a participant. Raises MeetingFullError at the 51st person."""
        with self._lock:
            meeting = self.get(meeting_id)
            if meeting.status is MeetingStatus.ENDED:
                raise MeetingEndedError(meeting_id)
            if not secrets.compare_digest(passcode, meeting.passcode):
                raise InvalidPasscodeError(meeting_id)
            if len(meeting.active_participants) >= meeting.max_participants:
                raise MeetingFullError(
                    f"Meeting {meeting_id} already has {meeting.max_participants} participants"
                )
            if meeting.status is MeetingStatus.SCHEDULED:
                meeting.status = MeetingStatus.LIVE
                meeting.started_at = _now()
            participant = Participant(
                participant_id=secrets.token_hex(8),
                name=name,
                joined_at=_now(),
                is_host=(name == meeting.host_name and not any(p.is_host for p in meeting.active_participants)),
            )
            meeting.participants[participant.participant_id] = participant
            return participant

    def leave(self, meeting_id: str, participant_id: str) -> None:
        with self._lock:
            meeting = self.get(meeting_id)
            participant = meeting.participants.get(participant_id)
            if participant and participant.left_at is None:
                participant.left_at = _now()

    def end_meeting(self, meeting_id: str) -> Meeting:
        """End the meeting (host action). Fires on_end hooks -> final summary."""
        with self._lock:
            meeting = self.get(meeting_id)
            if meeting.status is MeetingStatus.ENDED:
                return meeting
            meeting.status = MeetingStatus.ENDED
            meeting.ended_at = _now()
            for p in meeting.active_participants:
                p.left_at = meeting.ended_at
        for hook in self._on_end:
            hook(meeting)
        return meeting

    # --- transcript ------------------------------------------------------

    def add_transcript_segment(self, meeting_id: str, segment: TranscriptSegment) -> None:
        """Called by the speech-to-text pipeline for every finalized utterance."""
        meeting = self.get(meeting_id)
        if meeting.status is not MeetingStatus.LIVE:
            raise MeetingError(f"Meeting {meeting_id} is not live")
        meeting.transcript.append(segment)
        for hook in self._on_segment:
            hook(meeting, segment)

    def on_segment(self, hook: Callable[[Meeting, TranscriptSegment], None]) -> None:
        self._on_segment.append(hook)

    def on_end(self, hook: Callable[[Meeting], None]) -> None:
        self._on_end.append(hook)
