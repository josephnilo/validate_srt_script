import pytest
import srt
import argparse
from datetime import timedelta
from rich.console import Console
from io import StringIO

# Remove old Pipenv environment check logic
# def ensure_pipenv_environment():
# ... (remove function) ...
# if "PIPENV_ACTIVE" not in os.environ:
#    ensure_pipenv_environment()

# Remove old imports if they were left behind
# import pytest
# from validate_srt import validate_and_fix_srt, MalformedTimecodeError

# Assume validate_srt.py is in the same directory or PYTHONPATH is set
from validator.models import ValidationError
from validator.rules import validate_srt_content
from validator.fixer import fix_srt_subtitles
from validator.io import read_srt_content, write_srt
from validate_srt import (
    ValidationSummary,
    build_console,
    build_json_report,
    normalize_input_path,
    process_srt_file,
    process_path,
    print_validation_errors,
    DEFAULT_MAX_CHARS_PER_LINE,
    DEFAULT_MAX_LINES_PER_SUB,
    DEFAULT_MIN_SUB_DURATION_MS,
    DEFAULT_MAX_SUB_DURATION_MS,
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
    return """1
00:00:01,000 --> 00:00:02,500
Short line.

2
00:00:03,000 --> 00:00:05,000
Another short line.
"""


@pytest.fixture
def overlapping_srt_content():
    return """1
00:00:01,000 --> 00:00:03,500
First subtitle.

2
00:00:03,000 --> 00:00:05,000
Overlapping subtitle.
"""


@pytest.fixture
def start_after_end_srt_content():
    return """1
00:00:03,000 --> 00:00:02,000
Start time is after end time.
"""


@pytest.fixture
def misnumbered_srt_content():
    return """1
00:00:01,000 --> 00:00:02,000
First subtitle.

3
00:00:03,000 --> 00:00:04,000
Misnumbered subtitle.
"""


@pytest.fixture
def empty_content_srt():
    return """1
00:00:01,000 --> 00:00:02,000


2
00:00:03,000 --> 00:00:04,000
Second subtitle.
"""


@pytest.fixture
def too_many_lines_srt_content():
    return """1
00:00:01,000 --> 00:00:03,000
Line 1
Line 2
Line 3
"""


@pytest.fixture
def too_long_line_srt_content():
    # Using default 42 chars
    return """1
00:00:01,000 --> 00:00:03,000
This line is definitely going to be way too long for subtitle standards.
"""


@pytest.fixture
def duration_too_short_srt_content():
    # Default min 1000ms
    return """1
00:00:01,000 --> 00:00:01,500
Too short.
"""


@pytest.fixture
def duration_too_long_srt_content():
    # Default max 7000ms
    return """1
00:00:01,000 --> 00:00:09,000
Too long.
"""


@pytest.fixture
def unclosed_tag_srt_content():
    return """1
00:00:01,000 --> 00:00:03,000
This has <i>an unclosed italic tag.
"""


@pytest.fixture
def bad_timecode_format_srt_content():
    return """1
00:00:01 --> 00:00:03,000
Bad timecode.
"""


@pytest.fixture
def empty_file_content():
    return ""


@pytest.fixture
def specific_failing_srt_content():
    # Content provided by user that causes errors but doesn't print details
    return """1
00:00:01,333 --> 00:00:06,958
Vlog Pop is vlogging made-easy with 23
Final Cut Pro vlog-themed titles,

2
00:00:07,083 --> 00:00:11,416
effects and tools tailored for
vlogging on YouTube.

3
00:00:14,125 --> 00:00:15,750
This product was created

4
00:00:15,750 --> 00:00:19,250
exclusively for Final Cut Pro
by Stupid Raisins.

5
00:00:20,125 --> 00:00:23,791
You can find it in the Titles Browser
under Vlog Pop,

6
00:00:24,250 --> 00:00:27,333
with some additional transitions
in the Transition browser.

7
00:00:28,041 --> 00:00:31,791
The title templates are broken up
into some different design styles:

8
00:00:32,583 --> 00:00:36,083
Cozy, Cute

9
00:00:37,958 --> 00:00:40,958
and Family Fun.

10
00:00:41,541 --> 00:00:44,541
I've got some Vlog footage on my timeline.

11
00:00:44,750 --> 00:00:48,875
Let's create a complete, polished video
for YouTube with Vlog Pop.

12
00:00:49,500 --> 00:00:53,875
I'll use elements from the Cozy category,
as it fits my footage nicely.

13
00:00:54,458 --> 00:00:57,458
I'll start by dragging the Opener
before my footage.

14
00:00:58,250 --> 00:01:00,125
It's got a drop zone.

15
00:01:00,125 --> 00:01:03,125
I have an intro video prepped
as a Compound Clip.

16
00:01:03,833 --> 00:01:06,500
I'll load it up and position it
in the circular frame.

17
00:01:07,916 --> 00:01:10,500
I'll add in my text.

18
00:01:10,500 --> 00:01:12,333
I'll adjust the background color

19
00:01:12,333 --> 00:01:15,333
to match the branding of her
YouTube channel.

20
00:01:15,625 --> 00:01:18,625
This looks great!

21
00:01:18,875 --> 00:01:21,875
Let's add the Cozy Title to my next clip.

22
00:01:22,333 --> 00:01:25,333
This has a letterbox effect
that animates on.

23
00:01:25,708 --> 00:01:27,916
I'll adjust it slightly.

24
00:01:27,916 --> 00:01:30,291
I'll add in my text.

25
00:01:30,291 --> 00:01:33,791
There are extra effects I like that add
some visual interest:
a Text Wriggle effect and a type-on
Cursor effect for the second line.

26
00:01:34,291 --> 00:01:38,416
a Text Wriggle effect and a type-on
Cursor effect for the second line.

27
00:01:38,416 --> 00:01:41,416
For the second line.

28
00:01:43,375 --> 00:01:45,291
Let's add the Timebreak title

29
00:01:45,291 --> 00:01:48,583
to transition from the studio footage
to the location footage.

30
00:01:49,458 --> 00:01:53,625
I can customize all the colors
and visual aspects of this animation.

31
00:01:54,958 --> 00:01:56,666
I'll add the Call to Action

32
00:01:56,666 --> 00:02:00,041
Subscribe 2 template over
my location clips.

33
00:02:01,000 --> 00:02:04,000
I can adjust the position, scale,

34
00:02:04,125 --> 00:02:07,125
and rotation with the on-screen controls.

35
00:02:08,083 --> 00:02:11,750
I'll add in a profile pic
to the drop zone and position it.

36
00:02:13,000 --> 00:02:13,750
I'll adjust our

37
00:02:13,750 --> 00:02:16,750
text and colors to match our branding.

38
00:02:17,541 --> 00:02:21,250
Let's use the included transitions
between the location clips.

39
00:02:22,083 --> 00:02:25,083
These look great in their default state.

40
00:02:26,083 --> 00:02:27,333
OK, let's finish

41
00:02:27,333 --> 00:02:30,333
with the end screen
attached to our final clip.

42
00:02:30,791 --> 00:02:34,708
I'll load up another video clip
in Drop Zone 1 as a suggested

43
00:02:34,708 --> 00:02:36,500
next watch.

44
00:02:36,500 --> 00:02:39,500
I'll add our profile pic
in Drop Zone 2.

45
00:02:40,083 --> 00:02:44,375
I'll load up the channel Logo in the logo
drop zone and position it.

46
00:02:45,125 --> 00:02:48,083
Finally, I'll customize all the text.

47
00:02:48,083 --> 00:02:52,541
Change the color of the banner and move it
farther to the top of the screen.

48
00:02:53,583 --> 00:02:55,166
And I'm done.

49
00:02:55,166 --> 00:02:59,041
I just added professional graphics
to a Vlog video in minutes,

50
00:02:59,125 --> 00:03:02,500
when it would have taken me hours
to design this all by hand.

51
00:03:03,208 --> 00:03:08,083
Impress your audience or your clients
with Vlog Pop for Final Cut Pro,

52
00:03:15,625 --> 00:03:18,500
Download a free trial today
right from the FxFactory

53
00:03:18,500 --> 00:03:21,500
application.

54
00:03:22,666 --> 00:03:25,250
Create with a wide range of great video

55
00:03:25,250 --> 00:03:28,583
effects, at FxFactory.com
"""


# --- Helper for Validation Args ---
@pytest.fixture
def default_args():
    return argparse.Namespace(
        max_chars_per_line=DEFAULT_MAX_CHARS_PER_LINE,
        max_lines_per_sub=DEFAULT_MAX_LINES_PER_SUB,
        min_duration_ms=DEFAULT_MIN_SUB_DURATION_MS,
        max_duration_ms=DEFAULT_MAX_SUB_DURATION_MS,
        fix=False,  # Default to no fix for validation tests
        verbose=False,
        input_path=None,  # Set per test if needed
    )


# --- Validation Tests (`validate_srt_content`) ---


def test_validate_valid(valid_srt_content, default_args):
    errors = validate_srt_content(
        "valid.srt",
        valid_srt_content,
        max_chars_per_line=default_args.max_chars_per_line,
        max_lines_per_sub=default_args.max_lines_per_sub,
        min_duration_ms=default_args.min_duration_ms,
        max_duration_ms=default_args.max_duration_ms,
    )
    assert not errors


def test_validate_overlapping(overlapping_srt_content, default_args):
    errors = validate_srt_content(
        "overlap.srt",
        overlapping_srt_content,
        max_chars_per_line=default_args.max_chars_per_line,
        max_lines_per_sub=default_args.max_lines_per_sub,
        min_duration_ms=default_args.min_duration_ms,
        max_duration_ms=default_args.max_duration_ms,
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
        max_duration_ms=default_args.max_duration_ms,
    )
    # Expect two errors: Start >= End AND Duration < Min (negative duration)
    assert len(errors) == 2
    assert any(
        e.error_type == "Timecode Error" and "Start time" in e.message for e in errors
    )
    assert any(
        e.error_type == "Duration Error" and "less than minimum" in e.message
        for e in errors
    )
    assert errors[0].subtitle_index == 1  # Both errors relate to sub 1


def test_validate_misnumbered(misnumbered_srt_content, default_args):
    errors = validate_srt_content(
        "misnum.srt",
        misnumbered_srt_content,
        max_chars_per_line=default_args.max_chars_per_line,
        max_lines_per_sub=default_args.max_lines_per_sub,
        min_duration_ms=default_args.min_duration_ms,
        max_duration_ms=default_args.max_duration_ms,
    )
    assert len(errors) == 1
    assert errors[0].error_type == "Index Error"


def test_validate_empty_content(empty_content_srt, default_args):
    errors = validate_srt_content(
        "empty.srt",
        empty_content_srt,
        max_chars_per_line=default_args.max_chars_per_line,
        max_lines_per_sub=default_args.max_lines_per_sub,
        min_duration_ms=default_args.min_duration_ms,
        max_duration_ms=default_args.max_duration_ms,
    )
    assert len(errors) == 1
    assert errors[0].error_type == "Content Error"


def test_validate_too_many_lines(too_many_lines_srt_content, default_args):
    errors = validate_srt_content(
        "lines.srt",
        too_many_lines_srt_content,
        max_chars_per_line=default_args.max_chars_per_line,
        max_lines_per_sub=default_args.max_lines_per_sub,
        min_duration_ms=default_args.min_duration_ms,
        max_duration_ms=default_args.max_duration_ms,
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
        max_duration_ms=default_args.max_duration_ms,
    )
    assert len(errors) == 1
    assert errors[0].error_type == "Format Error"
    assert "maximum characters" in errors[0].message
    assert errors[0].subtitle_index == 1
    assert errors[0].severity == "warning"
    assert errors[0].line_number == 3


def test_validate_duration_short(duration_too_short_srt_content, default_args):
    errors = validate_srt_content(
        "short.srt",
        duration_too_short_srt_content,
        max_chars_per_line=default_args.max_chars_per_line,
        max_lines_per_sub=default_args.max_lines_per_sub,
        min_duration_ms=default_args.min_duration_ms,
        max_duration_ms=default_args.max_duration_ms,
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
        max_duration_ms=default_args.max_duration_ms,
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
        max_duration_ms=default_args.max_duration_ms,
    )
    # Should find the <i> tag issue
    assert any(e.error_type == "Format Error" and "<i>" in e.message for e in errors)
    assert errors[0].subtitle_index == 1


def test_validate_bad_timecode(bad_timecode_format_srt_content, default_args):
    # This should now be caught by our explicit regex check,
    # even if srt.parse might be lenient.
    errors = validate_srt_content(
        "test.srt",
        bad_timecode_format_srt_content,
        default_args.max_chars_per_line,
        default_args.max_lines_per_sub,
        default_args.min_duration_ms,
        default_args.max_duration_ms,
    )
    assert len(errors) == 1
    assert errors[0].error_type == "Timecode Format Error"


def test_validate_empty_file(empty_file_content, default_args):
    errors = validate_srt_content(
        "empty_file.srt",
        empty_file_content,
        max_chars_per_line=default_args.max_chars_per_line,
        max_lines_per_sub=default_args.max_lines_per_sub,
        min_duration_ms=default_args.min_duration_ms,
        max_duration_ms=default_args.max_duration_ms,
    )
    assert len(errors) == 1
    assert errors[0].error_type == "Content Error"
    assert "SRT file is empty" in errors[0].message


# --- Fixing Tests (`fix_srt_subtitles`) ---


@pytest.fixture
def subs_to_fix():
    # Overlapping, misnumbered, includes extra whitespace/newlines
    content = """2
00:00:01,000 --> 00:00:03,500
  First subtitle.  \n\n\n
1
00:00:03,000 --> 00:00:05,000
   Overlapping subtitle.\r\n
"""
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
    assert fixed_subs[1].start == timedelta(
        seconds=3, milliseconds=501
    )  # 3.500 + 0.001

    # Check formatting fix (stripping, newline collapse, \r removal)
    assert fixed_subs[0].content == "First subtitle."
    assert fixed_subs[1].content == "Overlapping subtitle."


# --- I/O and Processing Tests ---


def test_read_valid_srt(tmp_path, valid_srt_content):
    p = tmp_path / "valid.srt"
    p.write_text(valid_srt_content, encoding="utf-8")
    content, error = read_srt_content(str(p))
    assert error is None
    assert content == valid_srt_content


def test_write_srt(tmp_path, valid_srt_content):
    p = tmp_path / "written.srt"
    subs = list(srt.parse(valid_srt_content))
    error = write_srt(str(p), subs)
    assert error is None
    assert p.read_text(encoding="utf-8").strip() == valid_srt_content.strip()


# Test process_srt_file (validation only)
def test_process_file_validation_ok(tmp_path, valid_srt_content, default_args):
    p = tmp_path / "valid.srt"
    p.write_text(valid_srt_content, encoding="utf-8")
    default_args.input_path = str(p)
    errors, fixes = process_srt_file(str(p), default_args)
    assert not errors
    assert not fixes


# Test process_srt_file (validation fails)
def test_process_file_validation_fail(tmp_path, overlapping_srt_content, default_args):
    p = tmp_path / "overlap.srt"
    p.write_text(overlapping_srt_content, encoding="utf-8")
    default_args.input_path = str(p)
    errors, fixes = process_srt_file(str(p), default_args)
    assert len(errors) == 1
    assert errors[0].error_type == "Timecode Error"
    assert not fixes


# Test process_srt_file (with fixing)
def test_process_file_with_fix(tmp_path, overlapping_srt_content, default_args):
    p = tmp_path / "overlap_fix.srt"
    p.write_text(overlapping_srt_content, encoding="utf-8")
    default_args.input_path = str(p)
    default_args.fix = True

    # We need to capture stdout to check messages, but pytest capsys interferes
    # with how process_srt_file is structured currently (prints directly).
    # For simplicity, we'll just check the file modification and return values.

    errors, fixes = process_srt_file(str(p), default_args)

    # After fixing, the file should re-validate cleanly.
    assert not errors

    # Check that fixes were applied
    assert "Timecode Fix" in fixes

    # Check file content was modified correctly
    new_content = p.read_text(encoding="utf-8")
    fixed_subs = list(srt.parse(new_content))
    assert fixed_subs[1].start == fixed_subs[0].end + timedelta(milliseconds=1)


# Test process_path (directory)
def test_process_path_directory(
    tmp_path, valid_srt_content, overlapping_srt_content, default_args
):
    d = tmp_path / "srt_dir"
    d.mkdir()
    p1 = d / "valid.srt"
    p2 = d / "overlap.srt"
    p3 = d / "other.txt"
    p1.write_text(valid_srt_content, encoding="utf-8")
    p2.write_text(overlapping_srt_content, encoding="utf-8")
    p3.write_text("not srt")

    default_args.input_path = str(d)

    # Again, capturing print output is tricky with current structure.
    # Focus on the returned errors.
    all_errors = process_path(str(d), default_args)

    assert len(all_errors) == 1  # Only the overlap error
    assert all_errors[0].error_type == "Timecode Error"
    assert all_errors[0].file_path == str(p2)


# Test process_path (single file)
def test_process_path_single_file(tmp_path, valid_srt_content, default_args):
    p = tmp_path / "valid_single.srt"
    p.write_text(valid_srt_content, encoding="utf-8")
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


def test_normalize_input_path_unwraps_quotes(tmp_path):
    p = tmp_path / "quoted.srt"
    p.write_text(
        "1\n00:00:01,000 --> 00:00:02,000\nHello\n",
        encoding="utf-8",
    )
    quoted = f"'{p}'"
    assert normalize_input_path(quoted) == str(p)


def test_process_path_accepts_quoted_input(tmp_path, valid_srt_content, default_args):
    p = tmp_path / "valid_quoted.srt"
    p.write_text(valid_srt_content, encoding="utf-8")
    quoted = f"'{p}'"
    default_args.input_path = quoted
    all_errors = process_path(quoted, default_args)
    assert not all_errors


def test_process_path_directory_output(
    tmp_path, valid_srt_content, overlapping_srt_content, default_args, capsys
):
    """Test that process_path prints error details correctly to stdout."""
    d = tmp_path / "srt_dir_output"
    d.mkdir()
    p_overlap = d / "overlap.srt"
    p_overlap.write_text(overlapping_srt_content, encoding="utf-8")

    default_args.input_path = str(d)
    default_args.fix = False  # Ensure fix is off for error reporting
    default_args.verbose = True  # Enable verbose for content check

    # Run the processing function that prints
    process_path(str(d), default_args)

    # Capture the printed output
    captured = capsys.readouterr()
    stdout = captured.out

    # Check for key parts of the expected output, ignoring rich markup and exact paths
    assert "Processing directory:" in stdout
    assert "Processing:" in stdout  # Check the file processing line marker
    assert "overlap.srt" in stdout  # Check if the filename appears
    assert "Errors found in" in stdout
    assert "[Sub:2 (L5)]" in stdout  # Check subtitle/line info marker
    assert "Timecode Error" in stdout  # Check error type
    assert "Overlaps with previous subtitle" in stdout  # Check error message fragment
    assert "Content:" not in stdout  # Verbose content still shouldn't be there
    assert "--- End Errors ---" in stdout
    assert "--- Validation Summary ---" in stdout
    assert "Files Processed: 1" in stdout
    assert "Files with Errors: 1" in stdout


def test_process_path_specific_file_output(
    tmp_path, specific_failing_srt_content, default_args, capsys
):
    """Test stdout output for the specific file content that wasn't showing errors."""
    p = tmp_path / "specific_fail.srt"
    p.write_text(specific_failing_srt_content, encoding="utf-8")

    default_args.input_path = str(p)
    default_args.fix = False
    default_args.verbose = True  # Keep verbose on to check content if applicable

    process_path(str(p), default_args)
    captured = capsys.readouterr()
    stdout = captured.out

    # Assert that the error details ARE printed
    # We check for a substring now, as rich may add formatting
    assert "Errors found in" in stdout
    assert "Exceeds maximum lines" in stdout


def test_process_path_escapes_rich_markup_in_file_path(
    tmp_path, overlapping_srt_content, default_args, capsys
):
    p = tmp_path / "weird[red]name.srt"
    p.write_text(overlapping_srt_content, encoding="utf-8")

    default_args.input_path = str(p)
    default_args.fix = False
    default_args.verbose = False

    process_path(str(p), default_args)
    stdout = capsys.readouterr().out

    assert "weird[red]name.srt" in stdout


def test_process_path_escapes_rich_markup_in_verbose_content(
    tmp_path, default_args, capsys
):
    srt_content = """1
00:00:01,000 --> 00:00:03,000
Line 1 [red]X[/red]
Line 2
Line 3
"""
    p = tmp_path / "content_markup.srt"
    p.write_text(srt_content, encoding="utf-8")

    default_args.input_path = str(p)
    default_args.fix = False
    default_args.verbose = True

    process_path(str(p), default_args)
    stdout = capsys.readouterr().out

    assert "[red]X[/red]" in stdout


# --- Argparse / Main Tests (Very basic) ---
# More comprehensive tests would involve subprocess calls to check main() output and exit codes

# We can't easily test main() directly due to sys.exit()
# and argparse relying on sys.argv. A common pattern is to refactor
# main to take argv as an argument, but we'll skip that complexity here.

# Instead, we can test the argument parsing setup


def test_argparse_defaults():
    # Simulate parsing with just the required argument
    # Need a dummy path that exists for basic parsing to work
    parser = argparse.ArgumentParser()
    # Simplified setup just to test default values
    parser.add_argument("input_path")
    parser.add_argument("--fix", action="store_true")
    parser.add_argument(
        "--max-chars-per-line", type=int, default=DEFAULT_MAX_CHARS_PER_LINE
    )
    parser.add_argument(
        "--max-lines-per-sub", type=int, default=DEFAULT_MAX_LINES_PER_SUB
    )
    parser.add_argument(
        "--min-duration-ms", type=int, default=DEFAULT_MIN_SUB_DURATION_MS
    )
    parser.add_argument(
        "--max-duration-ms", type=int, default=DEFAULT_MAX_SUB_DURATION_MS
    )
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

    args = parser.parse_args(
        ["dummy_path", "--max-chars-per-line", "50", "--min-duration-ms", "500"]
    )
    assert args.max_chars_per_line == 50
    assert args.min_duration_ms == 500


def test_print_errors_critical():
    """Test if critical errors are printed in red."""
    errors = [
        ValidationError("test.srt", None, 1, "Parsing Error", "Failed to parse.", "")
    ]
    # Force color output for testing
    string_io = StringIO()
    console = Console(file=string_io, force_terminal=True, color_system="truecolor")

    print_validation_errors(errors, "test.srt", verbose=False, console=console)

    output = string_io.getvalue()
    assert "\x1b[1;31m" in output  # Check for red color ANSI escape code


def test_print_errors_non_critical():
    """Test if non-critical errors are printed in yellow."""
    errors = [
        ValidationError("test.srt", 1, 10, "Index Error", "Wrong index.", "10<-->11")
    ]
    string_io = StringIO()
    console = Console(file=string_io, force_terminal=True, color_system="truecolor")

    print_validation_errors(errors, "test.srt", verbose=False, console=console)

    output = string_io.getvalue()
    assert "\x1b[33m" in output  # Check for yellow color ANSI escape code
    assert "\x1b[1;31m" not in output  # Ensure red is not present


def test_print_errors_no_color():
    """Test if no-color output avoids ANSI escape codes."""
    errors = [
        ValidationError("test.srt", 1, 10, "Index Error", "Wrong index.", "10<-->11")
    ]
    string_io = StringIO()
    console = build_console(no_color=True, file=string_io)

    print_validation_errors(errors, "test.srt", verbose=False, console=console)

    output = string_io.getvalue()
    assert "\x1b[" not in output


def test_build_json_report_counts():
    summary = ValidationSummary(
        files_processed=2, files_with_errors=1, files_with_warnings=1, files_fixed=0
    )
    issues = [
        ValidationError("a.srt", 1, 1, "Parsing Error", "Bad parse.", "x"),
        ValidationError(
            "b.srt",
            2,
            2,
            "Format Error",
            "Too long.",
            "y",
            severity="warning",
        ),
    ]
    report = build_json_report(
        input_path=".",
        issues=issues,
        summary=summary,
        warnings_as_errors=False,
        fail_on_warnings=False,
        fix=False,
        verbose=False,
        exit_code=1,
    )

    assert report["files_processed"] == 2
    assert report["error_count"] == 1
    assert report["warning_count"] == 1
    assert report["issues"][0]["content"] is None


# -- I/O Function Tests --
@pytest.fixture
def valid_srt_file(tmp_path, valid_srt_content):
    p = tmp_path / "valid.srt"
    p.write_text(valid_srt_content, encoding="utf-8")
    return p


def test_read_valid_srt_file(valid_srt_file, valid_srt_content):
    content, error = read_srt_content(str(valid_srt_file))
    assert error is None
    assert content == valid_srt_content


def test_write_srt_file(tmp_path, valid_srt_content):
    p = tmp_path / "written.srt"
    subs = list(srt.parse(valid_srt_content))
    error = write_srt(str(p), subs)
    assert error is None
    assert p.read_text(encoding="utf-8").strip() == valid_srt_content.strip()


def test_write_srt_preserves_subtitle_indices(tmp_path):
    p = tmp_path / "nonsequential.srt"
    subs = [
        srt.Subtitle(
            index=10,
            start=timedelta(seconds=1),
            end=timedelta(seconds=2),
            content="A",
        ),
        srt.Subtitle(
            index=20,
            start=timedelta(seconds=3),
            end=timedelta(seconds=4),
            content="B",
        ),
    ]
    error = write_srt(str(p), subs)
    assert error is None

    parsed = list(srt.parse(p.read_text(encoding="utf-8")))
    assert [s.index for s in parsed] == [10, 20]
