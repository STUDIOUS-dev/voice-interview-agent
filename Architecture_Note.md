# Architecture Note: Voice Interview Agent

*Document version: 2.0 | Last updated: 2026-06-29*

---

## 1. Retrieval Design: State-Driven Sequential Retrieval

### Why RAG is the Wrong Pattern Here

Retrieval-Augmented Generation (RAG) is designed for user-initiated queries: the user asks something, and the system retrieves relevant context to answer it. This model is fundamentally user-driven - the retrieval is triggered by and grounded in the user's input.

An interviewer agent operates on the opposite paradigm: **the agent decides what comes next, not the candidate.** The agent must ask a specific question, retain the ideal answer for grading, and track exactly where in the interview it is. If we used RAG, there is no guarantee the correct question would be retrieved - similarity search might surface a different question if the candidate's answer accidentally resembles the topic of question 3 while the agent is on question 2.

### The State-Driven Approach

The agent uses a **sequential index into a JSON dataset** as its retrieval mechanism:

```
qa_dataset.json (7 questions) → slice to N → sequential list
         ↓
state.current_question_index  ← authoritative position tracker
         ↓
questions[index]              ← exact question + ideal_answer
         ↓
Injected into system prompt   ← LLM grounded on correct content
```

At each turn, `state.current_question` holds the exact question dict from the dataset. The `ideal_answer` is injected directly into the system prompt as a private rubric. The LLM scores the candidate against this rubric without the candidate ever seeing it.

**This guarantees:**
- The agent never loses its place in the interview.
- The ideal answer in context is always correct for the current question.
- No semantic search overhead - O(1) retrieval by index.
- The dataset is fully human-editable: add/remove/modify questions without touching code.

---

## 2. LLM Behavior & Grounding via Structured Outputs

### The JSON Schema

The evaluator uses Gemini's `response_mime_type: application/json` with `response_schema` to enforce a strict structured output on every evaluation turn:

```json
{
  "type": "object",
  "properties": {
    "spoken_reply":     { "type": "string" },
    "move_to_next":     { "type": "boolean" },
    "candidate_score":  { "type": "integer" },
    "private_feedback": { "type": "string" },
    "follow_up_reason": { "type": "string" }
  },
  "required": ["spoken_reply", "move_to_next", "candidate_score",
               "private_feedback", "follow_up_reason"]
}
```

### Field-by-Field Rationale

| Field | Type | Rationale |
|-------|------|-----------|
| `spoken_reply` | string | The exact text the TTS module speaks. Keeping it separate from reasoning prevents internal model monologue from being spoken aloud. |
| `move_to_next` | boolean | A binary state machine gate. Avoids ambiguous "maybe advance" responses. Forces the model to commit to a decision. |
| `candidate_score` | integer | Discrete 1–5 scale. Integers prevent spurious precision (no "3.7" scores). Code clips to valid range at parse time. |
| `private_feedback` | string | Recruiter-facing audit note, never spoken. Always in English regardless of session language (system prompt rule). Enables post-interview HR review without revealing the rubric to the candidate. |
| `follow_up_reason` | string | **The key insight:** this field forces the LLM to articulate internally *why* it is asking a follow-up before generating the follow-up question itself. This functions as a hidden chain-of-thought that significantly improves the quality and specificity of follow-up questions. It is printed to the terminal for debugging but never spoken aloud. |

### How Structured Outputs Prevent Hallucination

Without `response_schema`, the LLM might:
- Wrap the JSON in markdown code fences.
- Add prose before or after the JSON.
- Omit fields it deems unnecessary.
- Return `candidate_score: "four out of five"` (a string instead of integer).

With strict JSON schema enforcement, the model's output is guaranteed to be parseable on the first attempt in the vast majority of cases. The code still implements a retry-then-safe-default fallback for resilience.

---

## 3. Multi-Language Architecture

The system uses a three-layer approach to support English, Hindi, and German interviews.

### Layer 1 - Speech-to-Text (Google Speech Recognition)

```
Candidate speaks in Hindi → Google SR receives language="hi-IN" explicitly
```

Passing the BCP-47 language code explicitly prevents two problems:
1. **Misdetection:** Short technical answers (1-2 sentences) may be ambiguous to auto-detect. Explicit language prevents the recognizer from misidentifying Hindi as Bengali or German as Dutch.
2. **Technical term accuracy:** Words like "Python", "ORM", "REST", and "API" appear in all three languages unchanged. The recognizer handles these correctly when the language context is set.

### Layer 2 - LLM Evaluation (Google Gemini)

```
System prompt: "Evaluate logic in English internally.
                Respond in Hindi in spoken_reply.
                Always write private_feedback in English."
```

The critical design decision here is that **`ideal_answer` is always in English** regardless of the session language. This prevents two failure modes:
1. **Translation loss:** Technical nuances in ideal answers may not translate accurately. An ideal answer about Python generators that is translated to Hindi and then re-evaluated against a Hindi candidate response introduces two layers of potential semantic drift.
2. **Grading inconsistency:** The same answer in Hindi and English should receive the same score. Keeping the grading rubric in English and instructing the LLM to evaluate against it in English before responding in the target language ensures consistent scoring.

### Layer 3 - Text-to-Speech (gTTS)

```
TTS input: Hindi text → gTTS(lang="hi") → MP3 → pydub playback
```

