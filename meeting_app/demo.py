"""
End-to-end demo: create a meeting, have people join, replay a Hindi/English
transcript as if it were coming live from speech-to-text, end the meeting, and
print the automated notes + summary.

Run from the repo root:
    pip install anthropic pydantic
    export ANTHROPIC_API_KEY=...        # or a .env / `ant auth login` profile
    python meeting_app/demo.py [path/to/transcript.json]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from meetings import MeetingManager, TranscriptSegment  # noqa: E402
from note_taker import NoteTaker, attach_note_taker, render_markdown  # noqa: E402


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "sample_transcript.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    manager = MeetingManager()
    meeting = manager.create_meeting(title=data["title"], host_name=data["host"])
    print(f"Meeting created: {meeting.title}")
    print(f"  ID {meeting.meeting_id}  passcode {meeting.passcode}")
    print(f"  Join link: {meeting.join_link}\n")

    for name in data["participants"]:
        manager.join(meeting.meeting_id, name, meeting.passcode)
    print(f"{len(meeting.active_participants)} participants joined (limit {meeting.max_participants})\n")

    # Small chunk size so the demo shows a live notes refresh mid-meeting.
    note_taker = NoteTaker(chunk_words=120)

    def save(m, notes):
        md = render_markdown(notes)
        out = path.with_suffix(".notes.md")
        out.write_text(md, encoding="utf-8")
        print(md)
        print(f"(saved to {out})")

    attach_note_taker(manager, meeting, note_taker, on_notes=save)

    for raw in data["segments"]:
        segment = TranscriptSegment(**raw)
        manager.add_transcript_segment(meeting.meeting_id, segment)
        print(f"  {segment.speaker}: {segment.text}")
        if not note_taker._pending:  # a chunk was just merged into the live notes
            print(f"    -> live notes updated: {len(note_taker.notes.decisions)} decisions, "
                  f"{len(note_taker.notes.action_items)} action items so far")

    print("\nHost ended the meeting. Generating final notes...\n")
    manager.end_meeting(meeting.meeting_id)


if __name__ == "__main__":
    main()
