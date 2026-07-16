import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = PROJECT_ROOT / "n8n-workflows"


def _set_node_boolean(workflow_name: str, node_name: str, value_name: str) -> bool:
    workflow = json.loads((WORKFLOWS_DIR / workflow_name).read_text(encoding="utf-8"))
    for node in workflow["nodes"]:
        if node["name"] != node_name:
            continue
        for item in node["parameters"]["values"]["boolean"]:
            if item["name"] == value_name:
                return bool(item["value"])
    raise AssertionError(f"{workflow_name} missing {node_name}.{value_name}")


class N8nWorkflowTests(unittest.TestCase):
    def test_draft_assets_and_render_workflows_default_to_real_run(self):
        self.assertFalse(_set_node_boolean("shorts-superheroes-draft.json", "Set Draft Config", "dry_run"))
        self.assertFalse(_set_node_boolean("shorts-superheroes-assets.json", "Set Batch Config", "dry_run"))
        self.assertFalse(_set_node_boolean("shorts-superheroes-render.json", "Set Batch Config", "dry_run"))


if __name__ == "__main__":
    unittest.main()
