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
from shorts_superheroes.models import CharacterBible, Scene, StoryPackage, VillainProfile, load_json
from shorts_superheroes.pipeline import draft_batch, generate_audio, generate_images, render_batch, write_batch


def _sample_stories() -> list[StoryPackage]:
    stories: list[StoryPackage] = []
    for index in range(1, 5):
        video_id = f"video-{index:02d}"
        hero_name = f"Glow Garden {index}"
        villain_name = f"The Thorn Timer {index}"
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
                villain_profile=VillainProfile(
                    name=villain_name,
                    motive="wants the garden to follow only his rushed schedule",
                    plan="turns every garden marker backward so friends cannot agree where to help first",
                    visual_design="an original tiny antagonist with a square leaf clock and striped moss boots",
                    nonviolent_methods=["backward markers", "tick-tock fog", "mixed-up garden cards"],
                ),
                script=(
                    f"{hero_name} found a worried seed in the garden just as the morning light touched the leaves. "
                    f"Then {villain_name} turned every garden marker backward, because he wanted the garden to follow only his rushed schedule. "
                    "The tiny seed wanted to grow, but the wind felt loud, the soil felt cold, and every sign sent helpers in the wrong direction. "
                    f"{hero_name} tried a first attempt with listening lights, but the lights followed the backward markers and made a glowing loop. "
                    "A ladybug noticed the warmest patch of soil, a snail found a quiet path, and a sparrow spotted one marker with fresh moss on the wrong side. "
                    "That clue changed the plan: the markers were not lost, they had been turned in a pattern. "
                    f"{hero_name} faced {villain_name} without violence and asked the friends to read the pattern together. "
                    "Together they moved one pebble, brushed one leaf, turned each marker back, and made one cozy place where the seed could rest without feeling rushed. "
                    "When a small sprout finally peeked out, everyone cheered softly, because they had learned that careful listening can turn a confusing problem into shared work. "
                    f"{hero_name} smiled and promised to return whenever a friend needed patience, teamwork, and a little light."
                ),
                scenes=[
                    Scene("scene-01", 11, f"{hero_name} finds backward garden markers.", f"Portrait soft 3D storybook scene of {hero_name} finding backward garden markers caused by {villain_name}."),
                    Scene("scene-02", 11, f"{villain_name} watches the garden confusion.", f"Original antagonist {villain_name} with a square leaf clock near safe mixed-up garden signs."),
                    Scene("scene-03", 11, "A listening light loops around.", "A warm listening light loops around backward signs in a garden library."),
                    Scene("scene-04", 11, "Friends discover the moss clue.", "Friendly characters find a moss clue on a turned garden marker."),
                    Scene("scene-05", 11, f"{hero_name} faces {villain_name} calmly.", f"Nonviolent storybook confrontation between {hero_name} and {villain_name}, no weapons, no fighting."),
                    Scene("scene-06", 11, "A sprout grows after the markers are fixed.", "A happy sprout grows while friends restore garden markers together."),
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
