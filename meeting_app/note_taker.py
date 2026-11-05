"""
Automated meeting note taker (Hindi / English / Hinglish) using Claude.

Two phases, because meetings have no time limit:

1. LIVE  -- every ~N words of new transcript, Claude merges the new chunk into
            a running set of notes (key discussions, decisions, action items).
            The prompt only ever contains the previous notes + the new chunk,
            so cost per update stays flat no matter how long the meeting runs.
2. FINAL -- when the host ends the meeting, Claude writes the final notes and
            summary. If the whole transcript fits comfortably in one request it
            reads the full transcript (best quality); otherwise it works from
            the running notes.

Transcript segments come from a speech-to-text engine that handles Hindi,
English and code-switched Hinglish (see README.md for options). Claude reads
both Devanagari and romanized Hindi directly; notes are written in
`output_language` (English by default).
"""

from __future__ import annotations

from typing import Optional

import anthropic
from pydantic import BaseModel, Field

from meetings import Meeting, TranscriptSegment

MODEL = "claude-opus-5-5"

# ~1.3 tokens per English word, more for Devanagari. 150k words is far below the
# 1M-token context window but keeps the final request reasonably fast.
FULL_TRANSCRIPT_WORD_LIMIT = 150_000
DEFAULT_CHUNK_WORDS = 1_500


# ---------------------------------------------------------------------------
# Output schema (Claude's response is validated against these models)
# ---------------------------------------------------------------------------


class ActionItem(BaseModel):
    task: str = Field(description="What needs to be done, phrased as an action")
    owner: Optional[str] = Field(description="Person responsible, if stated or clearly implied")
    due: Optional[str] = Field(description="Deadline as said in the meeting, if any")


class Decision(BaseModel):
    decision: str
    made_by: Optional[str] = Field(description="Who made or approved it, if clear")
    context: str = Field(description="One line on why / what it resolves")


class Discussion(BaseModel):
    topic: str
    details: str = Field(description="Detailed notes: positions taken, numbers, options considered")
    speakers: list[str]


class RunningNotes(BaseModel):
    """Notes accumulated while the meeting is in progress."""

    key_discussions: list[Discussion]
    decisions: list[Decision]
    action_items: list[ActionItem]
    open_questions: list[str]


class MeetingNotes(RunningNotes):
    """Final notes, produced when the meeting ends."""

    title: str
    summary: str = Field(description="5-10 sentence executive summary of the whole meeting")
    languages_used: list[str] = Field(description="Languages spoken, e.g. ['Hindi', 'English']")


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the note taker for a business meeting. Participants speak \
Hindi, English, or a mix of both (Hinglish), sometimes switching mid-sentence; Hindi \
may appear in Devanagari or in Roman script, and the transcript comes from automatic \
speech recognition, so expect some misheard words.

Write all notes in {output_language}. Translate Hindi faithfully rather than \
summarizing it away; when a Hindi phrase carries meaning that translation would lose, \
keep it in parentheses after the translation. Keep people's names, product names, \
numbers, amounts (e.g. ₹, lakh, crore) and dates exactly as spoken.

