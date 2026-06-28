import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules.state import InterviewState


def _make_mock_gemini_response(text: str) -> MagicMock:
    mock_response = MagicMock()
    mock_response.text = text
    return mock_response


def _make_state() -> InterviewState:
    state = InterviewState(
        language="English",
        stt_lang_code="en-US",
        tts_lang_code="en",
    )
    state.current_question = {
        "question": "What is the difference between a list and a tuple?",
        "ideal_answer": "Lists are mutable, tuples are immutable.",
    }
    return state


def _make_settings() -> MagicMock:
    settings = MagicMock()
    settings.llm_model = "gemini-2.0-flash"
    settings.max_retries = 3
    return settings


class TestEvaluator(unittest.TestCase):

    @patch("modules.evaluator.time.sleep", return_value=None)
    @patch("modules.evaluator.genai.GenerativeModel")
    def test_parse_valid_json(self, mock_model_class, mock_sleep):
        from modules.evaluator import evaluate_response

        valid_payload = {
            "spoken_reply": "Good answer! You covered the key difference.",
            "move_to_next": True,
            "candidate_score": 4,
            "private_feedback": "Candidate clearly understood mutability.",
            "follow_up_reason": "",
        }

        mock_instance = MagicMock()
        mock_instance.generate_content.return_value = _make_mock_gemini_response(
            json.dumps(valid_payload)
        )
        mock_model_class.return_value = mock_instance

        result = evaluate_response(
            user_text="Lists are mutable and tuples are immutable.",
            state=_make_state(),
            settings=_make_settings(),
        )

        self.assertEqual(result["spoken_reply"], valid_payload["spoken_reply"])
        self.assertTrue(result["move_to_next"])
        self.assertEqual(result["candidate_score"], 4)
        self.assertEqual(result["private_feedback"], valid_payload["private_feedback"])
        self.assertIn("follow_up_reason", result)

    @patch("modules.evaluator.time.sleep", return_value=None)
    @patch("modules.evaluator.genai.GenerativeModel")
    def test_parse_invalid_json(self, mock_model_class, mock_sleep):
        from modules.evaluator import evaluate_response, _SAFE_DEFAULT

        mock_instance = MagicMock()
        mock_instance.generate_content.return_value = _make_mock_gemini_response(
            "This is not valid JSON at all!!!"
        )
        mock_model_class.return_value = mock_instance

        result = evaluate_response(
            user_text="I don't know the answer.",
            state=_make_state(),
            settings=_make_settings(),
        )

        
        self.assertEqual(mock_instance.generate_content.call_count, 2)

        
        self.assertEqual(result["move_to_next"], _SAFE_DEFAULT["move_to_next"])
        self.assertEqual(result["candidate_score"], _SAFE_DEFAULT["candidate_score"])
        self.assertEqual(result["private_feedback"], _SAFE_DEFAULT["private_feedback"])

    @patch("modules.evaluator.time.sleep", return_value=None)
    @patch("modules.evaluator.genai.GenerativeModel")
    def test_score_clipping(self, mock_model_class, mock_sleep):
        from modules.evaluator import evaluate_response

        mock_instance = MagicMock()
        mock_model_class.return_value = mock_instance

        
        payload_high = {
            "spoken_reply": "Excellent answer!",
            "move_to_next": True,
            "candidate_score": 7,
            "private_feedback": "Top performer.",
            "follow_up_reason": "",
        }
        mock_instance.generate_content.return_value = _make_mock_gemini_response(
            json.dumps(payload_high)
        )
        result = evaluate_response("perfect answer", _make_state(), _make_settings())
        self.assertEqual(result["candidate_score"], 5, "Score 7 should clip to 5")

        
        payload_low = {
            "spoken_reply": "Let us move on.",
            "move_to_next": True,
            "candidate_score": 0,
            "private_feedback": "No relevant content.",
            "follow_up_reason": "",
        }
        mock_instance.generate_content.return_value = _make_mock_gemini_response(
            json.dumps(payload_low)
        )
        result = evaluate_response("wrong answer", _make_state(), _make_settings())
        self.assertEqual(result["candidate_score"], 1, "Score 0 should clip to 1")

    @patch("modules.evaluator.time.sleep", return_value=None)
    @patch("modules.evaluator.genai.GenerativeModel")
    def test_private_feedback_present(self, mock_model_class, mock_sleep):
        from modules.evaluator import evaluate_response

        minimal_payload = {
            "spoken_reply": "Thanks for your answer.",
            "move_to_next": True,
            "candidate_score": 3,
            "private_feedback": "Average response.",
            "follow_up_reason": "",
        }

        mock_instance = MagicMock()
        mock_instance.generate_content.return_value = _make_mock_gemini_response(
            json.dumps(minimal_payload)
        )
        mock_model_class.return_value = mock_instance

        result = evaluate_response("some answer", _make_state(), _make_settings())

        self.assertIn("private_feedback", result)
        self.assertIsInstance(result["private_feedback"], str)
        self.assertGreater(len(result["private_feedback"]), 0)


if __name__ == "__main__":
    unittest.main()
