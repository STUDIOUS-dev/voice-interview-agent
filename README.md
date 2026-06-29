# Voice Interview Agent

> AI-powered voice screening that interviews candidates - so you don't have to.

---

## What It Does

The Voice Interview Agent conducts fully automated technical screening interviews via voice. The candidate speaks their answers aloud; Google Speech Recognition (free, no key) transcribes the speech in real time; Google Gemini evaluates the response against a predefined ideal answer and decides whether to ask a follow-up or advance; and gTTS (Google Text-to-Speech, free) speaks the interviewer's reply back to the candidate. At the end of the session, a structured recruiter report is generated automatically and saved to disk.


---

## Setup

### Prerequisites

- **Python 3.11+**
- **ffmpeg** (required for audio playback via pydub)

  | Platform | Command |
  |----------|---------|
  | macOS    | `brew install ffmpeg` |
  | Ubuntu / Debian | `sudo apt install ffmpeg` |
  | Windows  | Download from [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html) and add `bin/` to your system PATH |

- **Google API key** (for Gemini only) - get a **free** key at [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
  - No billing required - Google AI Studio has a generous free tier
  - Speech Recognition (STT) and gTTS (TTS) are **completely free** with no key needed

> **Note for Windows PyAudio users:** If `pip install PyAudio` fails, try:
> ```
> pip install pipwin
> pipwin install pyaudio
> ```
> Or download a pre-built wheel from [https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio](https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio)

---

### Installation Steps

**Step 1 - Clone the repository**
```bash
git clone https://github.com/STUDIOUS-dev/voice-interview-agent.git
cd voice-interview-agent
```

**Step 2 - Create and activate a virtual environment**
```bash
# Mac / Linux
python3.11 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

**Step 3 - Install Python dependencies**
```bash
pip install -r requirements.txt
```

**Step 4 - Configure your Google API key**
```bash
cp .env.example .env
# Open .env and replace the placeholder with your free Gemini key from:
# https://aistudio.google.com/app/apikey
```

**Step 5 - Run the agent**
```bash
python main.py --lang English
```

---

## CLI Options

| Flag | Values | Default | Description |
|------|--------|---------|-------------|
| `--lang` | `English` \| `Hindi` \| `German` | `English` | Interview language |
| `--questions` | integer | all (7) | Number of questions to ask |
| `--mode` | `voice` \| `text` | `voice` | Input mode (`text` requires no microphone) |

### Example Commands

```bash
# Standard English interview with all 7 questions
python main.py

# Hindi interview, 3 questions only
python main.py --lang Hindi --questions 3

# German interview via keyboard (no microphone required)
python main.py --mode text --lang German

# Quick 2-question text-mode test
python main.py --mode text --questions 2
```

---

## Running Tests

```bash
python -m unittest discover tests
```

This runs all tests in the `tests/` directory:
- **`test_dataset.py`** - validates `qa_dataset.json` schema (5 tests, no API calls)
- **`test_evaluator.py`** - validates evaluation logic with mocked LLM (4 tests, no API calls)

All tests run offline - no API key required.

---

## Project Structure

```
/voice-interview-agent
├── .env.example              # API key placeholder - never commit .env
├── .gitignore
├── README.md
├── requirements.txt
├── Architecture_Note.md      # Technical architecture analysis (retrieval, LLM grounding, latency)
├── qa_dataset.json           # 7 interview questions with ideal answers
├── main.py                   # CLI entry point + state machine orchestrator
├── config.py                 # Loads .env, exposes typed Settings dataclass
├── modules/
│   ├── __init__.py
│   ├── stt.py                # Speech-to-text via Google Speech Recognition (free)
│   ├── tts.py                # Text-to-speech via gTTS + pydub playback
│   ├── evaluator.py          # LLM evaluation with structured JSON output (Gemini)
│   ├── feedback.py           # Final report generation + save to file
│   ├── ffmpeg_check.py       # Proactive FFmpeg detection at startup
│   ├── translator.py         # Batch question translation for non-English sessions
│   └── state.py              # InterviewState dataclass - shared session state
└── tests/
    ├── test_evaluator.py     # Mock LLM tests for evaluation logic
    └── test_dataset.py       # Schema validation for qa_dataset.json
```

---

## Key Design Decisions

### Why state-driven sequential retrieval (not RAG)?
Standard RAG retrieves context based on the user's query - it's user-driven. An interviewer agent is agent-driven: the interviewer decides which question to ask next, not the candidate. A sequential index into `qa_dataset.json` guarantees the agent never loses its place and always has the correct ideal_answer in context without any similarity search overhead.

### Why structured JSON output schema?
Gemini's `response_mime_type: application/json` with `response_schema` enforces that the model returns exactly the fields we need - no parsing heuristics, no regex extraction. The `follow_up_reason` field acts as a hidden chain-of-thought: by forcing the model to articulate why it's asking a follow-up before generating the reply, the quality of follow-up questions improves significantly.

### Why batch translation at session start?
Translating per-question at runtime would add ~1s latency before every question. Batch translation at startup costs one API call and stores the results in memory for the session duration. If translation fails, the session falls back to English silently - the interview always continues.

### Why does private_feedback stay in English?
Recruiter reports need to be consistent across multilingual sessions. A recruiter reviewing a Hindi interview should receive the same feedback format as for an English interview. Forcing `private_feedback` to English in the system prompt ensures HR records remain standardised.

### Why does `--mode text` exist?
Text mode (`--mode text`) allows the system to be fully tested in CI environments without microphone hardware, and lets developers iterate on the evaluation logic without audio setup. It also makes the agent accessible in environments where audio is impractical.

---

## Customising Questions

Edit `qa_dataset.json` to add, remove, or modify questions. No code changes required. Each entry must have:

```json
{
  "id": 8,
  "question": "Your question here?",
  "ideal_answer": "2-4 sentences covering the key scoring points."
}
```

---

## Cost Estimate (per session, 7 questions)

| Component | Service | Approx. Cost |
|-----------|---------|-------------|
| **STT (Speech-to-Text)** | Google Speech Recognition (free) | **$0.00** |
| **LLM (Evaluation + Feedback)** | Google Gemini Flash (free tier: 15 RPM, 1M tokens/day) | **$0.00** on free tier |
| **TTS (Text-to-Speech)** | gTTS - Google Translate TTS (free) | **$0.00** |
| **Total** | | **$0.00** (free tier) |

> The free tier of Google AI Studio (Gemini) is sufficient for development and demos.
> For production at scale, Gemini Flash is priced at ~$0.075 per 1M input tokens.

Costs vary based on answer length and number of follow-ups.
