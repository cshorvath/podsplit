# podsplit

Split an audio file, direct HTTP(S) audio URL, or yt-dlp-supported webpage URL into numbered MP3 files.
Requires Python 3.10+ and FFmpeg with the `libmp3lame` encoder on your PATH.
On Debian/Ubuntu, install FFmpeg with `sudo apt install ffmpeg`.

Install the command on your PATH (includes yt-dlp):

```sh
pipx install .
pipx ensurepath
```

Restart your terminal after `ensurepath`. To update an existing installation,
run `pipx install --force .` from this directory.

Run directly (local files and direct media URLs need no Python dependencies;
webpage URLs require yt-dlp installed in the current Python or on PATH):

```sh
python3 podsplit.py recording.m4a
python3 podsplit.py recording.wav --duration 5m --output ./parts
python3 podsplit.py 'https://example.com/episode.mp3' -d 600 -o ./episode
```

Or install the command in a virtual environment:

```sh
python3 -m venv .venv
.venv/bin/pip install .
.venv/bin/podsplit recording.mp3
```

`--duration` / `-d` accepts seconds (e.g. `600`) or a number followed by
`s`, `m`, or `h` (e.g. `90s`, `2.5m`, `1h`). The default is 10 minutes.
`--output` / `-o` defaults to `<input-name>_chunks` in the current directory.

Output files are `chunk_0001.mp3`, `chunk_0002.mp3`, and so on. Audio is
re-encoded to variable-bitrate MP3 (FFmpeg quality 2), using the first audio
track. Chunk boundaries follow MP3 frames, so lengths can differ slightly
from the requested duration. The last chunk contains the remaining audio.
FFmpeg tries URLs directly first. If that fails, podsplit uses
[yt-dlp](https://github.com/yt-dlp/yt-dlp) to download the best available audio
to a temporary folder, then splits it with FFmpeg. Video webpage links are
supported wherever yt-dlp can extract them. A video link with a playlist
downloads only the video; standalone playlists are not supported.
Temporary downloads and staged chunks are cleaned up after processing.

Existing `chunk_*.mp3` files cause the command to stop without overwriting
them. If processing fails or is interrupted, partial chunks may remain;
remove them or choose a new output directory before retrying.

Run tests (requires FFmpeg and FFprobe):

```sh
python3 -m unittest discover -s tests -v
```
