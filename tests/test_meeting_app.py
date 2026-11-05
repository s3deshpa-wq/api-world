"""
Tests for meeting_app/ (meeting rules + note taker wiring). No network:
the Claude client is replaced with a fake.

Run:  pytest -v tests/test_meeting_app.py   (from the repo root)
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "meeting_app"))

from meetings import (  # noqa: E402
    InvalidPasscodeError,
    MeetingEndedError,
    MeetingFullError,
    MeetingManager,
    MeetingStatus,
    TranscriptSegment,
)
from note_taker import (  # noqa: E402
    ActionItem,
    Decision,
    MeetingNotes,
    NoteTaker,
    NoteTakerError,
    RunningNotes,
    attach_note_taker,
    render_markdown,
)


# --- meetings ---------------------------------------------------------------


def test_fifty_participants_allowed_fifty_first_rejected():
    mgr = MeetingManager()
    m = mgr.create_meeting("Standup", "Host")
    for i in range(50):
        mgr.join(m.meeting_id, f"P{i}", m.passcode)
    assert len(m.active_participants) == 50
    with pytest.raises(MeetingFullError):
        mgr.join(m.meeting_id, "P50", m.passcode)


def test_seat_frees_up_when_someone_leaves():
    mgr = MeetingManager(max_participants=2)
    m = mgr.create_meeting("Small", "A")
    a = mgr.join(m.meeting_id, "A", m.passcode)
    mgr.join(m.meeting_id, "B", m.passcode)
    mgr.leave(m.meeting_id, a.participant_id)
    mgr.join(m.meeting_id, "C", m.passcode)  # no error
    assert len(m.active_participants) == 2


def test_wrong_passcode_and_ended_meeting():
    mgr = MeetingManager()
    m = mgr.create_meeting("X", "Host")
    with pytest.raises(InvalidPasscodeError):
        mgr.join(m.meeting_id, "Eve", "wrong")
    mgr.join(m.meeting_id, "Host", m.passcode)
    assert m.status is MeetingStatus.LIVE
    mgr.end_meeting(m.meeting_id)
    with pytest.raises(MeetingEndedError):
        mgr.join(m.meeting_id, "Late", m.passcode)
    assert not m.active_participants


def test_no_time_limit_field():
    m = MeetingManager().create_meeting("Long", "Host")
    assert not any("duration" in f or "limit" in f for f in vars(m) if f != "max_participants")


# --- note taker -------------------------------------------------------------


EMPTY = RunningNotes(key_discussions=[], decisions=[], action_items=[], open_questions=[])


class FakeClient:
    """Mimics client.beta.messages.parse and records the prompts it was sent."""

    def __init__(self, outputs, stop_reason="end_turn"):
        self.outputs = list(outputs)
        self.calls = []
        self.stop_reason = stop_reason
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))

    def _parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(stop_reason=self.stop_reason, parsed_output=self.outputs.pop(0))


def seg(text, speaker="Priya", t=0.0):
    return TranscriptSegment(speaker=speaker, text=text, start_seconds=t)


def final_notes(**kw):
    base = dict(
        title="T", summary="S", languages_used=["Hindi", "English"],
        key_discussions=[], decisions=[], action_items=[], open_questions=[],
    )
    base.update(kw)
    return MeetingNotes(**base)


def test_live_notes_refresh_every_chunk():
    updated = EMPTY.model_copy(update={"open_questions": ["Launch date?"]})
    client = FakeClient([updated])
    nt = NoteTaker(client, chunk_words=5)
    assert nt.add_segment(seg("launch kab karna hai")) is False  # 4 words, buffered
    assert nt.add_segment(seg("15th ya 20th?")) is True  # crosses 5 words -> Claude call
    assert nt.notes.open_questions == ["Launch date?"]
    prompt = client.calls[0]["messages"][0]["content"]
    assert "launch kab karna hai" in prompt and "<running_notes>" in prompt
    assert client.calls[0]["output_format"] is RunningNotes


def test_finalize_uses_full_transcript_when_short():
    client = FakeClient([final_notes()])
    nt = NoteTaker(client, chunk_words=10_000)
    nt.add_segment(seg("पंद्रह तारीख थोड़ा मुश्किल है", speaker="Rahul", t=38))
    nt.finalize("Sync")
    prompt = client.calls[0]["messages"][0]["content"]
    assert "<transcript>" in prompt and "[00:00:38] Rahul: पंद्रह" in prompt


def test_finalize_falls_back_to_running_notes_when_long():
    client = FakeClient([EMPTY, final_notes()])
    nt = NoteTaker(client, chunk_words=10_000, full_transcript_word_limit=3)
    nt.add_segment(seg("one two three four"))
    nt.finalize("Long meeting")
    assert len(client.calls) == 2  # flush, then final
    assert "<running_notes>" in client.calls[1]["messages"][0]["content"]
    assert "<transcript>" not in client.calls[1]["messages"][0]["content"]


def test_finalize_empty_meeting_makes_no_api_call():
    client = FakeClient([])
    notes = NoteTaker(client).finalize("Silent")
    assert client.calls == [] and "No speech" in notes.summary


def test_refusal_raises():
    nt = NoteTaker(FakeClient([None], stop_reason="refusal"), chunk_words=1)
    with pytest.raises(NoteTakerError):
        nt.add_segment(seg("hello"))


def test_end_of_meeting_triggers_summary():
    client = FakeClient([final_notes(
        decisions=[Decision(decision="Launch on the 20th", made_by="Priya", context="Design needs a week")],
        action_items=[ActionItem(task="Sign Razorpay agreement", owner="Vikram", due="Friday")],
    )])
    mgr = MeetingManager()
    m = mgr.create_meeting("Sync", "Priya")
    mgr.join(m.meeting_id, "Priya", m.passcode)
    got = []
    attach_note_taker(mgr, m, NoteTaker(client, chunk_words=10_000), on_notes=lambda _m, n: got.append(n))
    mgr.add_transcript_segment(m.meeting_id, seg("Razorpay final karte hain"))
    mgr.end_meeting(m.meeting_id)
    assert len(got) == 1
    md = render_markdown(got[0])
    assert "| Sign Razorpay agreement | Vikram | Friday |" in md
    assert "Launch on the 20th (by Priya)" in md
