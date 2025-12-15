import srt
import re
from datetime import timedelta
from typing import List
from .models import ValidationError


def validate_srt_content(
    file_path: str,
    content: str,
    max_chars_per_line: int,
    max_lines_per_sub: int,
    min_duration_ms: int,
    max_duration_ms: int,
) -> List[ValidationError]:
    """Validates the content of an SRT file based on various rules."""
    errors: List[ValidationError] = []
    subtitles: List[srt.Subtitle] = []
    original_lines = content.splitlines()
    # Add strict timecode regex
    timecode_pattern = re.compile(
        r"^\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3}$"
    )

    # --- Pre-parsing Checks ---
    found_subs = False
    in_subtitle_block = False
    current_index = None
    current_timecode_line = None

    for i, line in enumerate(original_lines):
        line_num = i + 1
        stripped_line = line.strip()

        if re.match(r"^\d+$", stripped_line) and not in_subtitle_block:
            # Potential start of a block - Index line
            in_subtitle_block = True
            current_index = int(stripped_line)
            current_timecode_line = None
            found_subs = True  # Mark that we've found at least one potential sub
        elif (
            "-->" in stripped_line
            and in_subtitle_block
            and current_timecode_line is None
        ):
            # Timecode line
            current_timecode_line = stripped_line
            if not timecode_pattern.match(current_timecode_line):
                errors.append(
                    ValidationError(
                        file_path=file_path,
                        subtitle_index=current_index,
                        line_number=line_num,
                        error_type="Timecode Format Error",
                        message="Timecode line does not match HH:MM:SS,ms --> HH:MM:SS,ms format.",
                        content=line,  # Original line content
                    )
                )
        elif not stripped_line and in_subtitle_block:
            # Blank line separating blocks - reset state
            in_subtitle_block = False
            current_index = None
            current_timecode_line = None
        elif in_subtitle_block and current_timecode_line is not None:
            # Content line - currently no pre-parse checks needed here
            pass

    # Check if the file ended mid-block (e.g., index but no timecode, or timecode but no blank line)
    # if in_subtitle_block and current_timecode_line is None:
    #     errors.append(ValidationError(file_path, current_index, block_start_line, "Structure Error", "Subtitle block ended prematurely (missing timecode or content?)."))
    # Basic check if file is empty or contains only whitespace
    if not content.strip():
        errors.append(
            ValidationError(
                file_path,
                None,
                1,
                "Content Error",
                "SRT file is empty or contains only whitespace.",
            )
        )
        return errors  # No point parsing if empty
    # Check if we started parsing but found no valid subtitle blocks
    elif content.strip() and not found_subs:
        errors.append(
            ValidationError(
                file_path,
                None,
                1,
                "Parsing Error",
                "Content seems non-empty but no valid subtitle blocks found.",
                content[:100],
            )
        )
        return errors  # Likely malformed, stop here

    # If fatal format errors were found, return early before full parse
    if any(e.error_type == "Timecode Format Error" for e in errors):
        return errors

    # --- SRT Library Parsing and Validation ---
    try:
        # Use a generator to potentially catch errors earlier
        parsed_subs = list(srt.parse(content))
        if not parsed_subs and content.strip():
            errors.append(
                ValidationError(
                    file_path,
                    None,
                    1,
                    "Parsing Error",
                    "Content seems non-empty but no subtitles parsed.",
                    content,
                )
            )
        elif not parsed_subs and not content.strip():
            # This case is now handled by pre-parsing checks
            # errors.append(ValidationError(file_path, None, 1, "Content Error", "SRT file is empty.", content))
            pass

        subtitles.extend(parsed_subs)  # If parse succeeds, store them

    except Exception as e:  # Catch broad errors from srt.parse
        # Try to find the problematic line number
        line_num_guess = getattr(
            e, "lineno", 1
        )  # srt library might add lineno in future

        # Only append parsing error if no format error was already found for this line
        if not any(
            e.line_number == line_num_guess and e.error_type == "Timecode Format Error"
            for e in errors
        ):
            errors.append(
                ValidationError(
                    file_path,
                    None,
                    line_num_guess,
                    "Parsing Error",
                    f"SRT parsing failed: {e}",
                    content[:500],
                )
            )  # Limit context
        return errors  # Stop validation if basic parsing fails

    last_end_time = timedelta(0)
    expected_index = 1

    subtitle_line_map = {}  # Map subtitle index to original start line number
    current_sub_index_str = ""
    current_sub_start_line = 0
    for i, line in enumerate(original_lines):
        line_num = i + 1
        stripped_line = line.strip()
        if re.match(r"^\d+\s*$", stripped_line):
            if current_sub_index_str:  # Store previous mapping
                try:
                    subtitle_line_map[int(current_sub_index_str)] = (
                        current_sub_start_line
                    )
                except ValueError:
                    pass  # Ignore if index wasn't a valid number
            current_sub_index_str = stripped_line
            current_sub_start_line = line_num
        elif "-->" in line and current_sub_index_str:
            # Complete the mapping when timecode line is found
            try:
                subtitle_line_map[int(current_sub_index_str)] = current_sub_start_line
            except ValueError:
                pass
            current_sub_index_str = ""  # Reset for next subtitle
    # Map the last subtitle if file doesn't end with newline
    if current_sub_index_str:
        try:
            subtitle_line_map[int(current_sub_index_str)] = current_sub_start_line
        except ValueError:
            pass

    for sub in subtitles:
        start_line = subtitle_line_map.get(sub.index, None)

        # 1. Indexing Check
        if sub.index != expected_index:
            errors.append(
                ValidationError(
                    file_path,
                    sub.index,
                    start_line,
                    "Index Error",
                    f"Expected index {expected_index}, found {sub.index}.",
                )
            )

        expected_index += 1

        # 2. Timecode Order Check (Start < End)
        if sub.start >= sub.end:
            errors.append(
                ValidationError(
                    file_path,
                    sub.index,
                    start_line,
                    "Timecode Error",
                    f"Start time ({sub.start}) is not before end time ({sub.end}).",
                )
            )

        # 3. Overlap Check
        if sub.start < last_end_time:
            errors.append(
                ValidationError(
                    file_path,
                    sub.index,
                    start_line,
                    "Timecode Error",
                    f"Overlaps with previous subtitle (Ends: {last_end_time}, Starts: {sub.start}).",
                )
            )

        # 4. Duration Check
        duration = sub.end - sub.start
        duration_ms = duration.total_seconds() * 1000
        if duration_ms < min_duration_ms:
            errors.append(
                ValidationError(
                    file_path,
                    sub.index,
                    start_line,
                    "Duration Error",
                    f"Subtitle duration ({duration_ms:.0f}ms) is less than minimum ({min_duration_ms}ms).",
                )
            )
        if duration_ms > max_duration_ms:
            errors.append(
                ValidationError(
                    file_path,
                    sub.index,
                    start_line,
                    "Duration Error",
                    f"Subtitle duration ({duration_ms:.0f}ms) is greater than maximum ({max_duration_ms}ms).",
                )
            )

        # 5. Content Checks
        lines = sub.content.strip().split("\n")
        if not sub.content.strip():
            errors.append(
                ValidationError(
                    file_path,
                    sub.index,
                    start_line,
                    "Content Error",
                    "Subtitle content is empty.",
                )
            )
        else:
            # 5a. Max Lines Check
            if len(lines) > max_lines_per_sub:
                errors.append(
                    ValidationError(
                        file_path,
                        sub.index,
                        start_line,
                        "Format Error",
                        f"Exceeds maximum lines per subtitle ({len(lines)} > {max_lines_per_sub}).",
                        sub.content,
                    )
                )

            # 5b. Max Chars Per Line Check
            for i, line in enumerate(lines):
                # Basic tag stripping for length check (not perfect for nested/complex tags)
                line_no_tags = re.sub(r"<[^>]+>", "", line)
                if len(line_no_tags) > max_chars_per_line:
                    errors.append(
                        ValidationError(
                            file_path,
                            sub.index,
                            start_line + i + 2 if start_line else None,
                            "Format Error",
                            f"Line exceeds maximum characters ({len(line_no_tags)} > {max_chars_per_line}).",
                            line,
                            severity="warning",
                        )
                    )

        # 6. Basic Unclosed Tag Check (Common Tags) - Optional more complex parsing needed for accuracy
        common_tags = ["i", "b", "u", "font"]
        for tag in common_tags:
            open_tag = f"<{tag}>"
            open_tag_styled = f"<{tag} "  # e.g. <font color..>
            close_tag = f"</{tag}>"
            # Count occurrences ignoring case for simplicity
            open_count = sub.content.lower().count(
                open_tag
            ) + sub.content.lower().count(open_tag_styled)
            close_count = sub.content.lower().count(close_tag)
            if open_count != close_count:
                errors.append(
                    ValidationError(
                        file_path,
                        sub.index,
                        start_line,
                        "Format Error",
                        f"Potential unclosed or mismatched '<{tag}>' tag found.",
                        sub.content,
                    )
                )

        last_end_time = sub.end

    return errors