gTTS uses Google Translate's text-to-speech engine and auto-selects the correct voice for the language code. No model switch or API key is needed. The ISO 639-1 language code is passed explicitly.

### Translation Strategy

Questions are translated **once at session start** in a single batch Gemini call:
- For English sessions: zero API calls (passthrough, O(0) cost).
- For non-English: one call translates all N questions.
- Translated strings are cached in `state.translated_questions` for the session.
- `ideal_answer` fields are **never translated** - they remain in English in all sessions.
- Technical terms (ORM, REST, API, Python, decorator, generator) are explicitly instructed to remain in English within the translated questions.
- Parse failure triggers a silent English fallback - the interview always continues.

---

## 4. Latency Pipeline & Production Roadmap

### Prototype Latency Breakdown

| Stage | Estimated Latency | Notes |
|-------|-------------------|-------|
| Silence detection / VAD | ~0.5s | Ambient noise calibration (once per session) |
| User speaks | variable | Typically 10–60s for technical answers |
| Google Speech Recognition | ~1.0–1.5s | Record-then-upload model; scales with audio length |
| Gemini evaluation | ~1.5–2.5s | Structured JSON output, ~200 token response |
| gTTS generation | ~0.5–1.0s | HTTP request to Google Translate TTS endpoint |
| Audio playback | variable | Length of synthesised reply |
| **Total perceived latency** | **~3.5–5.5s** | After user stops speaking, before agent starts speaking |

This latency is acceptable for a prototype but would feel slow in a production product. Three targeted improvements eliminate the bulk of this delay:

### Production Improvement 1: Streaming STT (Deepgram Nova-2)

Replace the Google Speech Recognition record-then-upload model with Deepgram's WebSocket streaming API:
- Transcription begins while the candidate is still speaking.
- First partial transcript available in **<200ms** of speech onset.
- Full transcript delivered within **<500ms** of the candidate finishing.
- Deepgram Nova-2 matches Google SR accuracy on English technical speech and exceeds it on longer utterances.

**Eliminates:** The 1.0–1.5s STT API latency and reduces the silence detection gap.

### Production Improvement 2: LLM Streaming + Sentence Chunking

Use `stream=True` on the Gemini chat completion:
1. Buffer the streaming response until the first sentence boundary (`.`, `?`, `!`).
2. Send the first sentence to TTS immediately.
3. Continue generating and buffering the rest.
4. Pipeline: sentence 1 is being spoken while sentence 2 is being synthesised.

**Eliminates:** The full 1.5–2.5s LLM wait before TTS begins. First word of the interviewer's reply appears within ~0.5s of the candidate stopping.

**Note:** Sentence chunking requires parsing the structured JSON fields as they stream, which adds implementation complexity. The `spoken_reply` field should be positioned first in the schema for this approach.

### Production Improvement 3: WebRTC Audio Pipeline

Replace SpeechRecognition's energy-threshold VAD with a WebRTC-based pipeline:
- WebRTC VAD operates at 10–30ms frame resolution (vs. 100–300ms for energy threshold).
- Eliminates the 0.5s ambient noise calibration step.
- Enables barge-in detection: candidate can interrupt the interviewer's TTS reply.
- Combined with Deepgram WebSocket streaming, creates a fully bidirectional real-time audio pipeline.

**Eliminates:** The VAD silence gap entirely. End-to-end perceived latency drops to **~1.5–2.5s**.

---

## 5. Error Handling & Reliability

The system implements layered error handling across all failure modes, ensuring the interview always reaches a conclusion even under adverse conditions.

### Silence Timeout Recovery

```
Candidate doesn't speak for 10s
    → WaitTimeoutError caught in record_and_transcribe()
    → Returns {"timed_out": True}
    → handle_silence() increments silence_count
    → silence_count == 1: speak retry prompt, return False (retry)
    → silence_count == 2: speak skip prompt, log score=1, return True (advance)
```

The interview never hangs. After two consecutive silences, the question is scored 1 and the agent moves on. The `silence_count` resets to 0 at the start of each new question.

### LLM Retry with Strict Fallback

The Gemini evaluation call uses a two-attempt strategy:
```
Attempt 1 → standard system prompt → parse JSON
    ↓ failure
Attempt 2 → append strict suffix ("ONLY valid JSON, no prose") → parse JSON
    ↓ failure
Return safe default: {move_to_next: True, score: 3, spoken_reply: "Thank you..."}
```
The safe default always advances the interview. A score of 3 (middle of the scale) is logged for manual review.

### STT Retry with Exponential Backoff

Google Speech Recognition API calls retry with exponential backoff:
```
Attempt 1 → failure → wait 2s
Attempt 2 → failure → wait 4s
Attempt 3 → failure → return api_error state
```
Backoff respects rate limit windows without flooding the API with retries.

### FFmpeg Detection at Startup

The `ffmpeg_check` module runs at startup (voice mode only) and:
1. Locates `ffmpeg`/`ffprobe` via `shutil.which` then pydub fallback.
2. Explicitly wires paths into `AudioSegment.converter` and `AudioSegment.ffprobe`.
3. Exits with an actionable, OS-specific install command if FFmpeg is missing.

This prevents cryptic pydub errors mid-interview.

### Temp File Hygiene

All temporary files (`temp_output.mp3`) are deleted in `finally` blocks. Files are guaranteed to be cleaned up even if an exception occurs during processing. This prevents accumulation of audio files that could contain PII (candidate speech data).
