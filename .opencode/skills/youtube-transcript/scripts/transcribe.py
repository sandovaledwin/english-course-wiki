#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "click>=8.1.7",
#     "youtube-transcript-api>=0.6.2",
# ]
# ///

import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import click
from youtube_transcript_api import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    YouTubeTranscriptApi,
)


def extract_video_id(url_or_id: str) -> Optional[str]:
    """Extract an 11-character YouTube video ID from various URL formats or bare ID."""
    clean_input = url_or_id.strip()
    patterns = [
        r"(?:v=|\/v\/|embed\/|shorts\/)([a-zA-Z0-9_-]{11})",
        r"youtu\.be\/([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, clean_input)
        if match:
            return match.group(1)
    return None


def fetch_video_metadata(video_id: str) -> Dict[str, str]:
    """Fetch video title and channel name using YouTube's public oEmbed API."""
    canonical_url = f"https://www.youtube.com/watch?v={video_id}"
    oembed_url = (
        f"https://www.youtube.com/oembed?url={urllib.parse.quote(canonical_url)}&format=json"
    )
    req = urllib.request.Request(
        oembed_url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; YouTubeTranscriptCLI/1.0)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            return {
                "title": data.get("title", f"YouTube Video {video_id}").strip(),
                "author": data.get("author_name", "YouTube Channel").strip(),
            }
    except Exception:
        return {
            "title": f"YouTube Video {video_id}",
            "author": "YouTube Channel",
        }


def slugify(text: str) -> str:
    """Normalize and convert text into a clean kebab-case filename slug."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text[:80] if text else "video"


def format_seconds(seconds: float) -> str:
    """Format seconds into [HH:MM:SS] or [MM:SS]."""
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def build_transcript_text(transcript_data: List[dict], with_timestamps: bool) -> str:
    """Format the list of transcript segment dicts into clean text or timestamped lines."""
    if with_timestamps:
        lines = []
        for segment in transcript_data:
            time_tag = format_seconds(segment.get("start", 0.0))
            text = segment.get("text", "").strip()
            if text:
                lines.append(f"**[{time_tag}]** {text}")
        return "\n\n".join(lines)

    # Narrative flow: group lines into paragraphs
    paragraphs = []
    current_sentences = []
    current_length = 0

    for segment in transcript_data:
        text = segment.get("text", "").strip()
        if not text:
            continue
        current_sentences.append(text)
        current_length += len(text)

        # Break paragraph after ~400 chars or if sentence ends with a period/question/exclamation
        if current_length >= 400 and text.endswith((".", "!", "?")):
            paragraphs.append(" ".join(current_sentences))
            current_sentences = []
            current_length = 0

    if current_sentences:
        paragraphs.append(" ".join(current_sentences))

    return "\n\n".join(paragraphs)


def create_markdown_document(
    title: str,
    video_id: str,
    author: str,
    transcript_body: str,
    today_str: str,
) -> str:
    """Generate Markdown content conforming to wiki raw-reference standards."""
    safe_title = title.replace('"', '\\"')
    safe_author = author.replace('"', '\\"')

    frontmatter = f"""---
title: "{safe_title}"
source: "https://www.youtube.com/watch?v={video_id}"
author: "{safe_author}"
published: {today_str}
type: raw-reference
tags:
  - youtube-transcript
  - video
---

# {title}

**Source:** [https://www.youtube.com/watch?v={video_id}](https://www.youtube.com/watch?v={video_id})  
**Channel:** {author}  
**Video ID:** `{video_id}`  

## Transcript

{transcript_body}
"""
    return frontmatter


@click.command(
    name="transcribe",
    help="Extract transcripts from YouTube URLs and save them as markdown reference files.",
)
@click.argument("urls", nargs=-1, required=True)
@click.option(
    "-o",
    "--output-dir",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=Path("references"),
    show_default=True,
    help="Directory to save the markdown transcript files.",
)
@click.option(
    "-l",
    "--languages",
    default="en,es",
    show_default=True,
    help="Comma-separated preferred language codes in priority order.",
)
@click.option(
    "--timestamps/--no-timestamps",
    default=False,
    show_default=True,
    help="Include timestamp markers in the transcript.",
)
@click.option(
    "--overwrite/--no-overwrite",
    default=False,
    show_default=True,
    help="Overwrite existing output files if they already exist.",
)
def main(
    urls: Tuple[str, ...],
    output_dir: Path,
    languages: str,
    timestamps: bool,
    overwrite: bool,
) -> None:
    """Process a list of YouTube URLs, retrieve transcripts, and save markdown files."""
    lang_list = [code.strip() for code in languages.split(",") if code.strip()]
    if not lang_list:
        lang_list = ["en", "es"]

    output_dir.mkdir(parents=True, exist_ok=True)
    today_str = date.today().isoformat()

    success_count = 0
    fail_count = 0

    for raw_url in urls:
        video_id = extract_video_id(raw_url)
        if not video_id:
            click.secho(f"[ERROR] Could not extract video ID from: '{raw_url}'", fg="red", err=True)
            fail_count += 1
            continue

        click.echo(f"Processing video ID: {video_id}...")

        # 1. Fetch metadata
        metadata = fetch_video_metadata(video_id)
        title = metadata["title"]
        author = metadata["author"]
        click.echo(f"  Title: {title}")
        click.echo(f"  Channel: {author}")

        # 2. Fetch transcript
        try:
            if hasattr(YouTubeTranscriptApi, "get_transcript"):
                transcript_data = YouTubeTranscriptApi.get_transcript(
                    video_id, languages=lang_list
                )
            else:
                fetched = YouTubeTranscriptApi().fetch(
                    video_id, languages=lang_list
                )
                if hasattr(fetched, "to_raw_data"):
                    transcript_data = fetched.to_raw_data()
                else:
                    transcript_data = [
                        {
                            "text": getattr(s, "text", ""),
                            "start": getattr(s, "start", 0.0),
                            "duration": getattr(s, "duration", 0.0),
                        }
                        for s in fetched
                    ]
        except TranscriptsDisabled:
            click.secho(f"  [FAIL] Transcripts are disabled for video {video_id}.", fg="red", err=True)
            fail_count += 1
            continue
        except NoTranscriptFound:
            click.secho(
                f"  [FAIL] No transcript found for languages {lang_list} on video {video_id}.",
                fg="red",
                err=True,
            )
            fail_count += 1
            continue
        except VideoUnavailable:
            click.secho(f"  [FAIL] Video {video_id} is unavailable or private.", fg="red", err=True)
            fail_count += 1
            continue
        except CouldNotRetrieveTranscript as e:
            click.secho(f"  [FAIL] Could not retrieve transcript for {video_id}: {e}", fg="red", err=True)
            fail_count += 1
            continue
        except Exception as e:
            click.secho(f"  [FAIL] Unexpected error fetching transcript for {video_id}: {e}", fg="red", err=True)
            fail_count += 1
            continue

        # 3. Format transcript & document
        body_text = build_transcript_text(transcript_data, with_timestamps=timestamps)
        markdown_content = create_markdown_document(
            title=title,
            video_id=video_id,
            author=author,
            transcript_body=body_text,
            today_str=today_str,
        )

        # 4. Determine destination file path
        slug = slugify(title)
        filename = f"raw-{slug}.md"
        destination_path = output_dir / filename

        # If file exists and overwrite is False, add video_id suffix to avoid collisions
        if destination_path.exists() and not overwrite:
            destination_path = output_dir / f"raw-{slug}-{video_id}.md"

        try:
            destination_path.write_text(markdown_content, encoding="utf-8")
            click.secho(f"  [SAVED] -> {destination_path}", fg="green")
            success_count += 1
        except Exception as e:
            click.secho(f"  [ERROR] Failed writing to {destination_path}: {e}", fg="red", err=True)
            fail_count += 1

    click.echo("\nFinished processing transcripts.")
    click.echo(f"  Successfully processed: {success_count}")
    if fail_count > 0:
        click.echo(f"  Failed: {fail_count}")


if __name__ == "__main__":
    main()
