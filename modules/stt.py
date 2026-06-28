import sys
import time

import speech_recognition as sr


def calibrate_microphone() -> sr.Recognizer:
    recognizer = sr.Recognizer()

    try:
        with sr.Microphone() as source:
            print("[Calibrating microphone for ambient noise... please wait]")
            recognizer.adjust_for_ambient_noise(source, duration=1.5)
        print("[Microphone ready]")
    except OSError as e:
        print(
            f"\nERROR: Microphone not accessible.\n"
            f"  Details: {e}\n"
            f"  Suggestions:\n"
            f"    - Check that a microphone is connected.\n"
            f"    - Grant microphone permission to Terminal/Python in system settings.\n"
            f"    - On Windows: Settings → Privacy → Microphone → Allow apps access.\n"
            f"    - Alternatively, run with --mode text to bypass the microphone.\n"
        )
        sys.exit(1)
    except sr.RequestError as e:
        print(
            f"\nERROR: Microphone system error: {e}\n"
            f"  Run with --mode text to bypass the microphone.\n"
        )
        sys.exit(1)

    return recognizer


def record_and_transcribe(
    recognizer: sr.Recognizer,
    stt_lang_code: str,
    settings,
) -> dict:
    try:
        with sr.Microphone() as source:
            print("\n[Listening... speak your answer]")
            audio = recognizer.listen(
                source,
                timeout=settings.silence_timeout,
                phrase_time_limit=settings.phrase_limit,
            )
    except sr.WaitTimeoutError:
        return {"text": "", "timed_out": True, "empty": False, "api_error": False}

    print("[Processing your response...]")

    for attempt in range(1, settings.max_retries + 1):
        try:
            text = recognizer.recognize_google(audio, language=stt_lang_code)

            if not text.strip():
                return {"text": "", "timed_out": False, "empty": True, "api_error": False}

            print(f"[You said]: {text}")
            return {"text": text, "timed_out": False, "empty": False, "api_error": False}

        except sr.UnknownValueError:
            return {"text": "", "timed_out": False, "empty": True, "api_error": False}

        except sr.RequestError as e:
            if attempt < settings.max_retries:
                wait_seconds = 2 ** attempt
                print(
                    f"[Google STT error (attempt {attempt}/{settings.max_retries}): "
                    f"{e}. Retrying in {wait_seconds}s...]"
                )
                time.sleep(wait_seconds)
            else:
                print(
                    f"[Google STT failed after {settings.max_retries} attempts: {e}]"
                )
                return {"text": "", "timed_out": False, "empty": False, "api_error": True}

    return {"text": "", "timed_out": False, "empty": False, "api_error": True}
