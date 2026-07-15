from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


@dataclass
class CharacterBible:
    appearance: str
    color_palette: list[str]
    original_symbol: str
    power: str
    recurring_setting: str
    visual_style: str
    negative_restrictions: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "CharacterBible":
        return cls(
            appearance=str(data["appearance"]),
            color_palette=[str(item) for item in data.get("color_palette", [])],
            original_symbol=str(data["original_symbol"]),
            power=str(data["power"]),
            recurring_setting=str(data["recurring_setting"]),
            visual_style=str(data["visual_style"]),
            negative_restrictions=[str(item) for item in data.get("negative_restrictions", [])],
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Scene:
    scene_id: str
    duration_sec: int
    narration: str
    image_prompt: str
    image_path: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "Scene":
        return cls(
            scene_id=str(data["scene_id"]),
            duration_sec=int(data["duration_sec"]),
            narration=str(data["narration"]),
            image_prompt=str(data["image_prompt"]),
            image_path=str(data.get("image_path", "")),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StoryPackage:
    video_id: str
    hero_name: str
    moral: str
    target_duration_sec: int
    character_bible: CharacterBible
    script: str
    scenes: list[Scene]
    tiktok_title: str
    tiktok_description: str
    hashtags: list[str]
    voice_id: str = ""
    safety_flags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "StoryPackage":
        return cls(
            video_id=str(data["video_id"]),
            hero_name=str(data["hero_name"]),
            moral=str(data["moral"]),
            target_duration_sec=int(data["target_duration_sec"]),
            character_bible=CharacterBible.from_dict(data["character_bible"]),
            script=str(data["script"]),
            scenes=[Scene.from_dict(item) for item in data.get("scenes", [])],
            tiktok_title=str(data["tiktok_title"]),
            tiktok_description=str(data["tiktok_description"]),
            hashtags=[str(item) for item in data.get("hashtags", [])],
            voice_id=str(data.get("voice_id", "")),
            safety_flags=[str(item) for item in data.get("safety_flags", [])],
        )

    def to_dict(self) -> dict:
        data = asdict(self)
        data["character_bible"] = self.character_bible.to_dict()
        data["scenes"] = [scene.to_dict() for scene in self.scenes]
        return data


@dataclass
class Batch:
    batch_id: str
    status: str
    image_model: str
    review_mode: str = "full_validation"
    cost_estimates: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    final_video_paths: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Batch":
        return cls(
            batch_id=str(data["batch_id"]),
            status=str(data["status"]),
            image_model=str(data["image_model"]),
            review_mode=str(data.get("review_mode", "full_validation")),
            cost_estimates=[dict(item) for item in data.get("cost_estimates", [])],
            errors=[str(item) for item in data.get("errors", [])],
            final_video_paths=[str(item) for item in data.get("final_video_paths", [])],
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CostEstimate:
    text_usd: float
    images_usd: float
    voice_usd: float

    @property
    def total_usd(self) -> float:
        return round(self.text_usd + self.images_usd + self.voice_usd, 4)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["total_usd"] = self.total_usd
        return data


@dataclass
class CheckResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
