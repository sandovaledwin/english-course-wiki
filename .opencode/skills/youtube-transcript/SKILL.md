---
name: youtube-transcript
description: Download transcripts from YouTube video URLs and save them as raw markdown references. Use when given YouTube video links, URLs, or asked to fetch transcripts from YouTube.
---

# YouTube Transcript Downloader Skill

This skill extracts transcripts from one or more YouTube video URLs using the bundled CLI script powered by `uv`, `click`, and `youtube-transcript-api`. It formats the output into standard raw markdown references under `references/raw-<slug>.md`.

## CLI Tool Location

The script is located at:
`scripts/transcribe.py` (relative to this skill)
Absolute path: `.opencode/skills/youtube-transcript/scripts/transcribe.py`

## CLI Execution with `uv`

The script declares inline dependencies (`click`, `youtube-transcript-api`) following PEP 723. Run it using `uv run`:

```bash
uv run .opencode/skills/youtube-transcript/scripts/transcribe.py <url1> [url2 ...] [OPTIONS]
```

### Options

- `-o, --output-dir PATH`: Target directory to save transcript files (defaults to `references/`).
- `-l, --languages TEXT`: Comma-separated language priority list (defaults to `en,es`).
- `--timestamps / --no-timestamps`: Include timestamp markers `**[MM:SS]**` (default: `--no-timestamps` for clean readable paragraphs).
- `--overwrite / --no-overwrite`: Overwrite existing files (default: `--no-overwrite`, appends video ID on collision).

## Workflow

1. **Extract YouTube URLs**:
   Identify all YouTube video links or video IDs provided by the user (supports `youtube.com/watch?v=...`, `youtu.be/...`, `youtube.com/shorts/...`, etc.).

2. **Execute Transcribe CLI**:
   Run the CLI command using `bash`:
   ```bash
   uv run .opencode/skills/youtube-transcript/scripts/transcribe.py "<url1>" "<url2>"
   ```
   If timestamps are requested by the user, add `--timestamps`.
   If a specific language is requested (e.g., Spanish, French), specify `-l es` or `-l fr,en`.

3. **Verify Generated Files**:
   Inspect the command output to identify the saved file paths (e.g., `references/raw-<slug>.md`). Use `read` or `glob` to verify the generated files exist and contain valid metadata and transcripts.

4. **Suggest Next Step (Knowledge Synthesis)**:
   Once the raw transcripts are saved, inform the user of the created files. You can recommend running `/resumeraw references/raw-<slug>.md` to distill each transcript into an executive-level knowledge note in the wiki and register it in `index.md`.

## Output Document Standard

Each generated file follows the wiki raw-reference schema:

```yaml
---
title: "<Video Title>"
source: "https://www.youtube.com/watch?v=<video_id>"
author: "<Channel/Author>"
published: YYYY-MM-DD
type: raw-reference
tags:
  - youtube-transcript
  - video
---

# <Video Title>

**Source:** [https://www.youtube.com/watch?v=<video_id>](https://www.youtube.com/watch?v=<video_id>)  
**Channel:** <Channel Name>  
**Video ID:** `<video_id>`  

## Transcript

<Transcript Paragraphs>
```
