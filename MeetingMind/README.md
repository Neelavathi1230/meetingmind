# MeetingMind – Meeting Transcript Analysis System
Meeting speech → transcript → summary, decisions, action items (owner + deadline), open questions, speaking share, tone.

## Run
```bash
pip install -r requirements.txt
cd backend && uvicorn main:app --reload      # http://127.0.0.1:8000
```

## Real vs demo
- **Analysis is always real and local** (`backend/nlp.py`): speaker-line parsing, extractive summary, pattern-based decision and action-item detection, owner/deadline extraction, keyword topics, speaking-time share, lexicon tone.
- **Speech-to-text:** `pip install faster-whisper` for real transcription. Without it, uploaded audio gets a built-in *sample* transcript, labelled "demo". Pasting a transcript always works (no speech engine needed).
- Whisper does not label speakers; audio transcripts show as “Unknown”. For speaker analysis, paste “Name: text” lines or add diarization (future work).

## API
`POST /api/auth/{register,login,logout}` · `POST /api/meetings` (audio or transcript) · `GET /api/meetings` · `GET|PUT|DELETE /api/meetings/{id}` (PUT edits title, transcript → re-analysis, or action-item status)

## Limits
Rule-based extraction can miss or over-detect items; users can edit the transcript and tick off tasks. Future work: speaker diarization, ML/LLM extractors, calendar/email export, PDF/DOCX reports.