Record only what was actually said. Do not invent owners or deadlines: if an action \
item has no clear owner or due date, leave that field null. A decision is something \
the group agreed on or someone with authority approved, not merely proposed; put \
unresolved proposals under open_questions instead."""


def format_segments(segments: list[TranscriptSegment]) -> str:
    lines = []
    for s in segments:
        minutes, seconds = divmod(int(s.start_seconds), 60)
        hours, minutes = divmod(minutes, 60)
        lines.append(f"[{hours:02d}:{minutes:02d}:{seconds:02d}] {s.speaker}: {s.text}")
    return "\n".join(lines)


def _word_count(segments: list[TranscriptSegment]) -> int:
    return sum(len(s.text.split()) for s in segments)


# ---------------------------------------------------------------------------
# Note taker
# ---------------------------------------------------------------------------


class NoteTakerError(Exception):
    pass


class NoteTaker:
    """Attach one NoteTaker per meeting. Feed it segments; call finalize() at the end."""

    def __init__(
        self,
        client: Optional[anthropic.Anthropic] = None,
        *,
        model: str = MODEL,
        output_language: str = "English",
        chunk_words: int = DEFAULT_CHUNK_WORDS,
        full_transcript_word_limit: int = FULL_TRANSCRIPT_WORD_LIMIT,
    ):
        self.client = client or anthropic.Anthropic()
        self.model = model
        self.system = SYSTEM_PROMPT.format(output_language=output_language)
        self.chunk_words = chunk_words
        self.full_transcript_word_limit = full_transcript_word_limit

        self.segments: list[TranscriptSegment] = []
        self._pending: list[TranscriptSegment] = []
        self.notes = RunningNotes(key_discussions=[], decisions=[], action_items=[], open_questions=[])

    # -- Claude call -----------------------------------------------------

    def _ask(self, prompt: str, schema: type[BaseModel]) -> BaseModel:
        response = self.client.beta.messages.parse(
            model=self.model,
            max_tokens=16000,
            system=self.system,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
            output_config={"effort": "high"},
            # If a safety classifier declines, the API retries on a fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason == "refusal":
            raise NoteTakerError("Claude declined to process this transcript chunk")
        if response.stop_reason == "max_tokens":
            raise NoteTakerError("Notes were cut off (max_tokens); lower chunk_words")
        if response.parsed_output is None:
            raise NoteTakerError("Claude did not return notes in the expected format")
        return response.parsed_output

    # -- live phase ------------------------------------------------------

    def add_segment(self, segment: TranscriptSegment) -> bool:
        """Buffer a segment. Returns True if the running notes were refreshed."""
        self.segments.append(segment)
        self._pending.append(segment)
        if _word_count(self._pending) >= self.chunk_words:
            self.flush()
            return True
        return False

    def flush(self) -> RunningNotes:
        """Merge any buffered transcript into the running notes now."""
        if not self._pending:
            return self.notes
        prompt = (
            "Here are the running notes so far, as JSON:\n"
            f"<running_notes>\n{self.notes.model_dump_json(indent=2)}\n</running_notes>\n\n"
            "Here is the next part of the meeting transcript:\n"
            f"<transcript_chunk>\n{format_segments(self._pending)}\n</transcript_chunk>\n\n"
            "Return the updated running notes: keep every existing item (edit it if the new "
            "chunk changes it, e.g. a proposal that became a decision, or an action item that "
            "got an owner), and add anything new from this chunk."
        )
        self.notes = self._ask(prompt, RunningNotes)
        self._pending = []
        return self.notes

    # -- final phase -----------------------------------------------------

    def finalize(self, title: str) -> MeetingNotes:
        """Produce the final notes + summary. Call when the meeting ends."""
        if not self.segments:
            return MeetingNotes(
                title=title,
                summary="No speech was transcribed in this meeting.",
                languages_used=[],
                key_discussions=[],
                decisions=[],
                action_items=[],
                open_questions=[],
            )

        if _word_count(self.segments) <= self.full_transcript_word_limit:
            source = (
                "Here is the full meeting transcript:\n"
                f"<transcript>\n{format_segments(self.segments)}\n</transcript>"
            )
        else:
            self.flush()
            source = (
                "The meeting was too long to include verbatim. Here are the detailed notes "
                "taken during the meeting:\n"
                f"<running_notes>\n{self.notes.model_dump_json(indent=2)}\n</running_notes>"
            )
        prompt = (
            f'The meeting "{title}" has ended.\n\n{source}\n\n'
            "Write the final meeting notes: detailed key discussions, every decision made, "
            "every action item (with owner and due date where stated), open questions, the "
            "languages used, and an executive summary of the whole meeting."
        )
        notes = self._ask(prompt, MeetingNotes)
        self._pending = []
        return notes


def attach_note_taker(manager, meeting: Meeting, note_taker: NoteTaker, on_notes=None) -> None:
    """Wire a NoteTaker to a MeetingManager's transcript and end-of-meeting events."""

    def handle_segment(m: Meeting, segment: TranscriptSegment) -> None:
        if m.meeting_id == meeting.meeting_id:
            note_taker.add_segment(segment)

    def handle_end(m: Meeting) -> None:
        if m.meeting_id == meeting.meeting_id:
            notes = note_taker.finalize(m.title)
            if on_notes:
                on_notes(m, notes)

    manager.on_segment(handle_segment)
    manager.on_end(handle_end)


def render_markdown(notes: MeetingNotes) -> str:
    """Pretty-print notes for email / chat / a notes page."""
    out = [f"# {notes.title}", "", "## Summary", notes.summary, ""]
    if notes.languages_used:
        out += [f"_Languages: {', '.join(notes.languages_used)}_", ""]
    out.append("## Key discussions")
    for d in notes.key_discussions:
        out.append(f"### {d.topic}")
        out.append(d.details)
        if d.speakers:
            out.append(f"_Speakers: {', '.join(d.speakers)}_")
        out.append("")
    out.append("## Decisions")
    out += [
        f"- {d.decision}" + (f" (by {d.made_by})" if d.made_by else "") + f" -- {d.context}"
        for d in notes.decisions
    ] or ["- None recorded"]
    out += ["", "## Action items", "| Task | Owner | Due |", "|---|---|---|"]
    out += [f"| {a.task} | {a.owner or '-'} | {a.due or '-'} |" for a in notes.action_items]
    if notes.open_questions:
        out += ["", "## Open questions"] + [f"- {q}" for q in notes.open_questions]
    return "\n".join(out) + "\n"
