from __future__ import annotations

from pathlib import Path
import shutil
import subprocess


def resolve_ffmpeg_executable() -> str:
    executable = shutil.which("ffmpeg")
    if executable:
        return executable

    try:
        import imageio_ffmpeg
    except ImportError:
        return "ffmpeg"

    return str(imageio_ffmpeg.get_ffmpeg_exe())


def build_render_command(
    image_paths: list[Path],
    audio_path: Path,
    output_path: Path,
    scene_duration_sec: int,
) -> list[str]:
    if not image_paths:
        raise ValueError("image_paths must not be empty")

    command = [resolve_ffmpeg_executable(), "-y"]
    for image_path in image_paths:
        command.extend(["-loop", "1", "-t", str(scene_duration_sec), "-i", str(image_path)])

    command.extend(["-i", str(audio_path)])
    stream_count = len(image_paths)
    video_filters = []
    for index in range(stream_count):
        video_filters.append(
            f"[{index}:v]scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,setsar=1,format=yuv420p[v{index}]"
        )

    concat_inputs = "".join(f"[v{index}]" for index in range(stream_count))
    filter_complex = ";".join(video_filters) + f";{concat_inputs}concat=n={stream_count}:v=1:a=0[vout]"
    audio_index = stream_count
    command.extend(
        [
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
            "-map",
            f"{audio_index}:a",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )
    return command


def render_video(
    image_paths: list[Path],
    audio_path: Path,
    output_path: Path,
    scene_duration_sec: int,
    dry_run: bool,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = build_render_command(image_paths, audio_path, output_path, scene_duration_sec)
    if dry_run:
        output_path.write_text("DRY RUN VIDEO\n" + " ".join(command) + "\n", encoding="utf-8")
        return output_path

    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {completed.stderr[-2000:]}")
    return output_path
