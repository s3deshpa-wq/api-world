# Meeting app with an automated Hindi/English note taker

This folder covers two things:

1. **How Zoom handles each feature you listed**, and how you would build the same thing.
2. **A working Python prototype** of the parts that belong to your app rather than to a video vendor: the meeting rules (create, join, 50-person cap, no time limit) and the Claude-powered note taker (live notes, decisions, action items, final summary, Hindi/English/Hinglish).

```
meeting_app/
  meetings.py              meeting rooms: create / join (max 50) / leave / end, transcript events
  note_taker.py            Claude note taker: live running notes + final notes & summary
  demo.py                  end-to-end demo with a Hinglish sample meeting
  sample_transcript.json   sample: Hindi (Devanagari), romanized Hindi, English, code-mixed
tests/test_meeting_app.py  offline tests (fake Claude client)
```

---

## 1. How Zoom works, feature by feature

### The big picture

A Zoom meeting has three layers:

| Layer | What it does | In Zoom | In your app |
|---|---|---|---|
| **Control plane** | Accounts, scheduling, meeting IDs and passcodes, who may join, host controls | Zoom's web/API backend | Your backend (`meetings.py`) |
| **Media plane** | Moves live audio and video between participants | Zoom's own "multimedia router" servers, which act like an SFU (below) | A WebRTC SFU: LiveKit, mediasoup, Jitsi, or a hosted service (LiveKit Cloud, Daily, Agora, 100ms, Twilio) |
| **Intelligence** | Transcripts, AI Companion summaries, action items | Zoom AI Companion | Speech-to-text, then Claude (`note_taker.py`) |

**SFU (Selective Forwarding Unit):** each participant uploads their audio/video once to a server, and the server forwards each stream to everyone else. Nobody connects directly to all 49 other people, which would never scale. The SFU also sends lower-quality video layers to people on weak connections (this is called *simulcast*). Zoom built its own version of this. You shouldn't build one yourself: use LiveKit (open source, self-hostable or cloud) or a hosted provider.

### Feature 1: Set up a meeting that others can join

**Zoom:** the host clicks *New meeting* or *Schedule*. Zoom creates a meeting ID (9–11 digits) and a passcode and builds a join link such as `zoom.us/j/<id>?pwd=<hash>`. Anyone with the link opens the app or browser, and the backend checks the ID, passcode, waiting room and authentication settings. If they pass, the client gets connection details for a media server.

**Your app:** `MeetingManager.create_meeting()` generates the ID, passcode and join link. `join()` checks the passcode and the meeting's state. In production, a successful `join()` also creates a short-lived **SFU access token** (with LiveKit, a JWT naming the room and the user). The browser or mobile app uses that token to connect to the media server. Your backend never touches the audio or video.

### Feature 2: No limit on meeting time

**Zoom:** time limits are a business rule, not a technical one. Free accounts are cut off at 40 minutes, and paid plans allow up to 30 hours per meeting. The server simply ends the meeting when the timer runs out.

**Your app:** leave the timer out. `Meeting` has no duration field, and a meeting runs until the host calls `end_meeting()`. To support very long meetings in practice:
- **Token expiry:** SFU tokens expire, so refresh them before they do. A refresh must never disconnect anyone.
- **Reconnects:** laptops sleep and networks change. Let clients rejoin the same room using the same participant ID.
- **Recordings and transcripts:** store them in rolling chunks (for example every 5–10 minutes) instead of one giant file.
- **Note taker cost:** the note taker's cost per update must stay flat as the meeting grows. `note_taker.py` handles this: each live update sends only the previous notes plus the newest chunk of transcript, never the whole transcript.

### Feature 3: Maximum 50 participants

**Zoom:** capacity depends on the plan (100 on base plans, up to 1,000 with add-ons). The backend counts active participants and rejects or queues people beyond the cap.

**Your app:** `join()` counts active participants inside a lock and raises `MeetingFullError` for the 51st person. Leaving frees a seat. Also set the same limit on the SFU room (LiveKit has a `max_participants` setting), so nobody can bypass your API. Fifty people is comfortable for one SFU node. To keep bandwidth down, show a gallery of about 9–25 tiles and lower the video quality for thumbnails.

### Feature 4: Automated note taker (key discussions, decisions, action items)

**Zoom:** AI Companion records the meeting audio, transcribes it with speaker labels, and runs a language model over the transcript to produce a summary, next steps and topic notes.

**Your app:** the pipeline looks like this:

```
 participant mics ──► SFU room ──► note-taker bot (joins as a hidden participant)
                                     │ one audio track per speaker, so you know who is talking
                                     ▼
                         streaming speech-to-text (Hindi + English)
                                     │ TranscriptSegment(speaker, text, start_seconds, language)
                                     ▼
          MeetingManager.add_transcript_segment()  ──►  NoteTaker.add_segment()
                                                          │ every ~1,500 words:
                                                          ▼
                                     Claude merges the new chunk into the running notes
                                     (key discussions, decisions, action items, open questions)
```

