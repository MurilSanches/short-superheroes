import unittest
from pathlib import Path
import tempfile

from shorts_superheroes.models import CharacterBible, Scene, StoryPackage
from shorts_superheroes.costs import estimate_story_cost
from shorts_superheroes.review import build_review_markdown, write_story_files
from shorts_superheroes.safety import validate_story_package


def sample_story(**overrides):
    data = {
        "video_id": "video-01",
        "hero_name": "Luma Leap",
        "moral": "Honesty helps friends solve problems.",
        "target_duration_sec": 55,
        "character_bible": CharacterBible(
            appearance="A small original hero with a teal cape and cloud boots.",
            color_palette=["teal", "gold", "white"],
            original_symbol="a tiny sunrise inside a circle",
            power="making gentle guiding lights",
            recurring_setting="a cozy cloud city library",
            visual_style="soft 3D storybook illustration",
            negative_restrictions=["no existing superhero logos"],
        ),
        "script": "Luma Leap finds a lost map, tells the truth, and helps friends share clues.",
        "scenes": [
            Scene("scene-01", 8, "Luma Leap finds a map.", "A soft storybook scene with an original hero."),
            Scene("scene-02", 8, "Friends share clues.", "Original cloud city friends in a library."),
            Scene("scene-03", 8, "A gentle light appears.", "A warm guiding light over books."),
            Scene("scene-04", 8, "They tell the truth.", "Friends smiling and telling the truth."),
            Scene("scene-05", 8, "The map opens.", "The map opens with soft gold light."),
            Scene("scene-06", 8, "Everyone celebrates kindly.", "A cozy library celebration."),
        ],
        "tiktok_title": "Luma Leap and the Honest Map",
        "tiktok_description": "A gentle superhero story about honesty.",
        "hashtags": ["#kidsstory", "#storytime", "#superhero"],
    }
    data.update(overrides)
    return StoryPackage(**data)


class SafetyTests(unittest.TestCase):
    def test_valid_story_passes(self):
        result = validate_story_package(sample_story())
        self.assertTrue(result.ok)
        self.assertEqual(result.errors, [])

    def test_rejects_known_ip_terms(self):
        result = validate_story_package(sample_story(hero_name="Spider Boy"))
        self.assertFalse(result.ok)
        self.assertIn("known_ip_term: spider", result.errors)

    def test_rejects_too_few_scenes(self):
        story = sample_story()
        story.scenes = story.scenes[:5]
        result = validate_story_package(story)
        self.assertFalse(result.ok)
        self.assertIn("scene_count_out_of_range", result.errors)

    def test_rejects_personal_data_call_to_action(self):
        story = sample_story(script="Tell me your age and school in the comments.")
        result = validate_story_package(story)
        self.assertFalse(result.ok)
        self.assertIn("child_personal_data_prompt", result.errors)


class CostAndReviewTests(unittest.TestCase):
    def test_estimate_story_cost_uses_image_count_and_script_characters(self):
        story = sample_story()
        settings = {
            "costs": {
                "text_generation_usd_per_batch": 0.02,
                "image_usd_by_model_quality_size": {
                    "gpt-image-1-mini|medium|1024x1536": 0.015
                },
                "elevenlabs_flash_turbo_usd_per_1000_chars": 0.05,
            },
            "openai": {"image_size": "1024x1536", "image_quality": "medium"},
            "video_count": 4,
        }
        estimate = estimate_story_cost(story, settings, "gpt-image-1-mini")
        self.assertEqual(estimate.images_usd, 0.09)
        self.assertGreater(estimate.voice_usd, 0)
        self.assertEqual(estimate.text_usd, 0.005)

    def test_estimate_story_cost_rejects_non_mvp_video_count(self):
        story = sample_story()
        settings = {
            "costs": {
                "text_generation_usd_per_batch": 0.02,
                "image_usd_by_model_quality_size": {
                    "gpt-image-1-mini|medium|1024x1536": 0.015
                },
                "elevenlabs_flash_turbo_usd_per_1000_chars": 0.05,
            },
            "openai": {"image_size": "1024x1536", "image_quality": "medium"},
            "video_count": 3,
        }
        with self.assertRaisesRegex(ValueError, "exactly 4 videos"):
            estimate_story_cost(story, settings, "gpt-image-1-mini")

    def test_write_story_files_creates_script_metadata_and_story_json(self):
        story = sample_story()
        with tempfile.TemporaryDirectory() as tmp:
            video_dir = Path(tmp)
            write_story_files(video_dir, story)
            self.assertTrue((video_dir / "story.json").is_file())
            self.assertIn("Luma Leap", (video_dir / "script.txt").read_text(encoding="utf-8"))
            metadata = (video_dir / "metadata.txt").read_text(encoding="utf-8")
            self.assertIn("#kidsstory", metadata)

    def test_build_review_markdown_contains_checkpoints_and_costs(self):
        story = sample_story()
        settings = {
            "costs": {
                "text_generation_usd_per_batch": 0.02,
                "image_usd_by_model_quality_size": {
                    "gpt-image-1-mini|medium|1024x1536": 0.015
                },
                "elevenlabs_flash_turbo_usd_per_1000_chars": 0.05,
            },
            "openai": {"image_size": "1024x1536", "image_quality": "medium"},
            "video_count": 4,
        }
        estimate = estimate_story_cost(story, settings, "gpt-image-1-mini")
        markdown = build_review_markdown("2026-07-15-001", [story], [estimate])
        self.assertIn("# Batch 2026-07-15-001 Review", markdown)
        self.assertIn("- [ ] Scripts and image prompts approved", markdown)
        self.assertIn("Estimated total", markdown)

    def test_build_review_markdown_rejects_mismatched_estimates(self):
        story = sample_story()
        with self.assertRaisesRegex(ValueError, "stories and estimates"):
            build_review_markdown("2026-07-15-001", [story], [])


if __name__ == "__main__":
    unittest.main()
