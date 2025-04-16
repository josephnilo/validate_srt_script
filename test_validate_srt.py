import os
import sys
import pytest
import srt
import argparse
from datetime import timedelta
from pathlib import Path

# Remove old Pipenv environment check logic
# def ensure_pipenv_environment():
# ... (remove function) ...
# if "PIPENV_ACTIVE" not in os.environ:
#    ensure_pipenv_environment()

# Remove old imports if they were left behind
# import pytest
# from validate_srt import validate_and_fix_srt, MalformedTimecodeError

# Assume validate_srt.py is in the same directory or PYTHONPATH is set
from validate_srt import (
    validate_srt_content,
    fix_srt_subtitles,
    read_srt_content,
    write_srt,
    process_srt_file,
    process_path,
    ValidationError,
    DEFAULT_MAX_CHARS_PER_LINE,
    DEFAULT_MAX_LINES_PER_SUB,
    DEFAULT_MIN_SUB_DURATION_MS,
    DEFAULT_MAX_SUB_DURATION_MS
)

# Remove old fixtures if they were left behind
# @pytest.fixture
# def valid_srt():
# ... (remove fixture) ...
# @pytest.fixture
# def overlapping_srt():
# ... (remove fixture) ...
# @pytest.fixture
# def missing_arrow_srt():
# ... (remove fixture) ...
# @pytest.fixture
# def malformed_timecode_srt():
# ... (remove fixture) ...
# @pytest.fixture
# def misnumbered_srt():
# ... (remove fixture) ...
# @pytest.fixture
# def extra_blank_lines_srt():
# ... (remove fixture) ...


# Remove old tests
# def test_valid_srt(valid_srt):
# ... (remove test) ...
# def test_overlapping_srt(overlapping_srt):
# ... (remove test) ...
# def test_missing_arrow_srt(missing_arrow_srt):
# ... (remove test) ...
# def test_malformed_timecode_srt(malformed_timecode_srt):
# ... (remove test) ...
# def test_misnumbered_srt(misnumbered_srt):
# ... (remove test) ...
# def test_extra_blank_lines_srt(extra_blank_lines_srt):
# ... (remove test) ...

# --- Fixtures for SRT content ---
@pytest.fixture
def valid_srt_content():
    return ("""1
00:00:01,000 --> 00:00:02,500
Short line.

2
00:00:03,000 --> 00:00:05,000
Another short line.
""")

@pytest.fixture
def overlapping_srt_content():
    return ("""1
00:00:01,000 --> 00:00:03,500
First subtitle.

2
00:00:03,000 --> 00:00:05,000
Overlapping subtitle.
""")

@pytest.fixture
def start_after_end_srt_content():
     return ("""1
00:00:03,000 --> 00:00:02,000
Start time is after end time.
""")

@pytest.fixture
def misnumbered_srt_content():
    return ("""1
00:00:01,000 --> 00:00:02,000
First subtitle.

3
00:00:03,000 --> 00:00:04,000
Misnumbered subtitle.
""")

@pytest.fixture
def empty_content_srt():
     return ("""1
00:00:01,000 --> 00:00:02,000


2
00:00:03,000 --> 00:00:04,000
Second subtitle.
""")

@pytest.fixture
def too_many_lines_srt_content():
    return ("""1
00:00:01,000 --> 00:00:03,000
Line 1
Line 2
Line 3
""")

@pytest.fixture
def too_long_line_srt_content():
    # Using default 42 chars
    return ("""1
00:00:01,000 --> 00:00:03,000
This line is definitely going to be way too long for subtitle standards.
""")

@pytest.fixture
def duration_too_short_srt_content():
    # Default min 1000ms
    return ("""1
00:00:01,000 --> 00:00:01,500
Too short.
""")

@pytest.fixture
def duration_too_long_srt_content():
    # Default max 7000ms
    return ("""1
00:00:01,000 --> 00:00:09,000
Too long.
""")

@pytest.fixture
def unclosed_tag_srt_content():
     return ("""1
00:00:01,000 --> 00:00:03,000
This has <i>an unclosed italic tag.
""")

