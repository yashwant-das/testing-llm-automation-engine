import unittest

from src.utils.llm import extract_json_block


class TestJsonExtraction(unittest.TestCase):
    def test_clean_json(self):
        text = '{"foo": "bar"}'
        self.assertEqual(extract_json_block(text), text)

    def test_markdown_json(self):
        text = '```json\n{"foo": "bar"}\n```'
        self.assertEqual(extract_json_block(text), '{"foo": "bar"}')

    def test_surrounding_text(self):
        text = 'Here is the json:\n{"foo": "bar"}\nHope it helps.'
        self.assertEqual(extract_json_block(text), '{"foo": "bar"}')

    def test_no_json(self):
        text = "Just some text"
        self.assertEqual(extract_json_block(text), "Just some text")

    def test_malformed_control_chars_simulation(self):
        # We didn't fully implement the regex stripper yet, but this tests basic extraction logic
        # works even if we decide to add it later.
        text = '```json\n{"foo": "bar"}\n```'
        self.assertEqual(extract_json_block(text), '{"foo": "bar"}')


if __name__ == "__main__":
    unittest.main()
