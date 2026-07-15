from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from shorts_superheroes.clients import DryRunImageClient, DryRunStoryClient, DryRunTtsClient, OpenAIStoryClient
from shorts_superheroes.env import load_dotenv
from shorts_superheroes.models import load_json
from shorts_superheroes.pipeline import draft_batch, generate_audio, generate_images, render_batch


DEFAULT_SETTINGS_PATH = Path("projects/shorts-superheroes/config/settings.example.json")
DEFAULT_PROJECT_ROOT = Path("projects/shorts-superheroes")


def run_stage(payload: dict) -> dict:
    load_dotenv()
    stage = str(payload["stage"])
    dry_run = bool(payload.get("dry_run", False))

    if stage == "draft-batch":
        settings = load_json(Path(payload.get("settings", DEFAULT_SETTINGS_PATH)))
        project_root = Path(payload.get("project_root", DEFAULT_PROJECT_ROOT))
        story_client = (
            DryRunStoryClient()
            if dry_run
            else OpenAIStoryClient(
                api_key=os.environ["OPENAI_API_KEY"],
                model=settings["openai"]["text_model"],
            )
        )
        batch_dir = draft_batch(
            project_root,
            str(payload["batch_id"]),
            str(payload.get("theme_seed", "kindness and teamwork")),
            settings,
            story_client,
            str(payload.get("image_model", settings["openai"]["image_model_default"])),
        )
        return {"ok": True, "stage": stage, "batch_dir": str(batch_dir)}

    batch_dir = Path(str(payload["batch_dir"]))
    if stage == "generate-images":
        if not dry_run:
            raise ValueError("HTTP worker real image generation will be enabled after CLI real-run validation")
        generate_images(batch_dir, DryRunImageClient())
    elif stage == "generate-audio":
        if not dry_run:
            raise ValueError("HTTP worker real audio generation will be enabled after CLI real-run validation")
        generate_audio(batch_dir, DryRunTtsClient())
    elif stage == "render-batch":
        render_batch(batch_dir, dry_run=dry_run)
    else:
        raise ValueError(f"unknown stage: {stage}")

    return {"ok": True, "stage": stage, "batch_dir": str(batch_dir)}


class WorkerHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw.decode("utf-8"))
            if self.path == "/health":
                self._send_json(200, {"ok": True})
            elif self.path == "/run-stage":
                self._send_json(200, run_stage(payload))
            else:
                self._send_json(404, {"ok": False, "error": "not_found"})
        except Exception as exc:
            self._send_json(500, {"ok": False, "error": str(exc)})

    def log_message(self, format: str, *args) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), WorkerHandler)
    print(f"shorts-superheroes worker listening on http://{args.host}:{args.port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