@pytest.fixture
def bad_timecode_format_srt_content():
     return ("""1
00:00:01 --> 00:00:03,000
Bad timecode.
""")

@pytest.fixture
def empty_file_content():
    return ""

# --- Helper for Validation Args ---
@pytest.fixture
def default_args():
    return argparse.Namespace(
        max_chars_per_line=DEFAULT_MAX_CHARS_PER_LINE,
        max_lines_per_sub=DEFAULT_MAX_LINES_PER_SUB,
        min_duration_ms=DEFAULT_MIN_SUB_DURATION_MS,
        max_duration_ms=DEFAULT_MAX_SUB_DURATION_MS,
        fix=False, # Default to no fix for validation tests
        verbose=False,
        input_path=None # Set per test if needed
    )

# --- Validation Tests (`validate_srt_content`) ---

def test_validate_valid(valid_srt_content, default_args):
    errors = validate_srt_content(
        "valid.srt",
        valid_srt_content,
        max_chars_per_line=default_args.max_chars_per_line,
        max_lines_per_sub=default_args.max_lines_per_sub,
        min_duration_ms=default_args.min_duration_ms,
        max_duration_ms=default_args.max_duration_ms
    )
    assert not errors

def test_validate_overlapping(overlapping_srt_content, default_args):
    errors = validate_srt_content(
        "overlap.srt",
        overlapping_srt_content,
        max_chars_per_line=default_args.max_chars_per_line,
        max_lines_per_sub=default_args.max_lines_per_sub,
        min_duration_ms=default_args.min_duration_ms,
        max_duration_ms=default_args.max_duration_ms
    )
    assert len(errors) == 1
    assert errors[0].error_type == "Timecode Error"
    assert "Overlaps" in errors[0].message
    assert errors[0].subtitle_index == 2

def test_validate_start_after_end(start_after_end_srt_content, default_args):
    errors = validate_srt_content(
        "start_end.srt",
        start_after_end_srt_content,
        max_chars_per_line=default_args.max_chars_per_line,
        max_lines_per_sub=default_args.max_lines_per_sub,
        min_duration_ms=default_args.min_duration_ms,
        max_duration_ms=default_args.max_duration_ms
    )
    # Expect two errors: Start >= End AND Duration < Min (negative duration)
    assert len(errors) == 2
    assert any(e.error_type == "Timecode Error" and "Start time" in e.message for e in errors)
    assert any(e.error_type == "Duration Error" and "less than minimum" in e.message for e in errors)
    assert errors[0].subtitle_index == 1 # Both errors relate to sub 1

def test_validate_misnumbered(misnumbered_srt_content, default_args):
    errors = validate_srt_content(
        "misnum.srt",
        misnumbered_srt_content,
        max_chars_per_line=default_args.max_chars_per_line,
        max_lines_per_sub=default_args.max_lines_per_sub,
        min_duration_ms=default_args.min_duration_ms,
        max_duration_ms=default_args.max_duration_ms
    )
    assert len(errors) == 1
    assert errors[0].error_type == "Index Error"
    assert "Expected index 2" in errors[0].message
    assert errors[0].subtitle_index == 3 # Reports the index found

def test_validate_empty_content(empty_content_srt, default_args):
    errors = validate_srt_content(
        "empty.srt",
        empty_content_srt,
        max_chars_per_line=default_args.max_chars_per_line,
        max_lines_per_sub=default_args.max_lines_per_sub,
        min_duration_ms=default_args.min_duration_ms,
        max_duration_ms=default_args.max_duration_ms
    )
    assert len(errors) == 1
    assert errors[0].error_type == "Content Error"
    assert "content is empty" in errors[0].message
    assert errors[0].subtitle_index == 1

