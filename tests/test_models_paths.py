import tempfile
import unittest
from datetime import date
from pathlib import Path

from shorts_superheroes.models import Batch, CharacterBible, Scene, StoryPackage
from shorts_superheroes.paths import ensure_batch_layout, make_batch_id


class ModelAndPathTests(unittest.TestCase):
    def test_batch_round_trips_to_json_dict(self):
        batch = Batch(
            batch_id="2026-07-15-001",
            status="ready_for_review",
            image_model="gpt-image-1-mini",
            review_mode="full_validation",
            final_video_paths=["batches/2026-07-15-001/video-01/final/video.mp4"],
        )

        restored = Batch.from_dict(batch.to_dict())

        self.assertEqual(restored.batch_id, "2026-07-15-001")
        self.assertEqual(restored.status, "ready_for_review")
        self.assertEqual(restored.review_mode, "full_validation")
        self.assertEqual(
            restored.final_video_paths,
            ["batches/2026-07-15-001/video-01/final/video.mp4"],
        )

    def test_make_batch_id_uses_iso_date_and_three_digit_sequence(self):
        self.assertEqual(make_batch_id(date(2026, 7, 15), 1), "2026-07-15-001")
        self.assertEqual(make_batch_id(date(2026, 7, 15), 42), "2026-07-15-042")

    def test_story_package_round_trips_to_json_dict(self):
        story = StoryPackage(
            video_id="video-01",
            hero_name="Luma Leap",
            moral="Small honest choices can light the way.",
            target_duration_sec=55,
            character_bible=CharacterBible(
                appearance="A bright childlike hero with a teal cape and star buttons.",
                color_palette=["teal", "gold", "white"],
                original_symbol="a tiny sunrise inside a circle",
                power="making gentle guiding lights",
                recurring_setting="a cozy cloud city library",
                visual_style="soft 3D storybook illustration",
                negative_restrictions=["no Marvel", "no DC", "no existing superhero logos"],
            ),
            script="Luma Leap found a lost moon map and helped everyone share the clues.",
            scenes=[
                Scene(
                    scene_id="scene-01",
                    duration_sec=8,
                    narration="Luma Leap found a glowing map under the library stairs.",
                    image_prompt="Soft 3D storybook image of Luma Leap finding a glowing map.",
                )
            ],
            tiktok_title="Luma Leap and the Moon Map",
            tiktok_description="A gentle superhero bedtime adventure.",
            hashtags=["#kidsstory", "#superhero", "#storytime"],
        )
        payload = story.to_dict()
        self.assertEqual(payload["video_id"], "video-01")
        self.assertEqual(payload["character_bible"]["original_symbol"], "a tiny sunrise inside a circle")
        restored = StoryPackage.from_dict(payload)
        self.assertEqual(restored.scenes[0].scene_id, "scene-01")

    def test_ensure_batch_layout_creates_expected_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layout = ensure_batch_layout(root, "2026-07-15-001", video_count=4)
            self.assertTrue(layout["batch_dir"].is_dir())
            self.assertTrue((layout["batch_dir"] / "video-01" / "images").is_dir())
            self.assertTrue((layout["batch_dir"] / "video-04" / "final").is_dir())
            self.assertFalse((layout["batch_dir"] / "video-05").exists())


if __name__ == "__main__":
    unittest.main()
