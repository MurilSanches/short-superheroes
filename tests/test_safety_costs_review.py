import unittest
from pathlib import Path
import tempfile

from shorts_superheroes.models import CharacterBible, Scene, StoryPackage, VillainProfile
from shorts_superheroes.costs import estimate_story_cost
from shorts_superheroes.review import build_review_markdown, write_story_files
from shorts_superheroes.safety import validate_story_package


def sixty_second_script() -> str:
    return (
        "Luma Leap woke up above the cozy cloud city library and saw a little door glowing softly. "
        "Inside the door was a lost map that seemed nervous because no one had listened to it all morning. "
        "Luma Leap called three friends, asked each one to share an idea, and promised that every voice would matter. "
        "The first friend noticed a golden corner, the second friend found a tiny sunrise mark, "
        "and the third friend remembered a quiet shelf where old maps liked to rest. "
        "When the clues did not fit right away, Luma Leap told the truth and said they needed to slow down. "
        "Together they matched the clues, followed a warm guiding light, and found the map's missing page. "
        "The library doors opened with a gentle sparkle, and every friend felt proud because honest teamwork "
        "helped them solve the mystery without rushing or leaving anyone out. "
        "Before they went home, Luma Leap asked the friends to remember the best part of the day. "
        "One friend said the best part was being heard, another said the best part was telling the truth, "
        "and another said the best part was learning that a small clue can matter when the team is patient. "
        "Luma Leap placed the map back on its shelf, where it glowed like a tiny sunrise, and the friends promised "
        "to use the same honest teamwork the next time a problem felt confusing or too big."
    )


def sample_story(**overrides):
    data = {
        "video_id": "video-01",
        "hero_name": "Luma Leap",
        "moral": "Honesty helps friends solve problems.",
        "target_duration_sec": 65,
        "character_bible": CharacterBible(
            appearance="A small original hero with a teal cape and cloud boots.",
            color_palette=["teal", "gold", "white"],
            original_symbol="a tiny sunrise inside a circle",
            power="making gentle guiding lights",
            recurring_setting="a cozy cloud city library",
            visual_style="soft 3D storybook illustration",
            negative_restrictions=["no existing superhero logos"],
        ),
        "villain_profile": VillainProfile(
            name="The Quiet Shuffler",
            motive="wants every library map to obey only his secret order",
            plan="mixes up glowing map pages so friends cannot find the reading room",
            visual_design="a small original antagonist in a square purple coat with folded-map cuffs",
            nonviolent_methods=["map shuffling", "soft fog", "misleading arrows"],
        ),
        "script": sixty_second_script(),
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

    def test_rejects_story_shorter_than_sixty_seconds(self):
        result = validate_story_package(sample_story(target_duration_sec=59))
        self.assertFalse(result.ok)
        self.assertIn("duration_out_of_range", result.errors)

    def test_rejects_script_too_short_for_sixty_seconds(self):
        result = validate_story_package(sample_story(script="Too short."))
        self.assertFalse(result.ok)
        self.assertIn("script_too_short_for_60_seconds", result.errors)

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
        self.assertIn("**Villain:** The Quiet Shuffler", markdown)
        self.assertIn("**Villain plan:** mixes up glowing map pages", markdown)

    def test_build_review_markdown_rejects_mismatched_estimates(self):
        story = sample_story()
        with self.assertRaisesRegex(ValueError, "stories and estimates"):
            build_review_markdown("2026-07-15-001", [story], [])


if __name__ == "__main__":
    unittest.main()
