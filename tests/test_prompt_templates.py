import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = PROJECT_ROOT / "config" / "prompt-templates"


class PromptTemplateTests(unittest.TestCase):
    def test_story_system_prompt_requires_antagonist_story_structure(self):
        prompt = (TEMPLATES_DIR / "story-system.md").read_text(encoding="utf-8").lower()

        self.assertIn("villain_profile", prompt)
        self.assertIn("antagonist", prompt)
        self.assertIn("villain plan", prompt)
        self.assertIn("first attempt", prompt)
        self.assertIn("twist", prompt)
        self.assertIn("nonviolent", prompt)
        self.assertIn("without violence", prompt)

    def test_story_user_prompt_requests_complex_superhero_villain_conflict(self):
        prompt = (TEMPLATES_DIR / "story-user.md").read_text(encoding="utf-8").lower()

        self.assertIn("antagonistic villain", prompt)
        self.assertIn("clear plan", prompt)
        self.assertIn("clue or twist", prompt)
        self.assertIn("nonviolent resolution", prompt)
        self.assertIn("{{theme_seed}}", prompt)


if __name__ == "__main__":
    unittest.main()
