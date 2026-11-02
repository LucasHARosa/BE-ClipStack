"""Classe escolhida por settings.VIDEO_PROCESSOR_CLASS (fake em dev/testes, ffmpeg real)."""

import io
import json
import shutil
import subprocess  # noqa: S404  (chamadas com lista de argumentos, sem shell)
import time
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.utils.module_loading import import_string
from PIL import Image, ImageDraw

from apps.processing.exceptions import ProcessingError, TransientProcessingError


@dataclass(frozen=True)
class ProcessingResult:
    duration_seconds: int | None
    resolution: str
    thumbnail: bytes | None  # JPEG


class BaseVideoProcessor:
    def process(self, file_path: str, on_progress) -> ProcessingResult:
        raise NotImplementedError


class FakeVideoProcessor(BaseVideoProcessor):
    steps = 5

    def process(self, file_path, on_progress):
        size = Path(file_path).stat().st_size
        if size == 0:
            raise ProcessingError("Arquivo vazio ou corrompido.")
        for step in range(1, self.steps + 1):
            time.sleep(settings.FAKE_PROCESSOR_STEP_SECONDS)
            on_progress(step * 100 // self.steps)
        return ProcessingResult(
            duration_seconds=max(1, size // 100_000),
            resolution="1280x720",
            thumbnail=_placeholder_thumbnail(Path(file_path).stem),
        )


class FfmpegVideoProcessor(BaseVideoProcessor):
    timeout_seconds = 120

    def process(self, file_path, on_progress):
        if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
            # Temporário: outro worker pode ter o binário.
            raise TransientProcessingError("ffmpeg/ffprobe não encontrados no PATH.")
        on_progress(10)
        probe = self._run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height:format=duration",
                "-of",
                "json",
                file_path,
            ]
        )
        info = json.loads(probe)
        streams = info.get("streams") or []
        if not streams:
            raise ProcessingError("O arquivo não tem trilha de vídeo.")
        width, height = streams[0]["width"], streams[0]["height"]
        duration = float(info.get("format", {}).get("duration") or 0)
        on_progress(50)
        at = min(3.0, duration * 0.1)
        thumbnail = self._run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-ss",
                f"{at:.2f}",
                "-i",
                file_path,
                "-frames:v",
                "1",
                "-vf",
                "scale=480:-2",
                "-f",
                "image2",
                "-vcodec",
                "mjpeg",
                "pipe:1",
            ],
            binary=True,
        )
        on_progress(90)
        return ProcessingResult(
            duration_seconds=round(duration) or None,
            resolution=f"{width}x{height}",
            thumbnail=thumbnail or None,
        )

    def _run(self, args, binary=False):
        try:
            result = subprocess.run(  # noqa: S603
                args, capture_output=True, check=True, timeout=self.timeout_seconds
            )
        except subprocess.TimeoutExpired as exc:
            raise TransientProcessingError("ffmpeg excedeu o tempo limite.") from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode(errors="replace").strip()[:500]
            raise ProcessingError(f"ffmpeg falhou: {stderr}") from exc
        return result.stdout if binary else result.stdout.decode()


def get_video_processor() -> BaseVideoProcessor:
    return import_string(settings.VIDEO_PROCESSOR_CLASS)()


def _placeholder_thumbnail(label):
    image = Image.new("RGB", (480, 270), color=(36, 41, 56))
    ImageDraw.Draw(image).text((20, 120), f"ClipStack - {label[:30]}", fill=(230, 230, 230))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=80)
    return buffer.getvalue()
