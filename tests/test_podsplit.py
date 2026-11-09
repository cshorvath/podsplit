import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from podsplit import duration_seconds, split_audio


CLI = Path(__file__).resolve().parents[1] / "podsplit.py"


class DurationTests(unittest.TestCase):
    def test_units_and_invalid_values(self):
        for value, expected in [("600", 600), ("2.5m", 150), ("1h", 3600), ("30S", 30)]:
            self.assertEqual(duration_seconds(value), expected)
        for value in ["0", "-1", "nan", "inf", "10minutes", "1e9"]:
            with self.assertRaises(argparse.ArgumentTypeError):
                duration_seconds(value)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "requires FFmpeg and FFprobe")
class SplitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "input audio.wav"
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
            "-i", "sine=frequency=440:duration=2.4", str(self.source),
        ], check=True)

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)],
                              cwd=self.root, capture_output=True, text=True, timeout=20)

    def check_chunks(self, output):
        chunks = sorted(output.glob("*.mp3"))
        self.assertEqual([p.name for p in chunks], [f"chunk_{n:04d}.mp3" for n in range(1, 4)])
        durations = []
        for path in chunks:
            result = subprocess.run([
                "ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_name",
                "-of", "json", str(path),
            ], capture_output=True, text=True, check=True)
            probe = json.loads(result.stdout)
            self.assertEqual(probe["streams"][0]["codec_name"], "mp3")
            durations.append(float(probe["format"]["duration"]))
            subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"], check=True)
        for duration in durations[:2]:
            self.assertAlmostEqual(duration, 1.0, delta=0.08)
        self.assertAlmostEqual(durations[-1], 0.4, delta=0.08)
        self.assertAlmostEqual(sum(durations), 2.4, delta=0.1)

    def test_local_and_overwrite_protection(self):
        output = self.root / "parts"
        result = self.run_cli(self.source, "-d", "1s", "-o", output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.check_chunks(output)
        before = {p.name: p.read_bytes() for p in output.iterdir()}
        result = self.run_cli(self.source, "-d", "1s", "-o", output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already contains chunks", result.stderr)
        self.assertEqual(before, {p.name: p.read_bytes() for p in output.iterdir()})

    def test_http_url(self):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(self.root)))
        except PermissionError:
            self.skipTest("environment does not permit local network sockets")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/input%20audio.wav?download=1"
            result = self.run_cli(url, "-d", "1")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.check_chunks(self.root / "input audio_chunks")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_default_duration_and_output(self):
        result = self.run_cli(self.source)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(list((self.root / "input audio_chunks").glob("*.mp3"))), 1)

    def test_url_fallback_cleans_partial_chunks_and_download(self):
        output = self.root / "fallback"
        url = "https://example.com/watch?v=123"
        real_run = subprocess.run
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            if command[:3] == [sys.executable, "-m", "yt_dlp"]:
                downloaded = Path(command[command.index("-o") + 1].replace("%(ext)s", "wav"))
                shutil.copyfile(self.source, downloaded)
                return subprocess.CompletedProcess(command, 0, stdout=str(downloaded) + "\n")
            if "-i" in command and command[command.index("-i") + 1] == url:
                Path(command[-1].replace("%04d", "0001")).write_bytes(b"incomplete")
                return subprocess.CompletedProcess(command, 1)
            return real_run(command, **kwargs)

        with patch("podsplit.subprocess.run", side_effect=run), patch("podsplit.importlib.util.find_spec", return_value=object()):
            split_audio(url, 1, output)
        self.check_chunks(output)
        self.assertEqual(len(list(output.iterdir())), 3)
        download_command = calls[1]
        self.assertIn("--no-playlist", download_command)
        self.assertEqual(download_command[-2:], ["--", url])

    def test_failed_download_leaves_no_chunks_or_temp_files(self):
        output = self.root / "failed"
        with patch("podsplit.subprocess.run", return_value=subprocess.CompletedProcess([], 1)), patch("podsplit.importlib.util.find_spec", return_value=object()):
            with self.assertRaisesRegex(ValueError, "yt-dlp failed"):
                split_audio("https://example.com/watch?v=123", 1, output)
        self.assertEqual(list(output.iterdir()), [])

    def test_missing_and_invalid_audio(self):
        result = self.run_cli("missing.wav")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("input file does not exist", result.stderr)
        invalid = self.root / "invalid.wav"
        invalid.write_text("this is not audio")
        result = self.run_cli(invalid)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FFmpeg failed", result.stderr)


if __name__ == "__main__":
    unittest.main()
