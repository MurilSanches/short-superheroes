from __future__ import annotations

from pathlib import Path

from shorts_superheroes.models import CostEstimate, StoryPackage, write_json


def write_story_files(video_dir: Path, story: StoryPackage) -> None:
    video_dir.mkdir(parents=True, exist_ok=True)
    write_json(video_dir / "story.json", story.to_dict())
    (video_dir / "script.txt").write_text(story.script + "\n", encoding="utf-8")
    metadata_lines = [
        f"Title: {story.tiktok_title}",
        "",
        story.tiktok_description,
        "",
        " ".join(story.hashtags),
        "",
    ]
    (video_dir / "metadata.txt").write_text("\n".join(metadata_lines), encoding="utf-8")


def build_review_markdown(batch_id: str, stories: list[StoryPackage], estimates: list[CostEstimate]) -> str:
    if len(stories) != len(estimates):
        raise ValueError("stories and estimates must have the same length")
    lines = [
        f"# Batch {batch_id} Review",
        "",
        "## Checkpoints",
        "",
        "- [ ] Scripts and image prompts approved",
        "- [ ] Generated images approved",
        "- [ ] Final videos and metadata approved",
        "",
        "## Cost Estimate",
        "",
        "| Video | Hero | Text | Images | Voice | Estimated total |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for story, estimate in zip(stories, estimates):
        lines.append(
            f"| {story.video_id} | {story.hero_name} | "
            f"${estimate.text_usd:.4f} | ${estimate.images_usd:.4f} | "
            f"${estimate.voice_usd:.4f} | ${estimate.total_usd:.4f} |"
        )
    lines.extend(["", "## Stories", ""])
    for story in stories:
        lines.extend(
            [
                f"### {story.video_id}: {story.hero_name}",
                "",
                f"**Moral:** {story.moral}",
                "",
                "**Script:**",
                "",
                story.script,
                "",
                "**Scenes:**",
                "",
            ]
        )
        for scene in story.scenes:
            lines.extend(
                [
                    f"- `{scene.scene_id}` ({scene.duration_sec}s): {scene.narration}",
                    f"  - Prompt: {scene.image_prompt}",
                ]
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
