from __future__ import annotations

import argparse
import os
from pathlib import Path

from shorts_superheroes.clients import (
    DryRunImageClient,
    DryRunStoryClient,
    DryRunTtsClient,
    ElevenLabsTtsClient,
    OpenAIImageClient,
    OpenAIStoryClient,
)
from shorts_superheroes.env import load_dotenv
from shorts_superheroes.models import CharacterBible, Scene, StoryPackage, load_json
from shorts_superheroes.pipeline import draft_batch, generate_audio, generate_images, render_batch, write_batch


def _sample_stories() -> list[StoryPackage]:
    stories: list[StoryPackage] = []
    for index in range(1, 5):
        video_id = f"video-{index:02d}"
        hero_name = f"Glow Garden {index}"
        stories.append(
            StoryPackage(
                video_id=video_id,
                hero_name=hero_name,
                moral="Friends can solve problems when they listen to each other.",
                target_duration_sec=66,
                character_bible=CharacterBible(
                    appearance=f"A friendly original hero named {hero_name} with a green scarf and glowing buttons.",
                    color_palette=["green", "gold", "white"],
                    original_symbol="three tiny leaves inside a circle",
                    power="making gentle listening lights",
                    recurring_setting="a sunny garden library",
                    visual_style="soft 3D storybook illustration",
                    negative_restrictions=["no existing superhero logos", "no Marvel", "no DC"],
                ),
                script=(
                    f"{hero_name} found a worried seed in the garden just as the morning light touched the leaves. "
                    "The tiny seed wanted to grow, but the wind felt loud, the soil felt cold, and every shadow seemed too big. "
                    f"{hero_name} sat nearby, kept a gentle voice, and asked the garden friends to listen before anyone tried to fix the problem. "
                    "A ladybug noticed the warmest patch of soil, a snail found a quiet path, and a sparrow brought a soft feather to make the seed feel safe. "
                    "The hero made listening lights that glowed whenever someone shared a kind idea, and soon the whole garden could see the plan clearly. "
                    "Together they moved one pebble, brushed one leaf, and made one cozy place where the seed could rest without feeling rushed. "
                    "When a small sprout finally peeked out, everyone cheered softly, because they had learned that careful listening can turn a scary problem into shared work. "
                    f"{hero_name} smiled and promised to return whenever a friend needed patience, teamwork, and a little light."
                ),
                scenes=[
                    Scene("scene-01", 11, f"{hero_name} finds a worried seed.", f"Portrait soft 3D storybook scene of {hero_name} finding a worried seed."),
                    Scene("scene-02", 11, "Friends gather kindly.", "Garden friends gather kindly around an original hero."),
                    Scene("scene-03", 11, "A listening light appears.", "A warm listening light appears in a garden library."),
                    Scene("scene-04", 11, "Everyone shares ideas.", "Friendly characters share ideas in a sunny garden."),
                    Scene("scene-05", 11, "The seed settles into soil.", "A tiny seed settles into glowing soil."),
                    Scene("scene-06", 11, "A sprout grows.", "A happy sprout grows while friends smile."),
                ],
                tiktok_title=f"{hero_name} and the Listening Light",
                tiktok_description="A gentle original superhero story about listening.",
                hashtags=["#kidsstory", "#storytime", "#superhero"],
            )
        )
    return stories


def _load_settings(path: Path) -> dict:
    return load_json(path)


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--settings", default="projects/shorts-superheroes/config/settings.example.json")
    subparsers = parser.add_subparsers(dest="command", required=True)

    draft = subparsers.add_parser("draft-batch")
    draft.add_argument("--batch-id", required=True)
    draft.add_argument("--project-root", default="projects/shorts-superheroes")
    draft.add_argument("--theme-seed", default="kindness and teamwork")
    draft.add_argument("--image-model", default=None)
    draft.add_argument("--dry-run", action="store_true")

    sample = subparsers.add_parser("write-sample-batch")
    sample.add_argument("--batch-id", required=True)
    sample.add_argument("--project-root", default="projects/shorts-superheroes")
    sample.add_argument("--image-model", default=None)

    images = subparsers.add_parser("generate-images")
    images.add_argument("--batch-dir", required=True)
    images.add_argument("--dry-run", action="store_true")

    audio = subparsers.add_parser("generate-audio")
    audio.add_argument("--batch-dir", required=True)
    audio.add_argument("--dry-run", action="store_true")

    render = subparsers.add_parser("render-batch")
    render.add_argument("--batch-dir", required=True)
    render.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    settings = _load_settings(Path(args.settings))

    if args.command == "draft-batch":
        story_client = (
            DryRunStoryClient()
            if args.dry_run
            else OpenAIStoryClient(os.environ["OPENAI_API_KEY"], settings["openai"]["text_model"])
        )
        batch_dir = draft_batch(
            Path(args.project_root),
            args.batch_id,
            args.theme_seed,
            settings,
            story_client,
            args.image_model or settings["openai"]["image_model_default"],
        )
        print(batch_dir)
        return 0

    if args.command == "write-sample-batch":
        batch_dir = write_batch(
            Path(args.project_root),
            args.batch_id,
            _sample_stories(),
            settings,
            args.image_model or settings["openai"]["image_model_default"],
        )
        print(batch_dir)
        return 0

    if args.command == "generate-images":
        client = (
            DryRunImageClient()
            if args.dry_run
            else OpenAIImageClient(
                api_key=os.environ["OPENAI_API_KEY"],
                model=settings["openai"]["image_model_default"],
                size=settings["openai"]["image_size"],
                quality=settings["openai"]["image_quality"],
            )
        )
        generate_images(Path(args.batch_dir), client)
        return 0

    if args.command == "generate-audio":
        client = (
            DryRunTtsClient()
            if args.dry_run
            else ElevenLabsTtsClient(
                api_key=os.environ["ELEVENLABS_API_KEY"],
                voice_id=settings["elevenlabs"]["voice_id"],
                model_id=settings["elevenlabs"]["model_id"],
                output_format=settings["elevenlabs"]["output_format"],
            )
        )
        generate_audio(Path(args.batch_dir), client)
        return 0

    if args.command == "render-batch":
        render_batch(Path(args.batch_dir), dry_run=args.dry_run)
        return 0

    raise ValueError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
