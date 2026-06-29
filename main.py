import argparse
import json
import os
import sys

import google.generativeai as genai

from config import load_settings
from modules.evaluator import evaluate_response, handle_silence
from modules.feedback import generate_final_feedback, save_report
from modules.ffmpeg_check import ensure_ffmpeg
from modules.state import InterviewState
from modules.translator import translate_questions
from modules.tts import speak


LANG_CONFIG = {
    "English": {
        "stt_lang":     "en-US",   
        "tts_lang":     "en",      
        "greeting": (
            "Hello! Welcome to your technical screening interview. "
            "I'll be asking you {n} questions today. "
            "Take your time and speak clearly. Let's begin."
        ),
        "outro": (
            "That's all the questions. Thank you for your time. "
            "I'm now generating your feedback report."
        ),
        "retry_prompt": "I didn't catch that. Could you please repeat your answer?",
        "skip_prompt":  "No worries, let's move on to the next question.",
        "next_question": "Here is your next question.",
    },
    "Hindi": {
        "stt_lang":     "hi-IN",
        "tts_lang":     "hi",
        "greeting": (
            "नमस्ते! आपके तकनीकी इंटरव्यू में आपका स्वागत है। "
            "आज मैं आपसे {n} सवाल पूछूँगा। "
            "ध्यान से सुनें और स्पष्ट रूप से बोलें।"
        ),
        "outro": (
            "बस इतने ही सवाल थे। आपका बहुत धन्यवाद। "
            "मैं अब आपकी रिपोर्ट तैयार कर रहा हूँ।"
        ),
        "retry_prompt":  "मुझे समझ नहीं आया। क्या आप दोबारा बोल सकते हैं?",
        "skip_prompt":   "कोई बात नहीं, अगले सवाल पर चलते हैं।",
        "next_question": "अगला सवाल यह है।",
    },
    "German": {
        "stt_lang":     "de-DE",
        "tts_lang":     "de",
        "greeting": (
            "Hallo! Willkommen zu Ihrem technischen Vorstellungsgespräch. "
            "Ich werde Ihnen heute {n} Fragen stellen. "
            "Sprechen Sie klar und deutlich."
        ),
        "outro": (
            "Das waren alle Fragen. Vielen Dank für Ihre Zeit. "
            "Ich erstelle jetzt Ihren Feedback-Bericht."
        ),
        "retry_prompt":  "Ich habe das nicht verstanden. Könnten Sie das bitte wiederholen?",
        "skip_prompt":   "Kein Problem, weiter zur nächsten Frage.",
        "next_question": "Hier ist Ihre nächste Frage.",
    },
}


MAX_FOLLOW_UPS_PER_QUESTION = 3


def _get_stt_functions():
    from modules.stt import calibrate_microphone, record_and_transcribe
    return calibrate_microphone, record_and_transcribe


def load_dataset(path: str) -> list:
    if not os.path.exists(path):
        print(
            f"\nERROR: Dataset file not found: {path}\n"
            f"  Make sure qa_dataset.json is in the project root directory.\n"
        )
        sys.exit(1)

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list) or len(data) == 0:
            raise ValueError("Dataset must be a non-empty JSON array.")
        return data
    except (json.JSONDecodeError, ValueError) as e:
        print(f"\nERROR: Invalid dataset file ({path}): {e}\n")
        sys.exit(1)


