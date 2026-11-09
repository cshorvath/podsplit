# podsplit

Turn a long recording into smaller MP3 files with one command.
Give podsplit a local audio file or a link, and it creates **10-minute chunks**
by default. You can choose a different length and output folder.

## Install

You need **Python 3.10 or newer**, **FFmpeg**, and **pipx**.
FFmpeg handles the audio conversion; pipx makes the `podsplit` command
available from any folder.

On Ubuntu or Debian, install the prerequisites:

```sh
sudo apt install python3 pipx ffmpeg
```

Then, from the folder containing this README, run:

```sh
pipx install .
pipx ensurepath
```

Restart your terminal, then check that it works:

```sh
podsplit --help
```

Installation includes [yt-dlp](https://github.com/yt-dlp/yt-dlp), which podsplit
uses automatically for webpage links when FFmpeg cannot read them directly.

## Split your first recording

```sh
podsplit recording.mp3
```

This creates a `recording_chunks` folder in your current directory:

```text
recording_chunks/
  chunk_0001.mp3
  chunk_0002.mp3
  chunk_0003.mp3
  ...
```

Each chunk is about 10 minutes long. The last chunk holds whatever remains,
so a 25-minute recording produces two roughly 10-minute chunks and one
roughly 5-minute chunk. Your original file stays unchanged.

## Examples

**Make 5-minute chunks:**

```sh
podsplit recording.m4a --duration 5m
```

**Choose where the chunks go:**

```sh
podsplit recording.wav -d 5m --output ./my-chunks
```

**Split audio from a direct link:**

```sh
podsplit 'https://example.com/episode.mp3' -o ./episode
```

**Use a video webpage link:**

```sh
podsplit 'https://www.youtube.com/watch?v=VIDEO_ID' -d 10m -o ./episode
```

Replace the example URL with your own. Webpage support depends on yt-dlp's
ability to download that link. A video link containing a playlist downloads
only that video; standalone playlists are not supported.

**Use a filename containing spaces:**

```sh
podsplit 'My recording.mp3' -d 90s
```

## Options

```text
podsplit INPUT [-d LENGTH] [-o FOLDER]
```

| Option | What it does | Default |
| --- | --- | --- |
| `INPUT` | Local audio file or HTTP(S) URL | Required |
| `-d`, `--duration` | Length of each chunk | `10m` |
| `-o`, `--output` | Folder for the MP3 files; created if needed | `<input-name>_chunks` |
| `-h`, `--help` | Show command help | — |

Lengths can be given in seconds or with a unit:

| Value | Chunk length |
| --- | --- |
| `600` | 10 minutes |
| `90s` | 90 seconds |
| `2.5m` | 2 minutes, 30 seconds |
| `1h` | 1 hour |

## What to expect

- Output is always MP3, even when the input is another audio format.
- Chunk lengths can vary slightly because MP3 audio is split at frame boundaries.
- If the input has multiple audio tracks, podsplit uses the first one.
- Existing `chunk_*.mp3` files are never overwritten. Choose a different output
  folder to keep an earlier run.
- Webpage downloads use temporary disk space for the downloaded media.
  Temporary files are removed when processing finishes or fails.

## Troubleshooting

**`podsplit: command not found`**

Run `pipx ensurepath`, then close and reopen your terminal.

**FFmpeg is missing**

Install FFmpeg and check that `ffmpeg -version` works in your terminal.
Your FFmpeg installation must include the `libmp3lame` MP3 encoder.

**The output folder already contains chunks**

Choose a new folder with `-o ./another-folder`, or move the old chunks before
trying again. If processing was interrupted while publishing files, some
chunks may already be in the output folder.

**A webpage link fails to download**

Check that the link works and update yt-dlp:

```sh
pipx runpip podsplit install --upgrade yt-dlp
```

## Update podsplit

From the project folder, reinstall the current code:

```sh
pipx install --force .
```

## Run without pipx

You can run the script directly for local files and direct media URLs:

```sh
python3 podsplit.py recording.mp3 -d 5m
```

For webpage links, yt-dlp must be installed in the same Python environment
or available as a `yt-dlp` command. To install everything in a virtual environment:

```sh
python3 -m venv .venv
.venv/bin/pip install .
.venv/bin/podsplit recording.mp3
```

## Development

Run the tests with FFmpeg and FFprobe installed:

```sh
python3 -m unittest discover -s tests -v
```
