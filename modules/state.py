from dataclasses import dataclass, field
from typing import Optional

@dataclass
class InterviewState:

    
    current_question_index: int = 0
    current_question: Optional[dict] = None
    translated_questions: Optional[list] = None

    
    conversation_history: list = field(default_factory=list)

    
    feedback_log: list = field(default_factory=list)

    
    language: str = "English"
    stt_lang_code: str = "en-US"
    tts_lang_code: str = "en"

    
    total_questions: int = 0

    
    silence_count: int = 0