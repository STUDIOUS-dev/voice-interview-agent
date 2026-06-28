import json
import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_PATH = os.path.join(PROJECT_ROOT, "qa_dataset.json")


class TestDataset(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.dataset_exists = os.path.exists(DATASET_PATH)
        if cls.dataset_exists:
            with open(DATASET_PATH, "r", encoding="utf-8") as f:
                cls.data = json.load(f)
        else:
            cls.data = []

    def test_file_exists(self):
        self.assertTrue(
            self.dataset_exists,
            f"qa_dataset.json not found at: {DATASET_PATH}"
        )

    def test_minimum_entries(self):
        self.assertGreaterEqual(
            len(self.data),
            5,
            f"Expected at least 5 questions, found {len(self.data)}."
        )

    def test_required_fields(self):
        required = {"id", "question", "ideal_answer"}
        for i, entry in enumerate(self.data):
            with self.subTest(entry_index=i):
                missing = required - set(entry.keys())
                self.assertEqual(
                    missing,
                    set(),
                    f"Entry {i} is missing fields: {missing}. Entry: {entry}"
                )

    def test_no_duplicate_ids(self):
        ids = [entry["id"] for entry in self.data if "id" in entry]
        self.assertEqual(
            len(ids),
            len(set(ids)),
            f"Duplicate IDs found: {[x for x in ids if ids.count(x) > 1]}"
        )

    def test_answer_length(self):
        for i, entry in enumerate(self.data):
            if "ideal_answer" not in entry:
                continue  
            with self.subTest(entry_index=i, question_id=entry.get("id")):
                self.assertGreaterEqual(
                    len(entry["ideal_answer"]),
                    20,
                    f"Entry {i} (id={entry.get('id')}) has a too-short ideal_answer: "
                    f"\"{entry['ideal_answer'][:50]}...\""
                )


if __name__ == "__main__":
    unittest.main()
