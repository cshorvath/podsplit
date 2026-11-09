#!/usr/bin/env python3
"""Split a local or remote audio file into MP3 chunks using FFmpeg."""

import argparse
import importlib.util
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlsplit


def duration_seconds(value: str) -> float:
    """Accept seconds or a number with an s, m, or h suffix."""
    match = re.fullmatch(r"(\d+(?:\.\d+)?)([smh]?)", value.strip(), re.IGNORECASE)
    if not match:
        raise argparse.ArgumentTypeError("use seconds or a duration such as 30s, 10m, or 1h")
    seconds = float(match[1]) * {"": 1, "s": 1, "m": 60, "h": 3600}[match[2].lower()]
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("duration must be a positive, finite number")
    return seconds


def download_audio(source: str, directory: Path) -> Path:
    if importlib.util.find_spec("yt_dlp") is not None:
        downloader = [sys.executable, "-m", "yt_dlp"]
    elif executable := shutil.which("yt-dlp"):
        downloader = [executable]
    else:
        raise ValueError("URL requires yt-dlp; install podsplit with pipx install --force . or install yt-dlp on PATH")
    result = subprocess.run([
        *downloader, "--ignore-config", "--no-playlist", "--no-progress",
        "--no-simulate", "-f", "bestaudio/best",
        "-o", str(directory / "download.%(ext)s"),
        "--print", "after_move:filepath", "--", source,
    ], stdout=subprocess.PIPE, text=True, check=False)
    if result.returncode:
        raise ValueError(f"yt-dlp failed (exit {result.returncode})")
    paths = result.stdout.strip().splitlines()
    if len(paths) != 1 or not Path(paths[0]).is_file():
        raise ValueError("yt-dlp did not produce a single audio file")
    return Path(paths[0])


def split_audio(source: str, duration: float, output: Path) -> list[Path]:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise ValueError("FFmpeg is required; install it and ensure ffmpeg is on PATH")

    parsed = urlsplit(source)
    is_url = parsed.scheme.lower() in ("http", "https")
    if is_url:
        if not parsed.netloc:
            raise ValueError("URL must include a host")
        input_source = source
    else:
        input_path = Path(source).expanduser().resolve()
        if not input_path.is_file():
            raise ValueError(f"input file does not exist: {source}")
        input_source = str(input_path)

    output = output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.glob("chunk_*.mp3")):
        raise ValueError(f"output folder already contains chunks: {output}; choose another folder")

    def encode(input_source: str, target: Path) -> int:
        command = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
            "-i", input_source,
            "-map", "0:a:0", "-vn", "-map_metadata", "-1",
            "-c:a", "libmp3lame", "-q:a", "2",
            "-f", "segment", "-segment_time", str(duration),
            "-segment_start_number", "1", "-reset_timestamps", "1",
            str(target).replace("%", "%%") + "/chunk_%04d.mp3",
        ]
        # Stream diagnostics without accumulating output for long recordings.
        return subprocess.run(command, check=False).returncode

    # Stage chunks so a failed direct URL attempt cannot mix with the retry.
    with tempfile.TemporaryDirectory(prefix=".podsplit-", dir=output) as work:
        directory = Path(work)
        result = encode(input_source, directory)
        if result and is_url:
            print("Direct URL processing failed; trying yt-dlp…", file=sys.stderr)
            for chunk in directory.glob("chunk_*.mp3"):
                chunk.unlink()
            downloaded = download_audio(source, directory)
            result = encode(str(downloaded), directory)
        if result:
            raise ValueError(f"FFmpeg failed (exit {result})")
        chunks = sorted(directory.glob("chunk_*.mp3"))
        if not chunks:
            raise ValueError("FFmpeg produced no audio chunks")
        published = []
        for chunk in chunks:
            destination = output / chunk.name
            # Exclusive creation prevents overwrites even from concurrent runs.
            destination.hardlink_to(chunk)
            published.append(destination)
        return published


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="audio file path, direct audio URL, or yt-dlp-supported webpage URL")
    parser.add_argument(
        "-d", "--duration", type=duration_seconds, default=600.0,
        metavar="LENGTH", help="chunk length: seconds, 30s, 10m, 1h (default: 10m)",
    )
    parser.add_argument("-o", "--output", type=Path, help="output folder (default: <input-name>_chunks)")
    args = parser.parse_args(argv)
    source_path = unquote(urlsplit(args.input).path) if args.input.lower().startswith(("http://", "https://")) else args.input
    stem = Path(source_path).stem or "audio"
    output = args.output or Path(f"{stem}_chunks")
    try:
        chunks = split_audio(args.input, args.duration, output)
    except (ValueError, OSError) as exc:
        print(f"podsplit: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\npodsplit: interrupted; partial chunks may remain in the output folder", file=sys.stderr)
        return 130
    print(f"Created {len(chunks)} MP3 chunk(s) in {chunks[0].parent}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
