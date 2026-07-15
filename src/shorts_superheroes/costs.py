from __future__ import annotations

from shorts_superheroes.models import CostEstimate, StoryPackage


def estimate_story_cost(story: StoryPackage, settings: dict, image_model: str) -> CostEstimate:
    image_size = settings["openai"]["image_size"]
    image_quality = settings["openai"]["image_quality"]
    price_key = f"{image_model}|{image_quality}|{image_size}"
    image_price = float(settings["costs"]["image_usd_by_model_quality_size"][price_key])
    text_batch_cost = float(settings["costs"]["text_generation_usd_per_batch"])
    video_count = int(settings["video_count"])
    if video_count != 4:
        raise ValueError("MVP cost estimation requires exactly 4 videos per batch")
    voice_rate = float(settings["costs"]["elevenlabs_flash_turbo_usd_per_1000_chars"])
    text_usd = round(text_batch_cost / 4, 4)
    images_usd = round(len(story.scenes) * image_price, 4)
    voice_usd = round((len(story.script) / 1000.0) * voice_rate, 4)
    return CostEstimate(text_usd=text_usd, images_usd=images_usd, voice_usd=voice_usd)
