import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from shorts_superheroes.env import load_dotenv


class EnvTests(unittest.TestCase):
    def test_load_dotenv_reads_values_comments_and_quotes(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "# local secrets",
                        "OPENAI_API_KEY=sk-test",
                        'ELEVENLABS_API_KEY="eleven-test"',
                        "N8N_URL=http://localhost:5678 # local n8n",
                        "export N8N_API_KEY=n8n-test",
                        "INVALID_LINE",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                loaded = load_dotenv(env_path)

                self.assertEqual(loaded["OPENAI_API_KEY"], "sk-test")
                self.assertEqual(os.environ["ELEVENLABS_API_KEY"], "eleven-test")
                self.assertEqual(os.environ["N8N_URL"], "http://localhost:5678")
                self.assertEqual(os.environ["N8N_API_KEY"], "n8n-test")
                self.assertNotIn("INVALID_LINE", os.environ)

    def test_load_dotenv_does_not_override_existing_values_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("OPENAI_API_KEY=from-file\n", encoding="utf-8")

            with patch.dict(os.environ, {"OPENAI_API_KEY": "from-shell"}, clear=True):
                loaded = load_dotenv(env_path)

                self.assertEqual(loaded["OPENAI_API_KEY"], "from-file")
                self.assertEqual(os.environ["OPENAI_API_KEY"], "from-shell")


if __name__ == "__main__":
    unittest.main()
