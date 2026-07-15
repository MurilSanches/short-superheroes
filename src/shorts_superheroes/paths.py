from __future__ import annotations

from datetime import date
from pathlib import Path


def make_batch_id(date_value: date, sequence: int) -> str:
    if sequence < 1 or sequence > 999:
        raise ValueError("sequence must be between 1 and 999")
    return f"{date_value.isoformat()}-{sequence:03d}"


def ensure_batch_layout(root: Path, batch_id: str, video_count: int = 4) -> dict[str, Path]:
    if video_count != 4:
        raise ValueError("MVP requires exactly 4 videos per batch")
    batch_dir = root / "batches" / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)
    for index in range(1, video_count + 1):
        video_dir = batch_dir / f"video-{index:02d}"
        for name in ["images", "audio", "final"]:
            (video_dir / name).mkdir(parents=True, exist_ok=True)
    return {"batch_dir": batch_dir}
