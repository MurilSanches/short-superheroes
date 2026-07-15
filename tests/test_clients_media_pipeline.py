import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from shorts_superheroes.clients import (
    DryRunImageClient,
    DryRunStoryClient,
    DryRunTtsClient,
    ElevenLabsTtsClient,
    OpenAIImageClient,
    OpenAIStoryClient,
)
from shorts_superheroes.media import build_render_command, render_video
from shorts_superheroes.models import CharacterBible, Scene, StoryPackage, load_json
from shorts_superheroes.pipeline import draft_batch, generate_audio, generate_images, render_batch, write_batch
from shorts_superheroes.worker import run_stage


def story_payload() -> dict:
    return {
        "video_id": "video-01",
        "hero_name": "Nova Nook",
        "moral": "Sharing ideas helps every friend shine.",
        "target_duration_sec": 54,
        "character_bible": {
            "appearance": "A child hero with a coral jacket and teal boots.",
            "color_palette": ["coral", "teal", "white"],
            "original_symbol": "a bright book inside a circle",
            "power": "turning kind ideas into small guiding lights",
            "recurring_setting": "a sunny rooftop garden library",
            "visual_style": "soft 3D storybook illustration",
            "negative_restrictions": ["no existing superhero logos"],
        },
        "script": "Nova Nook shares a map and helps friends find a lost seed.",
        "scenes": [
            {
                "scene_id": f"scene-{index:02d}",
                "duration_sec": 9,
                "narration": f"Scene {index} with Nova Nook.",
                "image_prompt": f"Original storybook scene {index} with Nova Nook.",
            }
            for index in range(1, 7)
        ],
        "tiktok_title": "Nova Nook and the Shared Seed",
        "tiktok_description": "A gentle story about sharing bright ideas.",
        "hashtags": ["#kidsstory", "#storytime", "#originalhero"],
    }


def story_batch_payload(count: int = 4) -> list[dict]:
    stories = []
    for index in range(1, count + 1):
        story = story_payload()
        story["video_id"] = f"video-{index:02d}"
        if index > 1:
            story["hero_name"] = f"Nova Nook {index}"
        stories.append(story)
    return stories


