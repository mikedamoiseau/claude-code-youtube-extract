import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "yt-extract.py"
spec = importlib.util.spec_from_file_location("yt_extract", MODULE_PATH)
yt_extract = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(yt_extract)


def test_slugify_basic_behavior():
    assert yt_extract.slugify("Hello, World!") == "hello-world"
    assert yt_extract.slugify("A" * 60) == "a" * 50


def test_timestamp_formatters_and_parser():
    assert yt_extract.format_timestamp_display(65) == "1:05"
    assert yt_extract.format_timestamp_display(3723) == "1:02:03"
    assert yt_extract.format_timestamp_filename(65) == "01m05s"
    assert yt_extract.format_timestamp_filename(3723) == "1h02m03s"
    assert yt_extract.parse_timestamp("1:05") == 65
    assert yt_extract.parse_timestamp("1:02:03") == 3723


def test_render_transcript_info_uses_integer_minutes_for_long_videos():
    rendered = yt_extract.render_transcript_info("manual (en)", 3723.9)
    assert rendered == "### Transcript Info\nmanual (en)\nVideo is 62 min long — full transcript\n"


def test_render_screenshots_section_with_chapter_titles():
    rendered = yt_extract.render_screenshots_section(
        True,
        "",
        [(30, "001_00m30s_intro.png")],
        [{"start_time": 0, "end_time": 60, "title": "Intro"}],
        120,
    )
    assert rendered == (
        "### Screenshots\n"
        "- ![0:30 — Intro](screenshots/001_00m30s_intro.png) 0:30 — Intro\n"
        ""
    )


def test_render_screenshot_status_success_and_warning():
    rendered = yt_extract.render_screenshot_status(
        True,
        "",
        2,
        [(30, "001.png")],
        ["Frame at 1:00 failed: timeout"],
    )
    assert rendered == (
        "### Screenshot Status\n"
        "2 screenshots requested, 1 successfully extracted.\n"
        "- WARNING: Frame at 1:00 failed: timeout\n"
        ""
    )


def test_render_comments_modes():
    assert yt_extract.render_comments(False, []) == "### Comments\nSKIPPED"
    assert yt_extract.render_comments(True, []) == "### Comments\nComments not available."
    assert yt_extract.render_comments(True, [{"author": "Alice", "likes": 4, "text": "Useful"}]) == (
        "### Comments\n1. **Alice** (👍 4) — Useful"
    )
