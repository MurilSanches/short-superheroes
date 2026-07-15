import json
import os
from pathlib import Path
import sys
import urllib.request


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from shorts_superheroes.env import load_dotenv


load_dotenv(PROJECT_ROOT / ".env")
N8N_URL = os.environ.get("N8N_URL", "http://localhost:5678")
N8N_KEY = os.environ["N8N_API_KEY"]


def post_workflow(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{N8N_URL.rstrip('/')}/api/v1/workflows",
        data=data,
        method="POST",
        headers={"X-N8N-API-KEY": N8N_KEY, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    for name in [
        "shorts-superheroes-draft.json",
        "shorts-superheroes-assets.json",
        "shorts-superheroes-render.json",
    ]:
        result = post_workflow(ROOT / name)
        print(f"created {result.get('id')} {result.get('name')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