class ClientTests(unittest.TestCase):
    def test_dry_run_image_client_writes_dry_run_image_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "image-01.txt"
            path = DryRunImageClient().generate_image("A prompt", output)
            self.assertEqual(path, output)
            self.assertIn("DRY RUN IMAGE", output.read_text(encoding="utf-8"))

    def test_dry_run_tts_client_writes_dry_run_audio_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "voice.mp3"
            path = DryRunTtsClient().generate_speech("Narration text", output)
            self.assertEqual(path, output)
            self.assertTrue(output.read_bytes().startswith(b"DRY RUN AUDIO"))

    def test_openai_image_client_builds_expected_request_payload(self):
        captured = {}

        def fake_transport(url, headers, payload):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = payload
            return {"data": [{"b64_json": "RFJZIFJVTg=="}]}

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "image.png"
            client = OpenAIImageClient(
                api_key="sk-test",
                model="gpt-image-1-mini",
                size="1024x1536",
                quality="medium",
                transport=fake_transport,
            )
            client.generate_image("Original hero prompt", output)
            self.assertEqual(captured["url"], "https://api.openai.com/v1/images/generations")
            self.assertEqual(captured["payload"]["model"], "gpt-image-1-mini")
            self.assertEqual(captured["payload"]["size"], "1024x1536")
            self.assertEqual(captured["payload"]["quality"], "medium")
            self.assertEqual(output.read_bytes(), b"DRY RUN")

    def test_dry_run_story_client_returns_four_complete_story_packages(self):
        stories = DryRunStoryClient().generate_stories("kind heroes")

        self.assertEqual(len(stories), 4)
        self.assertEqual([story.video_id for story in stories], ["video-01", "video-02", "video-03", "video-04"])
        for story in stories:
            self.assertGreaterEqual(story.target_duration_sec, 45)
            self.assertLessEqual(story.target_duration_sec, 60)
            self.assertEqual(len(story.scenes), 6)
            self.assertTrue(story.hero_name)
            self.assertTrue(story.tiktok_title)
            self.assertTrue(story.hashtags)

    def test_openai_story_client_builds_response_request_and_parses_stories(self):
        captured = {}

        def fake_transport(url, headers, payload):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = payload
            return {"output_text": json.dumps({"stories": story_batch_payload()})}

        client = OpenAIStoryClient(
            api_key="sk-test",
            model="gpt-4.1-mini",
            transport=fake_transport,
        )
        stories = client.generate_stories(
            theme_seed="sharing ideas",
            system_prompt="Write safe original stories.",
            user_prompt="Create four short stories.",
        )

        self.assertEqual(captured["url"], "https://api.openai.com/v1/responses")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer sk-test")
        self.assertEqual(captured["payload"]["model"], "gpt-4.1-mini")
        self.assertEqual(captured["payload"]["instructions"], "Write safe original stories.")
        self.assertEqual(
            captured["payload"]["input"],
            "Theme seed: sharing ideas\n\nCreate four short stories.",
        )
        self.assertEqual(captured["payload"]["text"]["format"]["type"], "json_schema")
        self.assertTrue(captured["payload"]["text"]["format"]["strict"])
        self.assertIn("stories", captured["payload"]["text"]["format"]["schema"]["properties"])
        self.assertEqual(
            captured["payload"]["text"]["format"]["schema"]["properties"]["stories"]["minItems"],
            4,
        )
        self.assertEqual(
            captured["payload"]["text"]["format"]["schema"]["properties"]["stories"]["maxItems"],
            4,
        )
        self.assertEqual(stories[0].hero_name, "Nova Nook")
        self.assertEqual(stories[0].scenes[0].scene_id, "scene-01")

    def test_openai_story_client_parses_responses_output_content_item(self):
        def fake_transport(url, headers, payload):
            del url, headers, payload
            return {
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps({"stories": story_batch_payload()}),
                            }
                        ]
                    }
                ]
            }

        client = OpenAIStoryClient(api_key="sk-test", transport=fake_transport)

        stories = client.generate_stories("sharing ideas", "system", "user")

        self.assertEqual(len(stories), 4)
        self.assertEqual(stories[0].video_id, "video-01")

    def test_openai_story_client_rejects_story_batches_with_wrong_size(self):
        def fake_transport(url, headers, payload):
            del url, headers, payload
            return {"output_text": json.dumps({"stories": story_batch_payload(3)})}

        client = OpenAIStoryClient(api_key="sk-test", transport=fake_transport)

        with self.assertRaisesRegex(ValueError, "exactly 4 StoryPackage instances"):
            client.generate_stories("sharing ideas", "system", "user")

    def test_elevenlabs_tts_client_uses_transport_and_writes_audio(self):
        captured = {}

        def fake_transport(url, headers, payload):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = payload
            return b"audio bytes"

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "voice.mp3"
            path = ElevenLabsTtsClient(
                api_key="eleven-test",
                voice_id="voice-123",
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128",
                transport=fake_transport,
            ).generate_speech("Narration text", output)
            self.assertEqual(output.read_bytes(), b"audio bytes")

        self.assertEqual(path, output)
        self.assertEqual(
            captured["url"],
            "https://api.elevenlabs.io/v1/text-to-speech/voice-123?output_format=mp3_44100_128",
        )
        self.assertEqual(captured["headers"]["xi-api-key"], "eleven-test")
        self.assertEqual(captured["headers"]["Content-Type"], "application/json")
        self.assertEqual(captured["headers"]["Accept"], "audio/mpeg")
        self.assertEqual(captured["payload"], {
            "text": "Narration text",
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.55, "similarity_boost": 0.75},
        })


