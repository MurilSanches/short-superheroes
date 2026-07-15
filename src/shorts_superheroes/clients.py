from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Callable
import urllib.request

from .models import CharacterBible, Scene, StoryPackage


JsonTransport = Callable[[str, dict[str, str], dict], dict]
BinaryTransport = Callable[[str, dict[str, str], dict], bytes]


def default_json_transport(url: str, headers: dict[str, str], payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST", headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def default_binary_transport(url: str, headers: dict[str, str], payload: dict) -> bytes:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST", headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


class OpenAIStoryClient:
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4.1-mini",
        transport: JsonTransport = default_json_transport,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.transport = transport

    def generate_stories(
        self,
        theme_seed: str,
        system_prompt: str,
        user_prompt: str,
    ) -> list[StoryPackage]:
        payload = {
            "model": self.model,
            "instructions": system_prompt,
            "input": f"Theme seed: {theme_seed}\n\n{user_prompt}",
            "text": {"format": _story_response_format()},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        result = self.transport("https://api.openai.com/v1/responses", headers, payload)
        story_data = json.loads(_response_output_text(result))
        stories = [StoryPackage.from_dict(item) for item in story_data["stories"]]
        if len(stories) != 4:
            raise ValueError(
                f"OpenAI story response must contain exactly 4 StoryPackage instances; got {len(stories)}"
            )
        return stories


class OpenAIImageClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        size: str,
        quality: str,
        transport: JsonTransport = default_json_transport,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.size = size
        self.quality = quality
        self.transport = transport

    def generate_image(self, prompt: str, output_path: Path) -> Path:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "size": self.size,
            "quality": self.quality,
            "n": 1,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        result = self.transport("https://api.openai.com/v1/images/generations", headers, payload)
        encoded = result["data"][0]["b64_json"]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(base64.b64decode(encoded))
        return output_path


class ElevenLabsTtsClient:
    def __init__(
        self,
        api_key: str,
        voice_id: str,
        model_id: str,
        output_format: str,
        transport: BinaryTransport = default_binary_transport,
    ) -> None:
        self.api_key = api_key
        self.voice_id = voice_id
        self.model_id = model_id
        self.output_format = output_format
        self.transport = transport

    def generate_speech(self, text: str, output_path: Path) -> Path:
        url = (
            f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
            f"?output_format={self.output_format}"
        )
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {"stability": 0.55, "similarity_boost": 0.75},
        }
        audio = self.transport(url, headers, payload)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(audio)
        return output_path


class DryRunStoryClient:
    def generate_stories(
        self,
        theme_seed: str,
        system_prompt: str = "",
        user_prompt: str = "",
    ) -> list[StoryPackage]:
        del theme_seed, system_prompt, user_prompt
        stories = [
            ("Luma Leap", "honesty", "a teal cape and gold cloud boots", "gentle guiding lights"),
            ("Piper Pulse", "sharing", "a coral jacket and silver sneakers", "warm rhythm waves"),
            ("Moss Mender", "patience", "a green hood and amber gloves", "tiny helpful vines"),
            ("Skye Spark", "kindness", "a blue vest and bright white boots", "soft star lanterns"),
        ]
        return [
            _dry_run_story(index, hero_name, moral, appearance, power)
            for index, (hero_name, moral, appearance, power) in enumerate(stories, start=1)
        ]


class DryRunImageClient:
    def generate_image(self, prompt: str, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"DRY RUN IMAGE\n{prompt}\n", encoding="utf-8")
        return output_path


class DryRunTtsClient:
    def generate_speech(self, text: str, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(("DRY RUN AUDIO\n" + text + "\n").encode("utf-8"))
        return output_path


def _response_output_text(result: dict) -> str:
    if "output_text" in result:
        return str(result["output_text"])

    for output_item in result.get("output", []):
        for content_item in output_item.get("content", []):
            if content_item.get("type") == "output_text":
                return str(content_item["text"])
    raise ValueError("OpenAI response did not contain output text")


def _story_response_format() -> dict:
    string_array = {"type": "array", "items": {"type": "string"}}
    scene = {
        "type": "object",
        "additionalProperties": False,
        "required": ["scene_id", "duration_sec", "narration", "image_prompt"],
        "properties": {
            "scene_id": {"type": "string"},
            "duration_sec": {"type": "integer"},
            "narration": {"type": "string"},
            "image_prompt": {"type": "string"},
        },
    }
    bible = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "appearance",
            "color_palette",
            "original_symbol",
            "power",
            "recurring_setting",
            "visual_style",
            "negative_restrictions",
        ],
        "properties": {
            "appearance": {"type": "string"},
            "color_palette": string_array,
            "original_symbol": {"type": "string"},
            "power": {"type": "string"},
            "recurring_setting": {"type": "string"},
            "visual_style": {"type": "string"},
            "negative_restrictions": string_array,
        },
    }
    story = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "video_id",
            "hero_name",
            "moral",
            "target_duration_sec",
            "character_bible",
            "script",
            "scenes",
            "tiktok_title",
            "tiktok_description",
            "hashtags",
        ],
        "properties": {
            "video_id": {"type": "string"},
            "hero_name": {"type": "string"},
            "moral": {"type": "string"},
            "target_duration_sec": {"type": "integer"},
            "character_bible": bible,
            "script": {"type": "string"},
            "scenes": {"type": "array", "items": scene},
            "tiktok_title": {"type": "string"},
            "tiktok_description": {"type": "string"},
            "hashtags": string_array,
        },
    }
    return {
        "type": "json_schema",
        "name": "story_batch",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["stories"],
            "properties": {
                "stories": {
                    "type": "array",
                    "items": story,
                    "minItems": 4,
                    "maxItems": 4,
                }
            },
        },
    }


def _dry_run_story(
    index: int,
    hero_name: str,
    moral: str,
    appearance: str,
    power: str,
) -> StoryPackage:
    scenes = [
        Scene(
            scene_id=f"scene-{scene_index:02d}",
            duration_sec=9,
            narration=f"{hero_name} begins a small mission with a friend.",
            image_prompt=f"Original soft 3D storybook scene of {hero_name} on a kind mission.",
        )
        for scene_index in range(1, 7)
    ]
    return StoryPackage(
        video_id=f"video-{index:02d}",
        hero_name=hero_name,
        moral=f"{moral.capitalize()} helps friends solve problems together.",
        target_duration_sec=54,
        character_bible=CharacterBible(
            appearance=f"An original young hero wearing {appearance}.",
            color_palette=["teal", "gold", "white"],
            original_symbol="a small sunrise inside a circle",
            power=power,
            recurring_setting="a cozy cloud city library",
            visual_style="soft 3D storybook illustration",
            negative_restrictions=["no existing superhero logos", "no known character designs"],
        ),
        script=(
            f"{hero_name} sees a friend with a small problem. {hero_name} listens, shares a kind idea, "
            f"and uses {power} to help. The friends learn that {moral} makes every mission brighter."
        ),
        scenes=scenes,
        tiktok_title=f"{hero_name}'s Kind Mission",
        tiktok_description=f"A simple original hero story about {moral}.",
        hashtags=["#kidsstory", "#storytime", "#originalhero"],
    )
