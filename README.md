# Shorts Super-Heroes

Semi-automatic pipeline for batches of 4 original superhero shorts for kids.

## Local Commands

Use Python:

```powershell
& "C:\Users\muril\AppData\Local\Programs\Python\Python310\python.exe" -m shorts_superheroes.cli --help
```

Set `PYTHONPATH` when running from the vault root:

```powershell
$env:PYTHONPATH="projects\shorts-superheroes\src"
```

Create a local `.env` file from `.env.example` for real API runs:

```powershell
Copy-Item projects\shorts-superheroes\.env.example projects\shorts-superheroes\.env
notepad projects\shorts-superheroes\.env
```

The CLI, local worker, and n8n importer load `projects/shorts-superheroes/.env` automatically. Existing shell environment variables take priority over `.env` values.

## MVP Stages

1. Draft stories and review scripts/prompts.
2. Generate images and review image consistency.
3. Generate narration and render MP4 files.

TikTok posting is manual in the MVP.

## Local Worker

Start the local worker before running the n8n stages:

```powershell
$env:PYTHONPATH="projects\shorts-superheroes\src"
& "C:\Users\muril\AppData\Local\Programs\Python\Python310\python.exe" -m shorts_superheroes.worker --host 127.0.0.1 --port 8765
```

If n8n runs in Docker, call the worker from n8n as:

```text
http://host.docker.internal:8765/run-stage
```

## n8n Workflows

The MVP uses a manual review gate between each stage:

- `n8n-workflows/shorts-superheroes-draft.json` creates the story batch.
- `n8n-workflows/shorts-superheroes-assets.json` generates images, then audio, after draft review.
- `n8n-workflows/shorts-superheroes-render.json` renders final videos after image review.

Import the three JSON files through the n8n UI, or fill `N8N_API_KEY` in `.env` and run:

```powershell
& "C:\Users\muril\AppData\Local\Programs\Python\Python310\python.exe" projects\shorts-superheroes\n8n-workflows\create-shorts-superheroes.py
```

If your shell is already inside the `projects/shorts-superheroes` repo, run:

```powershell
& "C:\Users\muril\AppData\Local\Programs\Python\Python310\python.exe" n8n-workflows\create-shorts-superheroes.py
```