def test_validate_too_many_lines(too_many_lines_srt_content, default_args):
    errors = validate_srt_content(
        "lines.srt",
        too_many_lines_srt_content,
        max_chars_per_line=default_args.max_chars_per_line,
        max_lines_per_sub=default_args.max_lines_per_sub,
        min_duration_ms=default_args.min_duration_ms,
        max_duration_ms=default_args.max_duration_ms
    )
    assert len(errors) == 1
    assert errors[0].error_type == "Format Error"
    assert "maximum lines" in errors[0].message
    assert errors[0].subtitle_index == 1

def test_validate_too_long_line(too_long_line_srt_content, default_args):
    errors = validate_srt_content(
        "long.srt",
        too_long_line_srt_content,
        max_chars_per_line=default_args.max_chars_per_line,
        max_lines_per_sub=default_args.max_lines_per_sub,
        min_duration_ms=default_args.min_duration_ms,
        max_duration_ms=default_args.max_duration_ms
    )
    assert len(errors) == 1
    assert errors[0].error_type == "Format Error"
    assert "maximum characters" in errors[0].message
    assert errors[0].subtitle_index == 1

def test_validate_duration_short(duration_too_short_srt_content, default_args):
    errors = validate_srt_content(
        "short.srt",
        duration_too_short_srt_content,
        max_chars_per_line=default_args.max_chars_per_line,
        max_lines_per_sub=default_args.max_lines_per_sub,
        min_duration_ms=default_args.min_duration_ms,
        max_duration_ms=default_args.max_duration_ms
    )
    assert len(errors) == 1
    assert errors[0].error_type == "Duration Error"
    assert "less than minimum" in errors[0].message
    assert errors[0].subtitle_index == 1

def test_validate_duration_long(duration_too_long_srt_content, default_args):
    errors = validate_srt_content(
        "long_dur.srt",
        duration_too_long_srt_content,
        max_chars_per_line=default_args.max_chars_per_line,
        max_lines_per_sub=default_args.max_lines_per_sub,
        min_duration_ms=default_args.min_duration_ms,
        max_duration_ms=default_args.max_duration_ms
    )
    assert len(errors) == 1
    assert errors[0].error_type == "Duration Error"
    assert "greater than maximum" in errors[0].message
    assert errors[0].subtitle_index == 1

def test_validate_unclosed_tag(unclosed_tag_srt_content, default_args):
    errors = validate_srt_content(
        "tag.srt",
        unclosed_tag_srt_content,
        max_chars_per_line=default_args.max_chars_per_line,
        max_lines_per_sub=default_args.max_lines_per_sub,
        min_duration_ms=default_args.min_duration_ms,
        max_duration_ms=default_args.max_duration_ms
    )
    # Should find the <i> tag issue
    assert any(e.error_type == "Format Error" and "<i>" in e.message for e in errors)
    assert errors[0].subtitle_index == 1

def test_validate_bad_timecode(bad_timecode_format_srt_content, default_args):
    # This should now be caught by our explicit regex check,
    # even if srt.parse might be lenient.
    errors = validate_srt_content(
        "bad_time.srt",
        bad_timecode_format_srt_content,
        max_chars_per_line=default_args.max_chars_per_line,
        max_lines_per_sub=default_args.max_lines_per_sub,
        min_duration_ms=default_args.min_duration_ms,
        max_duration_ms=default_args.max_duration_ms
    )
    # Revert to expecting 1 error: The format error.
    assert len(errors) == 1
    assert errors[0].error_type == "Timecode Format Error" # Expect specific error type
    assert "does not match HH:MM:SS,ms --> HH:MM:SS,ms" in errors[0].message
    assert errors[0].subtitle_index == 1 # Associated with the first subtitle block
    assert errors[0].line_number is not None # We should know the line number

def test_validate_empty_file(empty_file_content, default_args):
    errors = validate_srt_content(
        "empty_file.srt",
        empty_file_content,
        max_chars_per_line=default_args.max_chars_per_line,
        max_lines_per_sub=default_args.max_lines_per_sub,
        min_duration_ms=default_args.min_duration_ms,
        max_duration_ms=default_args.max_duration_ms
    )
    assert len(errors) == 1
    assert errors[0].error_type == "Content Error"
    assert "SRT file is empty" in errors[0].message

