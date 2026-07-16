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

    def test_story_prompts_request_script_buffer_above_validation_minimum(self):
        combined = "\n".join(
            [
                (TEMPLATES_DIR / "story-system.md").read_text(encoding="utf-8").lower(),
                (TEMPLATES_DIR / "story-user.md").read_text(encoding="utf-8").lower(),
            ]
        )

        self.assertIn("1300 to 1600 characters", combined)
        self.assertIn("expand any script below 1300 characters", combined)
        self.assertIn("180 to 230 words", combined)

    def test_story_system_prompt_requires_exactly_six_scenes(self):
        prompt = (TEMPLATES_DIR / "story-system.md").read_text(encoding="utf-8").lower()

        self.assertIn("exactly 6 scenes", prompt)
        self.assertNotIn("6 to 8 scenes", prompt)

    def test_theme_prompts_request_varied_original_superhero_villain_seed(self):
        combined = "\n".join(
            [
                (TEMPLATES_DIR / "theme-system.md").read_text(encoding="utf-8").lower(),
                (TEMPLATES_DIR / "theme-user.md").read_text(encoding="utf-8").lower(),
            ]
        )

        self.assertIn("theme_seed", combined)
        self.assertIn("variety", combined)
        self.assertIn("original superhero", combined)
        self.assertIn("villain", combined)
        self.assertIn("avoid repeating", combined)
        self.assertIn("strict json", combined)


if __name__ == "__main__":
    unittest.main()
