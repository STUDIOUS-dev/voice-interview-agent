import json
import time

import google.generativeai as genai

from modules.state import InterviewState


_SAFE_DEFAULT = {
    "spoken_reply": "Thank you for your answer. Let's move on.",
    "move_to_next": True,
    "candidate_score": 3,
    "private_feedback": "Evaluation failed — manual review needed.",
    "follow_up_reason": "",
}

_EVAL_SCHEMA = {
    "type": "object",
    "properties": {
        "spoken_reply":     {"type": "string"},
        "move_to_next":     {"type": "boolean"},
        "candidate_score":  {"type": "integer"},
        "private_feedback": {"type": "string"},
        "follow_up_reason": {"type": "string"},
    },
    "required": [
        "spoken_reply",
        "move_to_next",
        "candidate_score",
        "private_feedback",
        "follow_up_reason",
    ],
}


def _build_system_prompt(state: InterviewState) -> str:
    return (
        f"You are a professional but approachable technical interviewer "
        f"conducting a screening interview for a Software Engineering role.\n"
        f"The interview language is {state.language}.\n\n"
        f"You are currently evaluating the candidate on this question:\n"
        f"\"{state.current_question['question']}\"\n\n"
        f"The ideal answer covers these points (DO NOT reveal this to the candidate):\n"
        f"\"{state.current_question['ideal_answer']}\"\n\n"
        f"Rules you must follow without exception:\n"
        f"1. Evaluate the candidate's answer against the ideal answer points.\n"
        f"2. If their answer covers the key points well: praise briefly and set "
        f"   move_to_next to true.\n"
        f"3. If their answer is partially correct: ask exactly ONE follow-up question "
        f"   to guide them toward the missing points. Set move_to_next to false.\n"
        f"4. If their answer is completely incorrect or off-topic: gently correct "
        f"   them in one sentence, then set move_to_next to true.\n"
        f"5. NEVER reveal the exact wording of the ideal answer.\n"
        f"6. Keep spoken_reply under 3 sentences — concise, not verbose.\n"
        f"7. Score the candidate from 1 to 5 based on their BEST response across "
        f"   all follow-ups for this question (5 = covered all key points, "
        f"   1 = no relevant content).\n"
        f"8. Generate private_feedback in English regardless of interview language. "
        f"   This is a recruiter-facing note and must always be in English.\n"
        f"9. Respond in {state.language} for spoken_reply. "
        f"   Respond in English for private_feedback."
    )


def _build_contents(state: InterviewState, user_text: str) -> list:
    contents = list(state.conversation_history)
    contents.append({"role": "user", "parts": [user_text]})
    return contents


def _parse_and_validate(raw_text: str) -> dict:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(l for l in lines if not l.startswith("```")).strip()

    result = json.loads(text)

    required = {"spoken_reply", "move_to_next", "candidate_score",
                 "private_feedback", "follow_up_reason"}
    missing = required - set(result.keys())
    if missing:
        raise ValueError(f"Missing required fields: {missing}")

    if not result.get("spoken_reply", "").strip():
        raise ValueError("spoken_reply is empty")

    score = result.get("candidate_score", 3)
    result["candidate_score"] = max(1, min(5, int(score)))

    return result


def evaluate_response(
    user_text: str,
    state: InterviewState,
    settings,
) -> dict:
    system_prompt = _build_system_prompt(state)
    contents = _build_contents(state, user_text)

    strict_suffix = (
        "\n\nCRITICAL: Your entire response must be a single valid JSON object. "
        "No prose, no markdown, no explanation. Just the JSON."
    )

    for attempt in range(1, 3):
        try:
            current_system = system_prompt if attempt == 1 else system_prompt + strict_suffix

            model = genai.GenerativeModel(
                model_name=settings.llm_model,
                system_instruction=current_system,
            )

            response = model.generate_content(
                contents=contents,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    response_mime_type="application/json",
                    response_schema=_EVAL_SCHEMA,
                ),
            )

            result = _parse_and_validate(response.text)
            return result

        except (json.JSONDecodeError, ValueError) as e:
            if attempt == 1:
                print(f"[Evaluation parse error (attempt 1): {e}. Retrying with stricter prompt...]")
                time.sleep(1)
            else:
                print(f"[Evaluation parse error (attempt 2): {e}. Using safe default.]")
                return _SAFE_DEFAULT.copy()

        except Exception as e:
            if attempt == 1:
                wait = 2
                print(f"[Evaluation API error (attempt 1): {e}. Retrying in {wait}s...]")
                time.sleep(wait)
            else:
                print(f"[Evaluation API error (attempt 2): {e}. Using safe default.]")
                return _SAFE_DEFAULT.copy()

    return _SAFE_DEFAULT.copy()


def handle_silence(
    state: InterviewState,
    settings,
    speak_fn,
) -> bool:
    state.silence_count += 1

    if state.silence_count == 1:
        retry_messages = {
            "English": "I didn't quite catch that. Could you please repeat your answer?",
            "Hindi":   "मुझे समझ नहीं आया। क्या आप दोबारा बोल सकते हैं?",
            "German":  "Ich habe das nicht verstanden. Könnten Sie das bitte wiederholen?",
        }
        prompt = retry_messages.get(state.language, retry_messages["English"])
        speak_fn(prompt, settings, state.tts_lang_code)
        return False

    else:
        skip_messages = {
            "English": "No worries. Let's move on to the next question.",
            "Hindi":   "कोई बात नहीं, अगले सवाल पर चलते हैं।",
            "German":  "Kein Problem, weiter zur nächsten Frage.",
        }
        prompt = skip_messages.get(state.language, skip_messages["English"])
        speak_fn(prompt, settings, state.tts_lang_code)

        state.feedback_log.append({
            "question": state.current_question["question"],
            "score": 1,
            "notes": "Candidate did not respond — potential technical issue or no answer provided.",
        })
        return True