- **Speaker labels:** the bot subscribes to each participant's audio track separately, so you know exactly who said what without guessing speakers from a mixed recording. With LiveKit this is a LiveKit Agents worker.
- **Live notes:** `NoteTaker.flush()` sends Claude the current running notes and the new transcript chunk. Claude returns the updated notes. For example, a proposal can become a decision, or an action item can gain an owner. The response is checked against Pydantic models, so the app always gets valid JSON with fields such as `task`, `owner` and `due`.
- **No invented details:** the prompt says a *decision* is something agreed or approved, not merely proposed. Unresolved proposals go under *open questions*. If nobody was named as the owner or given a deadline, those fields stay `null`.

### Feature 5: Hindi and/or English

This is the hardest part, and almost all of it is in **speech-to-text**, not the notes. Indian meetings switch languages mid-sentence (*"website ka design almost ready hai"*), and many speech engines force one language per audio stream. Pick an engine that handles **code-switching**. Options to benchmark:

| Engine | Notes |
|---|---|
| Sarvam AI (Saarika / Saaras) | Built for Indian languages and code-mixed speech; can return Devanagari or romanized text |
| Deepgram (Nova-3 multilingual) | Streaming, handles code-switching across languages including Hindi |
| Google Cloud Speech-to-Text (Chirp) | Strong `hi-IN`; can be given English as an alternative language |
| Azure AI Speech | Real-time `hi-IN` and `en-IN` |
| Whisper large-v3 (self-hosted) | Good multilingual accuracy; streaming requires extra work |

Test these on 20–30 minutes of **your own** recorded meetings before choosing. Accents, microphones and the mix of languages matter more than published benchmarks.

Claude reads Hindi in Devanagari, romanized Hindi and mixed text directly, so no translation step is needed. The prompt asks it to write notes in `output_language` (English by default, and you can pass `"Hindi"`), to translate faithfully rather than drop Hindi parts, and to keep names, ₹ amounts, *lakh*/*crore* and dates exactly as spoken. It also warns Claude that the transcript comes from automatic speech recognition, so it can work around misheard words.

### Feature 6: Summary when the meeting ends

**Zoom:** after the meeting, AI Companion emails the host a summary and posts it to the meeting's page.

**Your app:** `end_meeting()` triggers the `on_end` event, and `attach_note_taker` wires that to `NoteTaker.finalize()`:
- If the full transcript is under ~150k words (roughly 8+ hours of speech), Claude reads **the entire transcript** for the best summary. Claude has a 1M-token context window.
- If it's longer, Claude works from the notes it built up during the meeting.
- The result is a `MeetingNotes` object (summary, key discussions, decisions, action items, open questions, languages used). `render_markdown()` turns it into Markdown you can email, post in chat or show on a page.

---

## 2. Running the prototype

```bash
pip install anthropic pydantic pytest
```

```bash
pytest -v tests/test_meeting_app.py        # offline, no API key needed
```

```bash
export ANTHROPIC_API_KEY=sk-ant-...        # or use `ant auth login`
python meeting_app/demo.py                 # makes real Claude calls
```

The demo creates a meeting, joins 4 people, replays `sample_transcript.json` as if it were arriving live from speech-to-text (showing a live notes update partway through), ends the meeting, prints the final notes, and saves them to `meeting_app/sample_transcript.notes.md`. To use your own transcript, pass a JSON file with the same shape: `python meeting_app/demo.py my_meeting.json`.

**Claude settings used** (`note_taker.py`): model `claude-opus-5-5`, `effort: high`, structured output through `client.beta.messages.parse(output_format=...)`, and server-side refusal fallback (`fallbacks="default"`), so a rare safety decline is retried on another model instead of losing the notes.

---

## 3. Turning this into a real product

1. **Media:** stand up LiveKit (Cloud or self-hosted) and add a `/meetings/{id}/join` endpoint that calls `MeetingManager.join()` and returns a LiveKit token. Build the web client with LiveKit's React components; mobile SDKs are available too.
2. **API:** put `MeetingManager` behind FastAPI and move storage from dicts to Postgres. Add host controls: mute, remove participant, waiting room, end for all.
3. **Note-taker bot:** a LiveKit Agents worker that joins each room, streams each speaker's audio to your chosen speech-to-text engine, and calls `add_transcript_segment()` for each finished utterance.
4. **Run Claude calls in the background:** `flush()` and `finalize()` take seconds to minutes. Run them in a job queue (Celery, RQ, or `asyncio` with `anthropic.AsyncAnthropic`) so they never block the meeting.
5. **Deliver notes:** save them in the database, show live notes in a side panel, and email the final notes to participants.
6. **Consent and privacy:** show everyone a clear "this meeting is being transcribed" notice, let the host turn the note taker off, and decide how long audio and transcripts are kept. Recording consent is legally required in many places.
