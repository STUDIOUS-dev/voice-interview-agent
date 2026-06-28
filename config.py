import os
import sys
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:

    
    google_api_key: str

    
    dataset_path: str = "qa_dataset.json"

    
    llm_model: str = "gemini-3.5-flash"

    
    silence_timeout: int = 10
    phrase_limit: int = 15

    
    max_retries: int = 3


def load_settings() -> Settings:
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()

    if not api_key:
        print(
            "\nERROR: GOOGLE_API_KEY not found.\n"
            "  1. Copy .env.example to .env\n"
            "  2. Get a FREE key from: https://aistudio.google.com/app/apikey\n"
            "  3. Replace the placeholder in .env with your real key.\n"
            "  4. Re-run the program.\n"
        )
        sys.exit(1)

    return Settings(google_api_key=api_key)
