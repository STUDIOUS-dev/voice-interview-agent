import os

from gtts import gTTS
from pydub import AudioSegment
from pydub.playback import play


def speak(text: str, settings, tts_lang: str = "en", bypass_audio: bool = False) -> None:
    print(f"\n[Interviewer]: {text}")

    if bypass_audio:
        return

    temp_path = "temp_output.mp3"

    try:
        try:
            tts = gTTS(text=text, lang=tts_lang, slow=False)
            tts.save(temp_path)
        except Exception as e:
            print(f"[gTTS synthesis error: {e}. Skipping audio playback - text shown above.]")
            return

        try:
            audio_segment = AudioSegment.from_mp3(temp_path)
            play(audio_segment)

        except Exception as e:
            
            
            print(f"[Audio playback error: {e}. Skipping audio - text shown above.]")  # noqa: BLE001

    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
