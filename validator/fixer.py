import srt
import re
from datetime import timedelta
from typing import List, Tuple


def fix_srt_subtitles(
    subtitles: List[srt.Subtitle],
) -> Tuple[List[srt.Subtitle], List[str]]:
    """Applies fixes to a list of subtitle objects."""
    fixed_subs = list(subtitles)  # Work on a copy
    fixes_applied: List[str] = []
    needs_reindex = False

    last_end_time = timedelta(0)
    for i, sub in enumerate(fixed_subs):
        original_content = sub.content

        # 1. Fix Overlapping/Negative Duration Timecodes
        # Ensure start is not before the last end time
        if sub.start < last_end_time:
            sub.start = last_end_time + timedelta(milliseconds=1)
            if "Timecode Fix" not in fixes_applied:
                fixes_applied.append("Timecode Fix")

        # Ensure end is after start (minimum 1ms duration)
        if sub.end <= sub.start:
            sub.end = sub.start + timedelta(milliseconds=1)
            if "Timecode Fix" not in fixes_applied:
                fixes_applied.append("Timecode Fix")

        last_end_time = sub.end

        # 2. Fix Formatting
        # Remove carriage returns, collapse excessive newlines, strip leading/trailing whitespace
        new_content = sub.content
        new_content = re.sub(r"\r", "", new_content)  # Remove carriage returns
        new_content = re.sub(
            r"\n{3,}", "\n\n", new_content
        )  # Collapse 3+ newlines to 2
        new_content = (
            new_content.strip()
        )  # Strip leading/trailing whitespace from the whole block

        if new_content != original_content:
            sub.content = new_content
            if "Formatting Fix" not in fixes_applied:
                fixes_applied.append("Formatting Fix")

        # 3. Check if Index needs fix (will be done in one pass later)
        if sub.index != i + 1:
            needs_reindex = True

    # 4. Re-number subtitles sequentially if needed
    if needs_reindex:
        for i, sub in enumerate(fixed_subs):
            sub.index = i + 1
        if "Numbering Fix" not in fixes_applied:
            fixes_applied.append("Numbering Fix")

    return fixed_subs, fixes_applied
