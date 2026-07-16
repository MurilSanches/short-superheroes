import json
import io
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from shorts_superheroes.clients import (
    DryRunImageClient,
    DryRunStoryClient,
    DryRunTtsClient,
    ElevenLabsTtsClient,
    OpenAIImageClient,
    OpenAIStoryClient,
    OpenAIThemeSeedClient,
    default_json_transport,
)
from shorts_superheroes.media import build_render_command, render_video
from shorts_superheroes.models import CharacterBible, Scene, StoryPackage, VillainProfile, load_json
from shorts_superheroes.pipeline import draft_batch, generate_audio, generate_images, render_batch, write_batch
from shorts_superheroes.cli import main as cli_main
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
        "villain_profile": {
            "name": "The Sign Swapper",
            "motive": "wants every garden path to follow only his rules",
            "plan": "quietly swaps every helpful sign so friends walk in circles",
            "visual_design": "a tiny original trickster in a striped raincoat with paper-arrow cuffs",
            "nonviolent_methods": ["confusing signs", "paper fog", "mismatched arrows"],
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

    def test_default_json_transport_includes_http_error_body(self):
        from urllib.error import HTTPError

        error_body = b'{"error":{"message":"Invalid image prompt","type":"invalid_request_error"}}'
        error = HTTPError(
            "https://api.openai.com/v1/images/generations",
            400,
            "Bad Request",
            {},
            io.BytesIO(error_body),
        )

        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "Invalid image prompt"):
                default_json_transport("https://api.openai.com/v1/images/generations", {}, {"prompt": "x"})

    def test_dry_run_story_client_returns_four_complete_story_packages(self):
        stories = DryRunStoryClient().generate_stories("kind heroes")

        self.assertEqual(len(stories), 4)
        self.assertEqual([story.video_id for story in stories], ["video-01", "video-02", "video-03", "video-04"])
        for story in stories:
            self.assertGreaterEqual(story.target_duration_sec, 60)
            self.assertLessEqual(story.target_duration_sec, 75)
            self.assertGreaterEqual(len(story.script), 900)
            self.assertEqual(len(story.scenes), 6)
            self.assertTrue(story.hero_name)
            self.assertTrue(story.villain_profile.name)
            self.assertTrue(story.villain_profile.plan)
            self.assertIn(story.villain_profile.name, story.script)
            self.assertTrue(
                any(story.villain_profile.name in scene.image_prompt for scene in story.scenes),
                "dry-run image prompts should include the antagonist for visual continuity",
            )
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
        story_schema = captured["payload"]["text"]["format"]["schema"]["properties"]["stories"]["items"]
        self.assertIn("villain_profile", story_schema["required"])
        villain_schema = story_schema["properties"]["villain_profile"]
        self.assertEqual(
            villain_schema["required"],
            ["name", "motive", "plan", "visual_design", "nonviolent_methods"],
        )
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

    def test_openai_theme_seed_client_builds_request_and_parses_seed(self):
        captured = {}

        def fake_transport(url, headers, payload):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = payload
            return {"output_text": json.dumps({"theme_seed": "moon garden hero versus clockwork fog villain"})}

        client = OpenAIThemeSeedClient(api_key="sk-test", model="gpt-4.1-mini", transport=fake_transport)

        theme_seed = client.generate_theme_seed("Theme system prompt", "Theme user prompt")

        self.assertEqual(theme_seed, "moon garden hero versus clockwork fog villain")
        self.assertEqual(captured["url"], "https://api.openai.com/v1/responses")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer sk-test")
        self.assertEqual(captured["payload"]["model"], "gpt-4.1-mini")
        self.assertEqual(captured["payload"]["instructions"], "Theme system prompt")
        self.assertEqual(captured["payload"]["input"], "Theme user prompt")
        self.assertEqual(captured["payload"]["text"]["format"]["schema"]["required"], ["theme_seed"])

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
    def test_resolve_ffmpeg_executable_falls_back_to_imageio_ffmpeg(self):
        fake_imageio_ffmpeg = SimpleNamespace(get_ffmpeg_exe=lambda: r"C:\tools\ffmpeg.exe")

        with (
            patch("shutil.which", return_value=None),
            patch.dict(sys.modules, {"imageio_ffmpeg": fake_imageio_ffmpeg}),
        ):
            from shorts_superheroes import media

            self.assertEqual(media.resolve_ffmpeg_executable(), r"C:\tools\ffmpeg.exe")

    def test_build_render_command_uses_resolved_ffmpeg_executable(self):
        with patch("shorts_superheroes.media.resolve_ffmpeg_executable", return_value="custom-ffmpeg", create=True):
            command = build_render_command([Path("scene-01.png")], Path("voice.mp3"), Path("final.mp4"), scene_duration_sec=8)

        self.assertEqual(command[0], "custom-ffmpeg")

    def test_build_render_command_targets_vertical_mp4(self):
        images = [Path("scene-01.png"), Path("scene-02.png")]
        command = build_render_command(images, Path("voice.mp3"), Path("final.mp4"), scene_duration_sec=8)
        command_text = " ".join(str(part) for part in command)
        self.assertIn("ffmpeg", command[0])
        self.assertIn("1080:1920", command_text)
        self.assertIn("loudnorm=I=-16:TP=-1.5:LRA=11", command_text)
        self.assertIn("-ac 2", command_text)
        self.assertIn("-ar 48000", command_text)
        self.assertIn("-b:a 192k", command_text)
        self.assertIn("final.mp4", command_text)

    def test_render_video_dry_run_writes_manifest_instead_of_calling_ffmpeg(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "final.mp4"
            path = render_video([Path("scene-01.txt")], Path("voice.mp3"), output, scene_duration_sec=8, dry_run=True)
            self.assertEqual(path, output)
            self.assertIn("DRY RUN VIDEO", output.read_text(encoding="utf-8"))

    def test_render_video_rejects_output_without_audio_stream(self):
        render_result = SimpleNamespace(returncode=0, stderr="", stdout="")
        probe_result = SimpleNamespace(
            returncode=1,
            stdout="",
            stderr=(
                "Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'final.mp4':\n"
                "  Stream #0:0: Video: h264, yuv420p, 1080x1920\n"
                "At least one output file must be specified\n"
            ),
        )
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("shorts_superheroes.media.resolve_ffmpeg_executable", return_value="ffmpeg"),
            patch("shorts_superheroes.media.subprocess.run", side_effect=[render_result, probe_result]),
        ):
            output = Path(tmp) / "final.mp4"
            with self.assertRaisesRegex(RuntimeError, "missing audio stream"):
                render_video([Path("scene-01.png")], Path("voice.mp3"), output, scene_duration_sec=8, dry_run=False)