class MediaTests(unittest.TestCase):
    def test_build_render_command_targets_vertical_mp4(self):
        images = [Path("scene-01.png"), Path("scene-02.png")]
        command = build_render_command(images, Path("voice.mp3"), Path("final.mp4"), scene_duration_sec=8)
        command_text = " ".join(str(part) for part in command)
        self.assertIn("ffmpeg", command[0])
        self.assertIn("1080:1920", command_text)
        self.assertIn("final.mp4", command_text)

    def test_render_video_dry_run_writes_manifest_instead_of_calling_ffmpeg(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "final.mp4"
            path = render_video([Path("scene-01.txt")], Path("voice.mp3"), output, scene_duration_sec=8, dry_run=True)
            self.assertEqual(path, output)
            self.assertIn("DRY RUN VIDEO", output.read_text(encoding="utf-8"))


def pipeline_story(video_id: str = "video-01") -> StoryPackage:
    return StoryPackage(
        video_id=video_id,
        hero_name="Pebble Pulse",
        moral="Teamwork makes hard tasks feel lighter.",
        target_duration_sec=48,
        character_bible=CharacterBible(
            appearance="A friendly original hero with pebble buttons and a green scarf.",
            color_palette=["green", "cream", "silver"],
            original_symbol="three tiny rounded stones",
            power="making gentle rhythm waves",
            recurring_setting="a sunny town garden",
            visual_style="soft 3D storybook illustration",
            negative_restrictions=["no existing superhero logos"],
        ),
        script="Pebble Pulse helped the garden friends move a heavy seed by sharing the work.",
        scenes=[
            Scene("scene-01", 8, "Pebble Pulse sees a heavy seed.", "Original hero sees a heavy seed."),
            Scene("scene-02", 8, "Friends gather kindly.", "Garden friends gather around."),
            Scene("scene-03", 8, "A gentle rhythm begins.", "Soft rhythm waves in the garden."),
            Scene("scene-04", 8, "Everyone moves together.", "Friends move the seed together."),
            Scene("scene-05", 8, "The seed finds soil.", "The seed lands in warm soil."),
            Scene("scene-06", 8, "A tiny sprout appears.", "A tiny sprout appears happily."),
        ],
        tiktok_title="Pebble Pulse and the Heavy Seed",
        tiktok_description="A gentle superhero teamwork story.",
        hashtags=["#kidsstory", "#storytime", "#superhero"],
    )


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = {
            "video_count": 4,
            "openai": {"image_size": "1024x1536", "image_quality": "medium"},
            "costs": {
                "text_generation_usd_per_batch": 0.02,
                "image_usd_by_model_quality_size": {"gpt-image-1-mini|medium|1024x1536": 0.015},
                "elevenlabs_flash_turbo_usd_per_1000_chars": 0.05,
            },
        }

    def test_pipeline_dry_run_creates_expected_batch_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stories = [pipeline_story(f"video-{index:02d}") for index in range(1, 5)]
            batch_dir = write_batch(root, "2026-07-15-001", stories, self.settings, "gpt-image-1-mini")
            generate_images(batch_dir, DryRunImageClient())
            generate_audio(batch_dir, DryRunTtsClient())
            render_batch(batch_dir, dry_run=True)

            self.assertTrue((batch_dir / "review.md").is_file())
            self.assertTrue((batch_dir / "video-01" / "images" / "scene-01.txt").is_file())
            self.assertTrue((batch_dir / "video-01" / "audio" / "voice.mp3").is_file())
            self.assertTrue((batch_dir / "video-01" / "final" / "video-01.mp4").is_file())
            batch = load_json(batch_dir / "batch.json")
            self.assertEqual(batch["status"], "rendered")
            self.assertEqual(len(batch["final_video_paths"]), 4)

    def test_render_batch_rejects_unexpected_batch_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch_dir = write_batch(
                root,
                "2026-07-15-003",
                [pipeline_story(f"video-{index:02d}") for index in range(1, 5)],
                self.settings,
                "gpt-image-1-mini",
            )

            with self.assertRaisesRegex(ValueError, "expected status 'audio_generated'"):
                render_batch(batch_dir, dry_run=True)

    def test_generate_images_rejects_invalid_loaded_story_before_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch_dir = write_batch(
                root,
                "2026-07-15-004",
                [pipeline_story(f"video-{index:02d}") for index in range(1, 5)],
                self.settings,
                "gpt-image-1-mini",
            )
            story_path = batch_dir / "video-01" / "story.json"
            story_data = load_json(story_path)
            story_data["scenes"] = story_data["scenes"][:5]
            story_path.write_text(json.dumps(story_data), encoding="utf-8")

            class RecordingImageClient:
                def __init__(self):
                    self.calls = []

                def generate_image(self, prompt, output_path):
                    self.calls.append((prompt, output_path))
                    return output_path

            client = RecordingImageClient()
            with self.assertRaisesRegex(ValueError, "scene_count_out_of_range"):
                generate_images(batch_dir, client)

            self.assertEqual(client.calls, [])
            self.assertFalse((batch_dir / "video-01" / "images" / "scene-01.txt").exists())

    def test_draft_batch_passes_theme_seed_and_prompt_contents_to_story_client(self):
        captured = {}

        class RecordingStoryClient:
            def generate_stories(self, theme_seed, system_prompt, user_prompt):
                captured.update(
                    theme_seed=theme_seed,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )
                return [pipeline_story(f"video-{index:02d}") for index in range(1, 5)]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            templates = root / "config" / "prompt-templates"
            templates.mkdir(parents=True)
            (templates / "story-system.md").write_text(
                "Create 4 stories per batch. Keep heroes original.", encoding="utf-8"
            )
            (templates / "story-user.md").write_text(
                "Theme seed: {{theme_seed}}", encoding="utf-8"
            )
            batch_dir = draft_batch(
                root,
                "2026-07-15-005",
                "garden teamwork",
                self.settings,
                RecordingStoryClient(),
                "gpt-image-1-mini",
            )

            self.assertEqual(captured["theme_seed"], "garden teamwork")
            self.assertIn("Create 4 stories per batch.", captured["system_prompt"])
            self.assertIn("Theme seed: garden teamwork", captured["user_prompt"])
            self.assertNotIn("{{theme_seed}}", captured["user_prompt"])
            self.assertEqual(load_json(batch_dir / "batch.json")["status"], "drafted")


    def test_draft_batch_with_dry_run_story_client_creates_four_story_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            templates = root / "config" / "prompt-templates"
            templates.mkdir(parents=True)
            (templates / "story-system.md").write_text("System prompt", encoding="utf-8")
            (templates / "story-user.md").write_text("Theme: {{theme_seed}}", encoding="utf-8")

            batch_dir = draft_batch(
                root,
                "2026-07-15-002",
                "garden teamwork",
                self.settings,
                DryRunStoryClient(),
                "gpt-image-1-mini",
            )

            self.assertTrue((batch_dir / "review.md").is_file())
            self.assertTrue((batch_dir / "video-01" / "story.json").is_file())
            self.assertEqual(len([path for path in batch_dir.glob("video-*") if path.is_dir()]), 4)
            self.assertEqual(load_json(batch_dir / "batch.json")["status"], "drafted")


class WorkerTests(unittest.TestCase):
    def test_run_stage_rejects_unknown_stage(self):
        with self.assertRaisesRegex(ValueError, "unknown stage"):
            run_stage({"stage": "unknown", "batch_dir": "x", "dry_run": True})

    def test_run_stage_dry_run_draft_batch_creates_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            templates = root / "config" / "prompt-templates"
            templates.mkdir(parents=True)
            (templates / "story-system.md").write_text("System prompt", encoding="utf-8")
            (templates / "story-user.md").write_text("Theme: {{theme_seed}}", encoding="utf-8")
            settings_path = root / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "video_count": 4,
                        "review_mode": "full_validation",
                        "openai": {
                            "text_model": "gpt-4.1-mini",
                            "image_model_default": "gpt-image-1-mini",
                            "image_size": "1024x1536",
                            "image_quality": "medium",
                        },
                        "costs": {
                            "text_generation_usd_per_batch": 0.02,
                            "image_usd_by_model_quality_size": {
                                "gpt-image-1-mini|medium|1024x1536": 0.015
                            },
                            "elevenlabs_flash_turbo_usd_per_1000_chars": 0.05,
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = run_stage(
                {
                    "stage": "draft-batch",
                    "batch_id": "2026-07-15-006",
                    "project_root": str(root),
                    "theme_seed": "gentle teamwork",
                    "settings": str(settings_path),
                    "dry_run": True,
                }
            )

            batch_dir = Path(result["batch_dir"])
            self.assertEqual(result, {"ok": True, "stage": "draft-batch", "batch_dir": str(batch_dir)})
            self.assertTrue((batch_dir / "review.md").is_file())
            self.assertEqual(load_json(batch_dir / "batch.json")["status"], "drafted")

    def test_run_stage_real_draft_uses_openai_story_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings_path = root / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "openai": {
                            "text_model": "gpt-4.1-mini",
                            "image_model_default": "gpt-image-1-mini",
                        }
                    }
                ),
                encoding="utf-8",
            )
            batch_dir = root / "batches" / "2026-07-15-007"

            with (
                patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}),
                patch("shorts_superheroes.worker.OpenAIStoryClient") as client_type,
                patch("shorts_superheroes.worker.draft_batch", return_value=batch_dir) as draft,
            ):
                result = run_stage(
                    {
                        "stage": "draft-batch",
                        "batch_id": "2026-07-15-007",
                        "project_root": str(root),
                        "settings": str(settings_path),
                        "dry_run": False,
                    }
                )

            client_type.assert_called_once_with(api_key="sk-test", model="gpt-4.1-mini")
            draft.assert_called_once()
            self.assertEqual(result, {"ok": True, "stage": "draft-batch", "batch_dir": str(batch_dir)})


if __name__ == "__main__":
    unittest.main()
