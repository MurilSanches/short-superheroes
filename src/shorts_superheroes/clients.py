from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Callable
import urllib.request

from .models import CharacterBible, Scene, StoryPackage, VillainProfile


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


class OpenAIThemeSeedClient:
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4.1-mini",
        transport: JsonTransport = default_json_transport,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.transport = transport

    def generate_theme_seed(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "instructions": system_prompt,
            "input": user_prompt,
            "text": {"format": _theme_seed_response_format()},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        result = self.transport("https://api.openai.com/v1/responses", headers, payload)
        theme_seed = str(json.loads(_response_output_text(result))["theme_seed"]).strip()
        if not theme_seed:
            raise ValueError("OpenAI theme response returned an empty theme_seed")
        return theme_seed


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
            (
                "Luma Leap",
                "honesty",
                "a teal cape and gold cloud boots",
                "gentle guiding lights",
                "The Page Taker",
                "wants to keep every secret map for himself",
                "slides glowing map pages into blank books so no friend can find the right shelf",
                "a small original antagonist with a violet bookmark cloak and square moon glasses",
                ["map hiding", "paper fog", "silent shelf shuffling"],
            ),
            (
                "Piper Pulse",
                "sharing",
                "a coral jacket and silver sneakers",
                "warm rhythm waves",
                "Madam Mute Button",
                "wants the town parade to hear only her tiny whistle",
                "captures friendly songs inside clear bubbles and floats them above the street",
                "an original button-covered trickster with a tall mint hat and ribbon shoes",
                ["sound bubbles", "echo loops", "mixed-up parade signs"],
            ),
            (
                "Moss Mender",
                "patience",
                "a green hood and amber gloves",
                "tiny helpful vines",
                "Count Crumbleclock",
                "wants every garden task finished too fast",
                "spins the garden clock until seedlings and helpers rush in the wrong order",
                "a clock-caped original antagonist with pebble buttons and twig spectacles",
                ["time rushing", "crooked schedules", "tick-tock fog"],
            ),
            (
                "Skye Spark",
                "kindness",
                "a blue vest and bright white boots",
                "soft star lanterns",
                "The Cloud Collector",
                "wants to keep all bright clouds in his own silver jar",
                "pulls helpful clouds away from the playground so everyone loses shade",
                "a round original antagonist with jar-shaped goggles and a silver raincoat",
                ["cloud scooping", "shadow puzzles", "floating jar tricks"],
            ),
        ]
        return [
            _dry_run_story(index, hero_name, moral, appearance, power, villain_name, motive, plan, visual, methods)
            for index, (
                hero_name,
                moral,
                appearance,
                power,
                villain_name,
                motive,
                plan,
                visual,
                methods,
            ) in enumerate(stories, start=1)
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
    villain = {
        "type": "object",
        "additionalProperties": False,
        "required": ["name", "motive", "plan", "visual_design", "nonviolent_methods"],
        "properties": {
            "name": {"type": "string"},
            "motive": {"type": "string"},
            "plan": {"type": "string"},
            "visual_design": {"type": "string"},
            "nonviolent_methods": string_array,
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
            "villain_profile",
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
            "target_duration_sec": {"type": "integer", "minimum": 60, "maximum": 75},
            "character_bible": bible,
            "villain_profile": villain,
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


def _theme_seed_response_format() -> dict:
    return {
        "type": "json_schema",
        "name": "theme_seed",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["theme_seed"],
            "properties": {
                "theme_seed": {
                    "type": "string",
                    "minLength": 20,
                    "maxLength": 180,
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
    villain_name: str,
    villain_motive: str,
    villain_plan: str,
    villain_visual: str,
    villain_methods: list[str],
) -> StoryPackage:
    hero_visual = f"An original young hero wearing {appearance}."
    recurring_setting = "a cozy cloud city library"
    scenes = [
        Scene(
            scene_id="scene-01",
            duration_sec=11,
            narration=f"{hero_name} notices the first strange clue from {villain_name}'s plan.",
            image_prompt=(
                f"Portrait 1024x1536 soft 3D storybook illustration. {hero_visual} "
                f"Setting: {recurring_setting}. Antagonist: {villain_name}, {villain_visual}. "
                f"Show a safe visual clue from the villain plan: {villain_plan}."
            ),
        ),
        Scene(
            scene_id="scene-02",
            duration_sec=11,
            narration=f"{villain_name} makes the problem bigger with a clever nonviolent trick.",
            image_prompt=(
                f"Portrait 1024x1536 soft 3D storybook illustration. {hero_visual} "
                f"Setting: {recurring_setting}. Show {villain_name}, {villain_visual}, using "
                f"{villain_methods[0]} without violence while friends look puzzled but safe."
            ),
        ),
        Scene(
            scene_id="scene-03",
            duration_sec=11,
            narration=f"{hero_name}'s first attempt helps a little but does not stop the whole plan.",
            image_prompt=(
                f"Portrait 1024x1536 soft 3D storybook illustration. {hero_visual} "
                f"{hero_name} uses {power} while {villain_name}'s plan still causes a gentle obstacle."
            ),
        ),
        Scene(
            scene_id="scene-04",
            duration_sec=11,
            narration="A small clue reveals what the team misunderstood.",
            image_prompt=(
                f"Portrait 1024x1536 soft 3D storybook illustration. {hero_visual} "
                f"Friends discover a kind clue about {villain_name}'s motive: {villain_motive}."
            ),
        ),
        Scene(
            scene_id="scene-05",
            duration_sec=11,
            narration=f"{hero_name} faces {villain_name} with courage, listening, and a smarter plan.",
            image_prompt=(
                f"Portrait 1024x1536 soft 3D storybook illustration. {hero_visual} "
                f"Nonviolent confrontation between {hero_name} and {villain_name}; no weapons, no fighting, "
                "only brave teamwork and glowing clues."
            ),
        ),
        Scene(
            scene_id="scene-06",
            duration_sec=11,
            narration=f"The friends repair the problem and {hero_name} explains the lesson.",
            image_prompt=(
                f"Portrait 1024x1536 soft 3D storybook illustration. {hero_visual} "
                f"The safe aftermath after stopping {villain_name}'s plan, friends restoring the setting together."
            ),
        ),
    ]
    return StoryPackage(
        video_id=f"video-{index:02d}",
        hero_name=hero_name,
        moral=f"{moral.capitalize()} helps friends solve problems together.",
        target_duration_sec=66,
        character_bible=CharacterBible(
            appearance=hero_visual,
            color_palette=["teal", "gold", "white"],
            original_symbol="a small sunrise inside a circle",
            power=power,
            recurring_setting=recurring_setting,
            visual_style="soft 3D storybook illustration",
            negative_restrictions=["no existing superhero logos", "no known character designs"],
        ),
        villain_profile=VillainProfile(
            name=villain_name,
            motive=villain_motive,
            plan=villain_plan,
            visual_design=villain_visual,
            nonviolent_methods=villain_methods,
        ),
        script=_dry_run_script(hero_name, moral, power, villain_name, villain_motive, villain_plan),
        scenes=scenes,
        tiktok_title=f"{hero_name} Stops {villain_name}",
        tiktok_description=f"An original hero and villain story about {moral}.",
        hashtags=["#kidsstory", "#storytime", "#originalhero"],
    )


def _dry_run_script(
    hero_name: str,
    moral: str,
    power: str,
    villain_name: str,
    villain_motive: str,
    villain_plan: str,
) -> str:
    return (
        f"{hero_name} was getting ready for a quiet morning when the cozy cloud city library gave three soft chimes, "
        "which meant something important had gone wrong. A row of friendly signs suddenly pointed in different directions, "
        f"and every lost reader whispered that the trouble began after {villain_name} passed by with a secret smile. "
        f"{villain_name} wanted a real obstacle, not a silly prank, because {villain_motive}. The villain plan was to {villain_plan}, "
        "so friends would feel confused and ask only the villain for answers. "
        f"{hero_name} tried a first attempt right away, using {power} to draw one bright path across the floor, but the path split into loops and did not solve the whole problem. "
        "That failure made the room quiet for a moment. Instead of pushing harder, the hero asked each friend what had changed, what still felt safe, and what clue looked different from the rest. "
        "A tiny corner of one sign had a folded mark, and that twist showed the team that the signs were not broken; they had been rearranged in a pattern. "
        f"{hero_name} faced {villain_name} without violence, weapons, or shouting. The hero named the plan, listened to the motive, and invited the friends to rebuild the pattern together. "
        "One friend read the folded marks, one friend watched the shelves, and one friend carried a lantern so nobody felt alone. "
        f"When the plan came apart, {villain_name} saw that control had made the library smaller, while teamwork made it bright again. "
        f"{hero_name} reminded everyone that {moral} works best when courage comes with patience, honesty, and care. "
        "By sunset, the signs pointed home, the readers found their books, and the whole team understood that a smart hero does not need to overpower a villain to protect a place they love."
    )