def main() -> None:
    
    parser = argparse.ArgumentParser(
        description="Voice Interview Agent - AI-powered technical screening"
    )
    parser.add_argument(
        "--lang",
        type=str,
        default="English",
        choices=["English", "Hindi", "German"],
        help="Language for the interview session (default: English)",
    )
    parser.add_argument(
        "--questions",
        type=int,
        default=None,
        help="Number of questions to ask (default: all in dataset)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="voice",
        choices=["voice", "text"],
        help="Input mode: voice (microphone) or text (keyboard, for testing)",
    )
    args = parser.parse_args()

    
    if args.mode == "voice":
        ensure_ffmpeg(verbose=True)

    
    settings = load_settings()
    genai.configure(api_key=settings.google_api_key)

    
    questions = load_dataset(settings.dataset_path)

    
    n = args.questions if args.questions is not None else len(questions)
    n = max(1, min(n, len(questions)))  
    questions = questions[:n]

    
    lang_config = LANG_CONFIG[args.lang]

    
    state = InterviewState(
        language=args.lang,
        stt_lang_code=lang_config["stt_lang"],
        tts_lang_code=lang_config["tts_lang"],
        total_questions=n,
    )

    
    print(f"\n[Preparing session in {args.lang}...]")
    state.translated_questions = translate_questions(questions, args.lang, settings)

    
    recognizer = None
    if args.mode == "voice":
        calibrate_microphone, record_and_transcribe = _get_stt_functions()
        recognizer = calibrate_microphone()
    else:
        record_and_transcribe = None
        print("[Text mode active - type your answers when prompted]")

    
    greeting_text = lang_config["greeting"].format(n=n)
    speak(greeting_text, settings, lang_config["tts_lang"], bypass_audio=(args.mode == "text"))
    print(f"\n[Session started | Language: {args.lang} | Questions: {n} | Mode: {args.mode}]")
    print("-" * 52)

    
    input_closed = False
    for i, translated_q in enumerate(state.translated_questions):
        if input_closed:
            break
        
        state.current_question_index = i
        state.current_question = questions[i]          
        state.conversation_history = []                 
        state.silence_count = 0                         

        question_to_speak = translated_q.get("translated_question", translated_q["question"])

        print(f"\n{'-' * 52}")
        print(f"  Question {i + 1} of {n}")
        print(f"{'-' * 52}")

        
        if i > 0:
            speak(lang_config["next_question"], settings, lang_config["tts_lang"], bypass_audio=(args.mode == "text"))

        speak(question_to_speak, settings, lang_config["tts_lang"], bypass_audio=(args.mode == "text"))

        move_to_next = False
        follow_up_count = 0

        
        while not move_to_next:

            
            if follow_up_count >= MAX_FOLLOW_UPS_PER_QUESTION:
                print(f"[Maximum follow-ups ({MAX_FOLLOW_UPS_PER_QUESTION}) reached - advancing]")
                
                last_score = state.feedback_log[-1]["score"] if state.feedback_log else 2
                state.feedback_log.append({
                    "question": state.current_question["question"],
                    "score": max(last_score, 1),
                    "notes": "Maximum follow-ups reached - candidate may need more preparation.",
                })
                move_to_next = True
                continue

            
            if args.mode == "voice":
                stt_result = record_and_transcribe(
                    recognizer,
                    state.stt_lang_code,
                    settings,
                )
            else:
                
                try:
                    raw = input("\n[Type your answer]: ").strip()
                except EOFError:
                    print("\n[Input stream closed - ending interview]")
                    input_closed = True
                    break

                stt_result = {
                    "text": raw,
                    "timed_out": False,
                    "empty": raw == "",
                    "api_error": False,
                }

            
            if stt_result.get("timed_out") or stt_result.get("empty"):
                should_advance = handle_silence(
                    state,
                    settings,
                    lambda msg, setts, lang: speak(msg, setts, lang, bypass_audio=(args.mode == "text"))
                )
                if should_advance:
                    move_to_next = True
                continue

            
            if stt_result.get("api_error"):
                speak(
                    "I'm having a technical issue with audio processing. Let's move on.",
                    settings,
                    lang_config["tts_lang"],
                    bypass_audio=(args.mode == "text"),
                )
                state.feedback_log.append({
                    "question": state.current_question["question"],
                    "score": 1,
                    "notes": "STT error - response could not be captured.",
                })
                move_to_next = True
                continue

            
            user_text = stt_result["text"]
            eval_result = evaluate_response(user_text, state, settings)

            
            speak(eval_result["spoken_reply"], settings, lang_config["tts_lang"], bypass_audio=(args.mode == "text"))

            
            state.conversation_history.append({"role": "user",  "parts": [user_text]})
            state.conversation_history.append({"role": "model", "parts": [eval_result["spoken_reply"]]})

            
            if eval_result["move_to_next"]:
                state.feedback_log.append({
                    "question": state.current_question["question"],
                    "score": eval_result["candidate_score"],
                    "notes": eval_result["private_feedback"],
                })
                move_to_next = True
            else:
                follow_up_count += 1
                if eval_result.get("follow_up_reason"):
                    print(f"[Follow-up reason]: {eval_result['follow_up_reason']}")

    
    print(f"\n{'-' * 52}")
    speak(lang_config["outro"], settings, lang_config["tts_lang"], bypass_audio=(args.mode == "text"))

    
    print("\n[Generating your feedback report...]")
    feedback_text = generate_final_feedback(state.feedback_log, args.lang, settings)
    filename = save_report(feedback_text, state.feedback_log, args.lang)

    
    print(
        "\n" + "=" * 52 + "\n"
        "  INTERVIEW COMPLETE - FINAL FEEDBACK\n"
        + "=" * 52
    )
    print(feedback_text)
    print("=" * 52)
    print(f"\n[Full report saved to: {filename}]")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[Interview interrupted by user. Goodbye.]")
        sys.exit(0)
