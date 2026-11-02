import shutil
import subprocess

import pytest

from apps.processing.exceptions import ProcessingError
from apps.processing.processors import (
    FakeVideoProcessor,
    FfmpegVideoProcessor,
    get_video_processor,
)


def test_di_by_settings_picks_the_class(settings):
    # override pela fixture "settings" do pytest-django: vale só neste teste.
    settings.VIDEO_PROCESSOR_CLASS = "apps.processing.processors.FfmpegVideoProcessor"
    assert isinstance(get_video_processor(), FfmpegVideoProcessor)


def test_fake_processor_reports_progress_and_thumbnail(tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"0" * 300_000)
    progress = []

    result = FakeVideoProcessor().process(str(video), progress.append)

    assert progress == [20, 40, 60, 80, 100]
    assert result.resolution == "1280x720"
    assert result.thumbnail[:2] == b"\xff\xd8"  # JPEG


def test_fake_processor_rejects_empty_file(tmp_path):
    empty = tmp_path / "vazio.mp4"
    empty.write_bytes(b"")
    with pytest.raises(ProcessingError):
        FakeVideoProcessor().process(str(empty), lambda p: None)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg não instalado")
def test_ffmpeg_processor_reads_real_metadata(tmp_path):
    video = tmp_path / "real.mp4"
    subprocess.run(  # noqa: S603
        [
            shutil.which("ffmpeg"),
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=2:size=320x240:rate=10",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ],
        check=True,
    )
    result = FfmpegVideoProcessor().process(str(video), lambda p: None)
    assert (result.duration_seconds, result.resolution) == (2, "320x240")
    assert result.thumbnail[:2] == b"\xff\xd8"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg não instalado")
def test_ffmpeg_processor_corrupted_file_is_permanent_error(tmp_path):
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"isto nao e um video")
    with pytest.raises(ProcessingError):
        FfmpegVideoProcessor().process(str(broken), lambda p: None)
