from __future__ import annotations

import importlib.util
import json
import subprocess
import unittest
import wave
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "build_unified_delivery.py"
SPEC = importlib.util.spec_from_file_location("build_unified_delivery", SCRIPT_PATH)
assert SPEC and SPEC.loader
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)


def _write_test_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(24_000)
        output.writeframes(b"\0\0" * 2_400)


class UnifiedDeliveryAudioTests(unittest.TestCase):
    def test_transcode_creates_and_validates_real_pcm_wav(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.mp3"
            destination = root / "delivery.wav"
            source.write_bytes(b"tracked mp3 fixture")

            def fake_ffmpeg(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                self.assertEqual(command[0], "ffmpeg-test")
                self.assertIn("pcm_s16le", command)
                self.assertEqual(Path(command[-1]), destination)
                _write_test_wav(destination)
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch.object(BUILD.subprocess, "run", side_effect=fake_ffmpeg):
                result = BUILD._transcode_to_pcm_wav(
                    source,
                    destination,
                    ffmpeg_executable="ffmpeg-test",
                )

            self.assertEqual(result, destination)
            self.assertTrue(BUILD._is_valid_wav(destination))

    def test_invalid_wav_header_is_rejected(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            invalid_wav = Path(temporary_directory) / "invalid.wav"
            invalid_wav.write_bytes(b"not a wav")
            self.assertFalse(BUILD._is_valid_wav(invalid_wav))

    def test_acceptance_rejects_a_wav_extension_without_pcm_audio(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory)
            invalid_wav = target / "04_音视频翻译" / "renamed-file.wav"
            invalid_wav.parent.mkdir(parents=True)
            invalid_wav.write_bytes(b"not a wav")
            records = [
                {
                    "任务通道": channel,
                    "格式": "WAV" if channel == "04_音视频翻译" else "JSON",
                    "大小Bytes": 9,
                    "SHA256": "a" * 64,
                    "相对路径": (
                        "04_音视频翻译/renamed-file.wav"
                        if channel == "04_音视频翻译"
                        else f"{channel}/evidence.json"
                    ),
                }
                for channel in ("01_图文翻译", "02_术语与风格", "03_DOCX翻译", "04_音视频翻译")
            ]
            (target / "05_资源索引").mkdir()

            with patch.object(BUILD, "TARGET", target):
                with self.assertRaises(RuntimeError):
                    BUILD._write_acceptance(records)

            acceptance = json.loads(
                (target / "05_资源索引" / "最终验收.json").read_text(encoding="utf-8")
            )
            self.assertFalse(acceptance["passed"])
            self.assertEqual(acceptance["generated_wav_count"], 0)


if __name__ == "__main__":
    unittest.main()