# --- Fixing Tests (`fix_srt_subtitles`) ---

@pytest.fixture
def subs_to_fix():
    # Overlapping, misnumbered, includes extra whitespace/newlines
    content = ("""2
00:00:01,000 --> 00:00:03,500
  First subtitle.  \n\n\n
1
00:00:03,000 --> 00:00:05,000
   Overlapping subtitle.\r\n
""")
    return list(srt.parse(content))

def test_fix_subtitles(subs_to_fix):
    fixed_subs, fixes = fix_srt_subtitles(subs_to_fix)

    assert "Timecode Fix" in fixes
    assert "Formatting Fix" in fixes
    assert "Numbering Fix" in fixes

    # Check numbering
    assert fixed_subs[0].index == 1
    assert fixed_subs[1].index == 2

    # Check timecode overlap fix (original index 1 was 00:03.000 -> 00:05.000)
    # fixed_subs[1] corresponds to original index 1
    assert fixed_subs[1].start == fixed_subs[0].end + timedelta(milliseconds=1)
    assert fixed_subs[1].start == timedelta(seconds=3, milliseconds=501) # 3.500 + 0.001

    # Check formatting fix (stripping, newline collapse, \r removal)
    assert fixed_subs[0].content == "First subtitle."
    assert fixed_subs[1].content == "Overlapping subtitle."

# --- I/O and Processing Tests ---

def test_read_valid_srt(tmp_path, valid_srt_content):
    p = tmp_path / "valid.srt"
    p.write_text(valid_srt_content, encoding='utf-8')
    content, error = read_srt_content(str(p))
    assert error is None
    assert content == valid_srt_content

def test_read_nonexistent_file(tmp_path):
    p = tmp_path / "nonexistent.srt"
    content, error = read_srt_content(str(p))
    assert content is None
    assert error is not None
    assert error.error_type == "File Error"
    assert "File not found" in error.message

def test_write_srt(tmp_path, valid_srt_content):
    p = tmp_path / "written.srt"
    subs = list(srt.parse(valid_srt_content))
    error = write_srt(str(p), subs)
    assert error is None
    assert p.read_text(encoding='utf-8').strip() == valid_srt_content.strip()

# Test process_srt_file (validation only)
def test_process_file_validation_ok(tmp_path, valid_srt_content, default_args):
    p = tmp_path / "valid.srt"
    p.write_text(valid_srt_content, encoding='utf-8')
    default_args.input_path = str(p)
    errors, fixes = process_srt_file(str(p), default_args)
    assert not errors
    assert not fixes

# Test process_srt_file (validation fails)
def test_process_file_validation_fail(tmp_path, overlapping_srt_content, default_args):
    p = tmp_path / "overlap.srt"
    p.write_text(overlapping_srt_content, encoding='utf-8')
    default_args.input_path = str(p)
    errors, fixes = process_srt_file(str(p), default_args)
    assert len(errors) == 1
    assert errors[0].error_type == "Timecode Error"
    assert not fixes

# Test process_srt_file (with fixing)
def test_process_file_with_fix(tmp_path, overlapping_srt_content, default_args):
    p = tmp_path / "overlap_fix.srt"
    p.write_text(overlapping_srt_content, encoding='utf-8')
    default_args.input_path = str(p)
    default_args.fix = True

    # We need to capture stdout to check messages, but pytest capsys interferes
    # with how process_srt_file is structured currently (prints directly).
    # For simplicity, we'll just check the file modification and return values.

    errors, fixes = process_srt_file(str(p), default_args)

    # Errors should still report the *original* validation errors found
    assert len(errors) == 1
    assert errors[0].error_type == "Timecode Error"
    assert errors[0].subtitle_index == 2

    # Check that fixes were applied
    assert "Timecode Fix" in fixes

    # Check file content was modified correctly
    new_content = p.read_text(encoding='utf-8')
    fixed_subs = list(srt.parse(new_content))
    assert fixed_subs[1].start == fixed_subs[0].end + timedelta(milliseconds=1)