def pipeline_story(video_id: str = "video-01") -> StoryPackage:
    script = (
        "Pebble Pulse noticed a heavy glowing seed beside the garden path. "
        "First, Pebble Pulse took a slow breath and asked every friend what they could do safely. "
        "The tiny beetles offered to clear pebbles, the cloud birds brought soft shade, "
        "and the flower twins marked a gentle path through the grass. "
        "Pebble Pulse used calm rhythm waves, not to push anyone, but to help the team move together. "
        "When the seed rolled a little too fast, the friends paused, listened, and made a kinder plan. "
        "Step by step, they carried the seed to warm soil near the sunny fence. "
        "By the end, the seed settled in, a little sprout waved hello, "
        "and everyone learned that teamwork makes hard tasks feel lighter. "
        "Pebble Pulse did not say the mission was easy; instead, the hero said it became possible because every helper mattered. "
        "The beetles felt proud of their careful clearing, the birds felt proud of their cool shade, "
        "and the flower twins felt proud that their path markers kept everyone calm. "
        "That evening, the whole garden remembered the lesson whenever another friend needed help with something heavy, "
        "because shared work, kind words, and patient listening had turned a hard moment into a bright team victory."
    )
    return StoryPackage(
        video_id=video_id,
        hero_name="Pebble Pulse",
        moral="Teamwork makes hard tasks feel lighter.",
        target_duration_sec=66,
        character_bible=CharacterBible(
            appearance="A friendly original hero with pebble buttons and a green scarf.",
            color_palette=["green", "cream", "silver"],
            original_symbol="three tiny rounded stones",
            power="making gentle rhythm waves",
            recurring_setting="a sunny town garden",
            visual_style="soft 3D storybook illustration",
            negative_restrictions=["no existing superhero logos"],
        ),
        villain_profile=VillainProfile(
            name="The Pebble Pusher",
            motive="wants the garden path to belong only to him",
            plan="rolls glowing seeds into the wrong places so friends cannot share the path",
            visual_design="a small original antagonist with square goggles and a coat of flat stones",
            nonviolent_methods=["rolling seeds", "blocking paths", "muddy sign tricks"],
        ),
        script=script,
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
            self.assertTrue((batch_dir / "video-01" / "images" / "scene-01.png").is_file())
            story = load_json(batch_dir / "video-01" / "story.json")
            self.assertTrue(story["scenes"][0]["image_path"].endswith("scene-01.png"))
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
            self.assertFalse((batch_dir / "video-01" / "images" / "scene-01.png").exists())

    def test_generate_images_skips_existing_image_files_when_resuming(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stories = [pipeline_story(f"video-{index:02d}") for index in range(1, 5)]
            batch_dir = write_batch(root, "2026-07-16-resume", stories, self.settings, "gpt-image-1-mini")
            existing = batch_dir / "video-01" / "images" / "scene-01.png"
            existing.write_bytes(b"existing image")

            class RecordingImageClient:
                def __init__(self):
                    self.calls = []

                def generate_image(self, prompt, output_path):
                    self.calls.append((prompt, output_path))
                    output_path.write_bytes(b"new image")
                    return output_path

            client = RecordingImageClient()
            generate_images(batch_dir, client)

            self.assertEqual(existing.read_bytes(), b"existing image")
            self.assertNotIn(existing, [output_path for _, output_path in client.calls])
            self.assertTrue((batch_dir / "video-01" / "images" / "scene-02.png").is_file())

    def test_generate_images_reports_story_scene_and_prompt_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stories = [pipeline_story(f"video-{index:02d}") for index in range(1, 5)]
            batch_dir = write_batch(root, "2026-07-16-image-error", stories, self.settings, "gpt-image-1-mini")

            class FailingImageClient:
                def generate_image(self, prompt, output_path):
                    del output_path
                    raise RuntimeError("HTTP 400 Bad Request: policy body")

            with self.assertRaisesRegex(RuntimeError, "video-01/scene-01"):
                generate_images(batch_dir, FailingImageClient())

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

    def test_draft_batch_retries_story_generation_with_validation_feedback(self):
        captured_user_prompts = []

        class RetryingStoryClient:
            def generate_stories(self, theme_seed, system_prompt, user_prompt):
                del theme_seed, system_prompt
                captured_user_prompts.append(user_prompt)
                if len(captured_user_prompts) == 1:
                    invalid = pipeline_story("video-01")
                    invalid.script = "Too short."
                    return [invalid] + [pipeline_story(f"video-{index:02d}") for index in range(2, 5)]
                return [pipeline_story(f"video-{index:02d}") for index in range(1, 5)]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            templates = root / "config" / "prompt-templates"
            templates.mkdir(parents=True)
            (templates / "story-system.md").write_text("System prompt", encoding="utf-8")
            (templates / "story-user.md").write_text("Theme seed: {{theme_seed}}", encoding="utf-8")

            batch_dir = draft_batch(
                root,
                "2026-07-16-010",
                "bedtime stars",
                self.settings,
                RetryingStoryClient(),
                "gpt-image-1-mini",
            )

            self.assertEqual(load_json(batch_dir / "batch.json")["status"], "drafted")
            self.assertEqual(len(captured_user_prompts), 2)
            self.assertIn("Previous story batch failed validation", captured_user_prompts[1])
            self.assertIn("script_too_short_for_60_seconds", captured_user_prompts[1])


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

    def test_run_stage_real_generate_images_uses_openai_image_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings_path = root / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "openai": {
                            "image_model_default": "gpt-image-1-mini",
                            "image_size": "1024x1536",
                            "image_quality": "medium",
                        }
                    }
                ),
                encoding="utf-8",
            )
            batch_dir = root / "batches" / "2026-07-15-008"

            with (
                patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}),
                patch("shorts_superheroes.worker.OpenAIImageClient") as client_type,
                patch("shorts_superheroes.worker.generate_images") as generate,
            ):
                result = run_stage(
                    {
                        "stage": "generate-images",
                        "batch_dir": str(batch_dir),
                        "settings": str(settings_path),
                        "dry_run": False,
                    }
                )

            client_type.assert_called_once_with(
                api_key="sk-test",
                model="gpt-image-1-mini",
                size="1024x1536",
                quality="medium",
            )
            generate.assert_called_once_with(batch_dir, client_type.return_value)
            self.assertEqual(result, {"ok": True, "stage": "generate-images", "batch_dir": str(batch_dir)})

    def test_run_stage_real_generate_audio_uses_elevenlabs_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings_path = root / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "elevenlabs": {
                            "voice_id": "voice-123",
                            "model_id": "eleven_multilingual_v2",
                            "output_format": "mp3_44100_128",
                        }
                    }
                ),
                encoding="utf-8",
            )
            batch_dir = root / "batches" / "2026-07-15-009"

            with (
                patch.dict(os.environ, {"ELEVENLABS_API_KEY": "eleven-test"}),
                patch("shorts_superheroes.worker.ElevenLabsTtsClient") as client_type,
                patch("shorts_superheroes.worker.generate_audio") as generate,
            ):
                result = run_stage(
                    {
                        "stage": "generate-audio",
                        "batch_dir": str(batch_dir),
                        "settings": str(settings_path),
                        "dry_run": False,
                    }
                )

            client_type.assert_called_once_with(
                api_key="eleven-test",
                voice_id="voice-123",
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128",
            )
            generate.assert_called_once_with(batch_dir, client_type.return_value)
            self.assertEqual(result, {"ok": True, "stage": "generate-audio", "batch_dir": str(batch_dir)})

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


