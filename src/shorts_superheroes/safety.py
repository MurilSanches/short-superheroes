from __future__ import annotations

from shorts_superheroes.models import CheckResult, StoryPackage


KNOWN_IP_TERMS = [
    "batman",
    "superman",
    "spider",
    "spider-man",
    "iron man",
    "hulk",
    "thor",
    "captain america",
    "wonder woman",
    "flash",
    "aquaman",
    "wolverine",
    "x-men",
    "avengers",
    "justice league",
    "marvel",
    "dc comics",
]

PERSONAL_DATA_PATTERNS = [
    "your age",
    "your school",
    "where you live",
    "your address",
    "your phone",
    "comment your age",
    "tell me your age",
    "send a photo",
]

UNSAFE_TERMS = [
    "blood",
    "gore",
    "kill",
    "murder",
    "gun",
    "knife",
    "sexy",
    "political campaign",
]


def _joined_story_text(story: StoryPackage) -> str:
    parts = [
        story.video_id,
        story.hero_name,
        story.moral,
        story.script,
        story.tiktok_title,
        story.tiktok_description,
        story.character_bible.appearance,
        story.character_bible.original_symbol,
        story.character_bible.power,
        story.character_bible.recurring_setting,
        story.character_bible.visual_style,
    ]
    for scene in story.scenes:
        parts.extend([scene.narration, scene.image_prompt])
    parts.extend(story.hashtags)
    return " ".join(parts).lower()


def validate_story_package(story: StoryPackage) -> CheckResult:
    errors: list[str] = []
    warnings: list[str] = []
    text = _joined_story_text(story)

    if len(story.scenes) < 6 or len(story.scenes) > 8:
        errors.append("scene_count_out_of_range")
    if story.target_duration_sec < 45 or story.target_duration_sec > 60:
        errors.append("duration_out_of_range")
    if not story.hero_name.strip():
        errors.append("missing_hero_name")
    if not story.script.strip():
        errors.append("missing_script")

    for term in KNOWN_IP_TERMS:
        if term in text:
            errors.append(f"known_ip_term: {term}")
    for pattern in PERSONAL_DATA_PATTERNS:
        if pattern in text:
            errors.append("child_personal_data_prompt")
            break
    for term in UNSAFE_TERMS:
        if term in text:
            errors.append(f"unsafe_term: {term}")

    if len(story.script) < 500:
        warnings.append("script_may_be_short_for_45_seconds")
    if len(story.script) > 1200:
        warnings.append("script_may_be_long_for_60_seconds")

    return CheckResult(ok=len(errors) == 0, errors=errors, warnings=warnings)