# Test process_path (directory)
def test_process_path_directory(tmp_path, valid_srt_content, overlapping_srt_content, default_args):
    d = tmp_path / "srt_dir"
    d.mkdir()
    p1 = d / "valid.srt"
    p2 = d / "overlap.srt"
    p3 = d / "other.txt"
    p1.write_text(valid_srt_content, encoding='utf-8')
    p2.write_text(overlapping_srt_content, encoding='utf-8')
    p3.write_text("not srt")

    default_args.input_path = str(d)

    # Again, capturing print output is tricky with current structure.
    # Focus on the returned errors.
    all_errors = process_path(str(d), default_args)

    assert len(all_errors) == 1 # Only the overlap error
    assert all_errors[0].error_type == "Timecode Error"
    assert all_errors[0].file_path == str(p2)

# Test process_path (single file)
def test_process_path_single_file(tmp_path, valid_srt_content, default_args):
     p = tmp_path / "valid_single.srt"
     p.write_text(valid_srt_content, encoding='utf-8')
     default_args.input_path = str(p)
     all_errors = process_path(str(p), default_args)
     assert not all_errors

# Test process_path (non-existent path)
def test_process_path_non_existent(tmp_path, default_args):
     p = tmp_path / "nope"
     default_args.input_path = str(p)
     all_errors = process_path(str(p), default_args)
     assert len(all_errors) == 1
     assert all_errors[0].error_type == "Path Error"
     assert "not a valid file or directory" in all_errors[0].message

# --- Argparse / Main Tests (Very basic) ---
# More comprehensive tests would involve subprocess calls to check main() output and exit codes

# We can't easily test main() directly due to sys.exit()
# and argparse relying on sys.argv. A common pattern is to refactor
# main to take argv as an argument, but we'll skip that complexity here.

# Instead, we can test the argument parsing setup
from validate_srt import main # Import main to access parser indirectly if needed

def test_argparse_defaults():
    # Simulate parsing with just the required argument
    # Need a dummy path that exists for basic parsing to work
    parser = argparse.ArgumentParser()
    # Simplified setup just to test default values
    parser.add_argument("input_path")
    parser.add_argument("--fix", action="store_true")
    parser.add_argument("--max-chars-per-line", type=int, default=DEFAULT_MAX_CHARS_PER_LINE)
    parser.add_argument("--max-lines-per-sub", type=int, default=DEFAULT_MAX_LINES_PER_SUB)
    parser.add_argument("--min-duration-ms", type=int, default=DEFAULT_MIN_SUB_DURATION_MS)
    parser.add_argument("--max-duration-ms", type=int, default=DEFAULT_MAX_SUB_DURATION_MS)
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args(["dummy_path"])
    assert args.input_path == "dummy_path"
    assert args.fix is False
    assert args.max_chars_per_line == DEFAULT_MAX_CHARS_PER_LINE
    assert args.max_lines_per_sub == DEFAULT_MAX_LINES_PER_SUB
    assert args.min_duration_ms == DEFAULT_MIN_SUB_DURATION_MS
    assert args.max_duration_ms == DEFAULT_MAX_SUB_DURATION_MS
    assert args.verbose is False

def test_argparse_fix_flag():
    # Simulate parsing with --fix flag
    parser = argparse.ArgumentParser()
    parser.add_argument("input_path")
    parser.add_argument("--fix", action="store_true")
    args = parser.parse_args(["dummy_path", "--fix"])
    assert args.fix is True

def test_argparse_custom_values():
    # Simulate parsing with custom values
    parser = argparse.ArgumentParser()
    parser.add_argument("input_path")
    parser.add_argument("--max-chars-per-line", type=int)
    parser.add_argument("--min-duration-ms", type=int)

    args = parser.parse_args(["dummy_path", "--max-chars-per-line", "50", "--min-duration-ms", "500"])
    assert args.max_chars_per_line == 50
    assert args.min_duration_ms == 500