class CliTests(unittest.TestCase):
    def test_run_full_batch_dry_run_prints_final_video_paths(self):
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
                        "elevenlabs": {
                            "voice_id": "voice-123",
                            "model_id": "eleven_flash_v2_5",
                            "output_format": "mp3_44100_128",
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

            argv = [
                "shorts_superheroes.cli",
                "--settings",
                str(settings_path),
                "run-full-batch",
                "--batch-id",
                "2026-07-16-cli-test",
                "--project-root",
                str(root),
                "--theme-seed",
                "bedtime star mystery",
                "--dry-run",
            ]

            with (
                patch.object(sys, "argv", argv),
                patch.object(sys, "stderr", io.StringIO()),
                patch("builtins.print") as print_call,
            ):
                exit_code = cli_main()

            self.assertEqual(exit_code, 0)
            printed_paths = [call.args[0] for call in print_call.call_args_list]
            self.assertEqual(len(printed_paths), 4)
            for index, printed_path in enumerate(printed_paths, start=1):
                self.assertTrue(printed_path.endswith(f"video-{index:02d}.mp4"))
                self.assertTrue(Path(printed_path).is_file())

    def test_run_full_batch_accepts_no_theme_with_generated_batch_id(self):
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
                        "project_root": str(root),
                        "video_count": 4,
                        "review_mode": "full_validation",
                        "openai": {
                            "text_model": "gpt-4.1-mini",
                            "image_model_default": "gpt-image-1-mini",
                            "image_size": "1024x1536",
                            "image_quality": "medium",
                        },
                        "elevenlabs": {
                            "voice_id": "voice-123",
                            "model_id": "eleven_flash_v2_5",
                            "output_format": "mp3_44100_128",
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

            argv = [
                "shorts_superheroes.cli",
                "--settings",
                str(settings_path),
                "run-full-batch",
                "--dry-run",
            ]

            with (
                patch.object(sys, "argv", argv),
                patch("shorts_superheroes.cli.date") as date_type,
                patch("shorts_superheroes.cli.random.choice", return_value="clockwork library villain mystery"),
                patch.object(sys, "stderr", io.StringIO()),
                patch("builtins.print") as print_call,
            ):
                date_type.today.return_value.isoformat.return_value = "2026-07-16"
                exit_code = cli_main()

            self.assertEqual(exit_code, 0)
            batch_dir = root / "batches" / "2026-07-16-001"
            batch = load_json(batch_dir / "batch.json")
            self.assertEqual(batch["theme_seed"], "clockwork library villain mystery")
            printed_paths = [call.args[0] for call in print_call.call_args_list]
            self.assertEqual(len(printed_paths), 4)

    def test_run_full_batch_writes_progress_logs_to_stderr(self):
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
                        "elevenlabs": {
                            "voice_id": "voice-123",
                            "model_id": "eleven_flash_v2_5",
                            "output_format": "mp3_44100_128",
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

            argv = [
                "shorts_superheroes.cli",
                "--settings",
                str(settings_path),
                "run-full-batch",
                "--batch-id",
                "2026-07-16-log-test",
                "--project-root",
                str(root),
                "--theme-seed",
                "bedtime star mystery",
                "--dry-run",
            ]
            stderr = io.StringIO()

            with (
                patch.object(sys, "argv", argv),
                patch.object(sys, "stderr", stderr),
                patch("builtins.print") as print_call,
            ):
                exit_code = cli_main()

            self.assertEqual(exit_code, 0)
            logs = stderr.getvalue()
            self.assertIn("[run-full-batch] starting batch 2026-07-16-log-test", logs)
            self.assertIn("[run-full-batch] theme_seed: bedtime star mystery", logs)
            self.assertIn("[run-full-batch] drafting stories", logs)
            self.assertIn("[run-full-batch] generating images", logs)
            self.assertIn("[run-full-batch] generating audio", logs)
            self.assertIn("[run-full-batch] rendering videos", logs)
            self.assertIn("[run-full-batch] done", logs)
            printed_paths = [call.args[0] for call in print_call.call_args_list]
            self.assertEqual(len(printed_paths), 4)


if __name__ == "__main__":
    unittest.main()
