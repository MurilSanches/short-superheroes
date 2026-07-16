from __future__ import annotations

from pathlib import Path

from shorts_superheroes.costs import estimate_story_cost
from shorts_superheroes.media import render_video
from shorts_superheroes.models import Batch, StoryPackage, load_json, write_json
from shorts_superheroes.paths import ensure_batch_layout
from shorts_superheroes.review import build_review_markdown, write_story_files
from shorts_superheroes.safety import validate_story_package


def _story_dirs(batch_dir: Path) -> list[Path]:
    return sorted(path for path in batch_dir.glob("video-*") if path.is_dir())


def _load_validated_batch(batch_dir: Path, expected_status: str) -> tuple[Batch, list[StoryPackage]]:
    batch = Batch.from_dict(load_json(batch_dir / "batch.json"))
    if batch.status != expected_status:
        raise ValueError(
            f"Batch {batch.batch_id} has status '{batch.status}'; "
            f"expected status '{expected_status}'"
        )

    stories: list[StoryPackage] = []
    errors: list[str] = []
    for video_dir in _story_dirs(batch_dir):
        story = StoryPackage.from_dict(load_json(video_dir / "story.json"))
        check = validate_story_package(story)
        if not check.ok:
            errors.extend(f"{story.video_id}: {error}" for error in check.errors)
        stories.append(story)
    if errors:
        raise ValueError("; ".join(errors))
    return batch, stories


def draft_batch(
    project_root: Path,
    batch_id: str,
    theme_seed: str,
    settings: dict,
    story_client,
    image_model: str,
    max_attempts: int = 3,
) -> Path:
    templates_dir = project_root / "config" / "prompt-templates"
    system_prompt = (templates_dir / "story-system.md").read_text(encoding="utf-8")
    base_user_prompt = (templates_dir / "story-user.md").read_text(encoding="utf-8")
    base_user_prompt = base_user_prompt.replace("{{theme_seed}}", theme_seed)
    user_prompt = base_user_prompt
    last_errors: list[str] = []

    for attempt in range(1, max_attempts + 1):
        stories = story_client.generate_stories(theme_seed, system_prompt, user_prompt)
        last_errors = _story_validation_errors(stories)
        if not last_errors:
            return write_batch(project_root, batch_id, stories, settings, image_model, theme_seed=theme_seed)
        if attempt < max_attempts:
            user_prompt = _retry_user_prompt(base_user_prompt, last_errors)

    raise ValueError("; ".join(last_errors))


def write_batch(
    project_root: Path,
    batch_id: str,
    stories: list[StoryPackage],
    settings: dict,
    image_model: str,
    theme_seed: str = "",
) -> Path:
    if len(stories) != 4:
        raise ValueError("MVP requires exactly 4 stories")

    errors = _story_validation_errors(stories)
    if errors:
        raise ValueError("; ".join(errors))

    estimates = [estimate_story_cost(story, settings, image_model) for story in stories]
    layout = ensure_batch_layout(project_root, batch_id, video_count=4)
    batch_dir = layout["batch_dir"]
    for story in stories:
        write_story_files(batch_dir / story.video_id, story)

    (batch_dir / "review.md").write_text(
        build_review_markdown(batch_id, stories, estimates), encoding="utf-8"
    )
    write_json(
        batch_dir / "batch.json",
        Batch(
            batch_id=batch_id,
            status="drafted",
            image_model=image_model,
            theme_seed=theme_seed,
            review_mode=str(settings.get("review_mode", "full_validation")),
            cost_estimates=[estimate.to_dict() for estimate in estimates],
        ).to_dict(),
    )
    return batch_dir


def _story_validation_errors(stories: list[StoryPackage]) -> list[str]:
    errors: list[str] = []
    for story in stories:
        check = validate_story_package(story)
        if not check.ok:
            errors.extend(f"{story.video_id}: {error}" for error in check.errors)
    return errors


def _retry_user_prompt(base_user_prompt: str, errors: list[str]) -> str:
    return (
        base_user_prompt
        + "\n\nPrevious story batch failed validation:\n"
        + "\n".join(f"- {error}" for error in errors)
        + "\n\nRegenerate all 4 stories from scratch. Fix every listed validation error. "
        "For script_too_short_for_60_seconds, write 1300 to 1600 characters and 180 to 230 words. "
        "Do not return any script below 1300 characters."
    )


def generate_images(batch_dir: Path, image_client) -> None:
    batch, stories = _load_validated_batch(batch_dir, "drafted")
    for video_dir, story in zip(_story_dirs(batch_dir), stories):
        for scene in story.scenes:
            output_path = video_dir / "images" / f"{scene.scene_id}.png"
            if output_path.is_file() and output_path.stat().st_size > 0:
                scene.image_path = str(output_path)
                continue
            try:
                scene.image_path = str(image_client.generate_image(scene.image_prompt, output_path))
            except Exception as error:
                raise RuntimeError(
                    f"Image generation failed for {story.video_id}/{scene.scene_id} "
                    f"at {output_path}: {error}\nPrompt: {scene.image_prompt}"
                ) from error
        write_json(video_dir / "story.json", story.to_dict())

    batch.status = "images_generated"
    write_json(batch_dir / "batch.json", batch.to_dict())


def generate_audio(batch_dir: Path, tts_client) -> None:
    batch, stories = _load_validated_batch(batch_dir, "images_generated")
    for video_dir, story in zip(_story_dirs(batch_dir), stories):
        tts_client.generate_speech(story.script, video_dir / "audio" / "voice.mp3")

    batch.status = "audio_generated"
    write_json(batch_dir / "batch.json", batch.to_dict())


def render_batch(batch_dir: Path, dry_run: bool) -> None:
    batch, stories = _load_validated_batch(batch_dir, "audio_generated")
    final_video_paths: list[str] = []
    for video_dir, story in zip(_story_dirs(batch_dir), stories):
        image_paths = [Path(scene.image_path) for scene in story.scenes if scene.image_path]
        if len(image_paths) != len(story.scenes):
            image_paths = sorted((video_dir / "images").glob("*"))
        output_path = video_dir / "final" / f"{story.video_id}.mp4"
        render_video(
            image_paths=image_paths,
            audio_path=video_dir / "audio" / "voice.mp3",
            output_path=output_path,
            scene_duration_sec=max(1, round(story.target_duration_sec / max(1, len(story.scenes)))),
            dry_run=dry_run,
        )
        final_video_paths.append(str(output_path))

    batch.status = "rendered"
    batch.final_video_paths = final_video_paths
    write_json(batch_dir / "batch.json", batch.to_dict())
