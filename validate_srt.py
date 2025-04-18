import os
import sys
import srt
import re
import argparse
from datetime import timedelta
from typing import List, Tuple, Optional, NamedTuple
import rich
from rich import print as rprint

# Validation Parameters (Defaults)
DEFAULT_MAX_CHARS_PER_LINE = 42
DEFAULT_MAX_LINES_PER_SUB = 2
DEFAULT_MIN_SUB_DURATION_MS = 1000  # 1 second
DEFAULT_MAX_SUB_DURATION_MS = 7000  # 7 seconds

class ValidationError(NamedTuple):
    file_path: str
    subtitle_index: Optional[int]
    line_number: Optional[int] # Line number in the original file
    error_type: str
    message: str
    content: Optional[str] = None # problematic content/line

# -- File I/O --

def read_srt_content(file_path: str) -> Tuple[Optional[str], Optional[ValidationError]]:
    """Reads SRT file content, handling potential file errors."""
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as file: # Use utf-8-sig to handle BOM
            return file.read(), None
    except FileNotFoundError:
        return None, ValidationError(file_path, None, None, "File Error", f"File not found: {file_path}")
    except Exception as e:
        return None, ValidationError(file_path, None, None, "File Error", f"Error reading file {file_path}: {e}")

def write_srt(file_path: str, subtitles: List[srt.Subtitle]) -> Optional[ValidationError]:
    """Writes SRT subtitles to a file."""
    try:
        content_to_write = srt.compose(subtitles, reindex=False) # Keep original index during compose
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content_to_write)
        return None
    except Exception as e:
        return ValidationError(file_path, None, None, "File Error", f"Error writing file {file_path}: {e}")

# -- Validation Logic --

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
    timecode_pattern = re.compile(r'^\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3}$')

    # --- Pre-parsing Checks ---
    block_start_line = 1
    expected_index_pre_parse = 1
    found_subs = False
    in_subtitle_block = False
    current_index = None
    current_timecode_line = None
    current_timecode_lineno = None

    for i, line in enumerate(original_lines):
        line_num = i + 1
        stripped_line = line.strip()

        if re.match(r'^\d+$', stripped_line) and not in_subtitle_block:
            # Potential start of a block - Index line
            in_subtitle_block = True
            block_start_line = line_num
            current_index = int(stripped_line)
            current_timecode_line = None
            current_timecode_lineno = None
            found_subs = True # Mark that we've found at least one potential sub
        elif "-->" in stripped_line and in_subtitle_block and current_timecode_line is None:
            # Timecode line
            current_timecode_line = stripped_line
            current_timecode_lineno = line_num
            if not timecode_pattern.match(current_timecode_line):
                errors.append(ValidationError(
                    file_path=file_path,
                    subtitle_index=current_index,
                    line_number=line_num,
                    error_type="Timecode Format Error",
                    message=f"Timecode line does not match HH:MM:SS,ms --> HH:MM:SS,ms format.",
                    content=line # Original line content
                ))
        elif not stripped_line and in_subtitle_block:
            # Blank line separating blocks - reset state
            in_subtitle_block = False
            current_index = None
            current_timecode_line = None
            current_timecode_lineno = None
        elif in_subtitle_block and current_timecode_line is not None:
            # Content line - currently no pre-parse checks needed here
            pass

    # Check if the file ended mid-block (e.g., index but no timecode, or timecode but no blank line)
    # if in_subtitle_block and current_timecode_line is None:
    #     errors.append(ValidationError(file_path, current_index, block_start_line, "Structure Error", "Subtitle block ended prematurely (missing timecode or content?)."))
    # Basic check if file is empty or contains only whitespace
    if not content.strip():
        errors.append(ValidationError(file_path, None, 1, "Content Error", "SRT file is empty or contains only whitespace."))
        return errors # No point parsing if empty
    # Check if we started parsing but found no valid subtitle blocks
    elif content.strip() and not found_subs:
         errors.append(ValidationError(file_path, None, 1, "Parsing Error", "Content seems non-empty but no valid subtitle blocks found.", content[:100]))
         return errors # Likely malformed, stop here

    # If fatal format errors were found, return early before full parse
    if any(e.error_type == "Timecode Format Error" for e in errors):
         return errors

    # --- SRT Library Parsing and Validation ---
    try:
        # Use a generator to potentially catch errors earlier
        parsed_subs = list(srt.parse(content))
        if not parsed_subs and content.strip():
             errors.append(ValidationError(file_path, None, 1, "Parsing Error", "Content seems non-empty but no subtitles parsed.", content))
        elif not parsed_subs and not content.strip():
             # This case is now handled by pre-parsing checks
             # errors.append(ValidationError(file_path, None, 1, "Content Error", "SRT file is empty.", content))
             pass

        subtitles.extend(parsed_subs) # If parse succeeds, store them

    except Exception as e: # Catch broad errors from srt.parse
        # Try to find the problematic line number
        line_num_guess = 1
        if hasattr(e, 'lineno'): # srt library might add lineno in future
            line_num_guess = e.lineno
        elif isinstance(e, ValueError) and "time string" in str(e):
             # Find the line containing the bad timecode if possible
             for i, line in enumerate(original_lines):
                 if "-->" in line and not re.match(r'^\d{1,}\s*$', line.strip()) and not re.match(r'^\s*$', line.strip()): # Avoid index lines and empty lines
                     try:
                         srt.srt_timestamp_to_timedelta(line.split("-->")[0].strip())
                         srt.srt_timestamp_to_timedelta(line.split("-->")[1].strip())
                     except:
                         line_num_guess = i + 1
                         break

        # Only append parsing error if no format error was already found for this line
        if not any(e.line_number == line_num_guess and e.error_type == "Timecode Format Error" for e in errors):
             errors.append(ValidationError(file_path, None, line_num_guess, "Parsing Error", f"SRT parsing failed: {e}", content[:500])) # Limit context
        return errors # Stop validation if basic parsing fails

    last_end_time = timedelta(0)
    expected_index = 1

    subtitle_line_map = {} # Map subtitle index to original start line number
    current_sub_index_str = ""
    current_sub_start_line = 0
    for i, line in enumerate(original_lines):
        line_num = i + 1
        stripped_line = line.strip()
        if re.match(r'^\d+\s*$', stripped_line):
            if current_sub_index_str: # Store previous mapping
                 try:
                     subtitle_line_map[int(current_sub_index_str)] = current_sub_start_line
                 except ValueError:
                     pass # Ignore if index wasn't a valid number
            current_sub_index_str = stripped_line
            current_sub_start_line = line_num
        elif "-->" in line and current_sub_index_str:
             # Complete the mapping when timecode line is found
             try:
                 subtitle_line_map[int(current_sub_index_str)] = current_sub_start_line
             except ValueError:
                 pass
             current_sub_index_str = "" # Reset for next subtitle
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
            errors.append(ValidationError(file_path, sub.index, start_line, "Index Error", f"Expected index {expected_index}, found {sub.index}."))
            # Don't update expected_index, report all mismatches based on sequence

        # 2. Timecode Order Check (Start < End)
        if sub.start >= sub.end:
            errors.append(ValidationError(file_path, sub.index, start_line, "Timecode Error", f"Start time ({sub.start}) is not before end time ({sub.end})."))

        # 3. Overlap Check
        if sub.start < last_end_time:
            errors.append(ValidationError(file_path, sub.index, start_line, "Timecode Error", f"Overlaps with previous subtitle (Ends: {last_end_time}, Starts: {sub.start})."))

        # 4. Duration Check
        duration = sub.end - sub.start
        duration_ms = duration.total_seconds() * 1000
        if duration_ms < min_duration_ms:
            errors.append(ValidationError(file_path, sub.index, start_line, "Duration Error", f"Subtitle duration ({duration_ms:.0f}ms) is less than minimum ({min_duration_ms}ms)."))
        if duration_ms > max_duration_ms:
             errors.append(ValidationError(file_path, sub.index, start_line, "Duration Error", f"Subtitle duration ({duration_ms:.0f}ms) is greater than maximum ({max_duration_ms}ms)."))

        # 5. Content Checks
        lines = sub.content.strip().split('\n')
        if not sub.content.strip():
            errors.append(ValidationError(file_path, sub.index, start_line, "Content Error", "Subtitle content is empty."))
        else:
             # 5a. Max Lines Check
            if len(lines) > max_lines_per_sub:
                errors.append(ValidationError(file_path, sub.index, start_line, "Format Error", f"Exceeds maximum lines per subtitle ({len(lines)} > {max_lines_per_sub}).", sub.content))

            # 5b. Max Chars Per Line Check
            for i, line in enumerate(lines):
                 # Basic tag stripping for length check (not perfect for nested/complex tags)
                 line_no_tags = re.sub(r'<[^>]+>', '', line)
                 if len(line_no_tags) > max_chars_per_line:
                     errors.append(ValidationError(file_path, sub.index, start_line + i + 1 if start_line else None, "Format Error", f"Line exceeds maximum characters ({len(line_no_tags)} > {max_chars_per_line}).", line))

        # 6. Basic Unclosed Tag Check (Common Tags) - Optional more complex parsing needed for accuracy
        common_tags = ['i', 'b', 'u', 'font']
        for tag in common_tags:
            open_tag = f'<{tag}>'
            open_tag_styled = f'<{tag} ' # e.g. <font color..>
            close_tag = f'</{tag}>'
            # Count occurrences ignoring case for simplicity
            open_count = sub.content.lower().count(open_tag) + sub.content.lower().count(open_tag_styled)
            close_count = sub.content.lower().count(close_tag)
            if open_count != close_count:
                 errors.append(ValidationError(file_path, sub.index, start_line, "Format Error", f"Potential unclosed or mismatched '<{tag}>' tag found.", sub.content))


        last_end_time = sub.end
        expected_index += 1 # Increment expected index for the next iteration

    return errors

# -- Fixing Logic --

def fix_srt_subtitles(subtitles: List[srt.Subtitle]) -> Tuple[List[srt.Subtitle], List[str]]:
    """Applies fixes to a list of subtitle objects."""
    fixed_subs = list(subtitles) # Work on a copy
    fixes_applied: List[str] = []
    needs_reindex = False

    last_end_time = timedelta(0)
    for i, sub in enumerate(fixed_subs):
        original_start = sub.start
        original_end = sub.end
        original_content = sub.content

        # 1. Fix Overlapping/Negative Duration Timecodes
        # Ensure start is not before the last end time
        if sub.start < last_end_time:
            sub.start = last_end_time + timedelta(milliseconds=1)
            if "Timecode Fix" not in fixes_applied: fixes_applied.append("Timecode Fix")

        # Ensure end is after start (minimum 1ms duration)
        if sub.end <= sub.start:
             sub.end = sub.start + timedelta(milliseconds=1)
             if "Timecode Fix" not in fixes_applied: fixes_applied.append("Timecode Fix")

        last_end_time = sub.end

        # 2. Fix Formatting
        # Remove carriage returns, collapse excessive newlines, strip leading/trailing whitespace
        new_content = sub.content
        new_content = re.sub(r'\r', '', new_content) # Remove carriage returns
        new_content = re.sub(r'\n{3,}', '\n\n', new_content) # Collapse 3+ newlines to 2
        new_content = new_content.strip() # Strip leading/trailing whitespace from the whole block

        if new_content != original_content:
             sub.content = new_content
             if "Formatting Fix" not in fixes_applied: fixes_applied.append("Formatting Fix")

        # 3. Check if Index needs fix (will be done in one pass later)
        if sub.index != i + 1:
             needs_reindex = True

    # 4. Re-number subtitles sequentially if needed
    if needs_reindex:
        for i, sub in enumerate(fixed_subs):
            sub.index = i + 1
        if "Numbering Fix" not in fixes_applied: fixes_applied.append("Numbering Fix")


    return fixed_subs, fixes_applied

# -- Processing Logic --

def process_srt_file(file_path: str, args: argparse.Namespace) -> Tuple[List[ValidationError], List[str]]:
    """Validates and optionally fixes a single SRT file."""
    content, read_error = read_srt_content(file_path)
    if read_error:
        return [read_error], [] # Return file read error

    if content is None: # Should not happen if read_error is None, but safety check
         return [ValidationError(file_path, None, None, "Internal Error", "Failed to read content unexpectedly.")], []

    # Temporarily remove try/except around validation for debugging
    # try:
    validation_errors = validate_srt_content(
        file_path,
        content,
        args.max_chars_per_line,
        args.max_lines_per_sub,
        args.min_duration_ms,
        args.max_duration_ms
    )
    # except Exception as e:
    #      # Catch unexpected validation errors
    #      validation_errors = [ValidationError(file_path, None, None, "Internal Validation Error", f"Unexpected error during validation: {e}")]

    fixes_applied: List[str] = []
    write_error: Optional[ValidationError] = None

    if validation_errors and args.fix:
        rprint(f"Attempting to fix [cyan]{file_path}[/cyan]...")
        try:
            # Re-parse needed before fixing if initial validation found errors but didn't stop
            subtitles_to_fix = list(srt.parse(content))
            fixed_subtitles, fixes_applied = fix_srt_subtitles(subtitles_to_fix)
            if fixes_applied:
                 write_error = write_srt(file_path, fixed_subtitles)
                 if write_error:
                     # If write fails, report it but keep original validation errors
                     validation_errors.append(write_error)
                 else:
                      rprint(f"Fixes applied ([green]{', '.join(fixes_applied)}[/green]) to: [cyan]{file_path}[/cyan]")
            else:
                 rprint(f"No automatic fixes applied (issues might remain) for: [cyan]{file_path}[/cyan]")

        except Exception as e:
            # Catch errors during the fixing parse/process itself
             fix_error = ValidationError(file_path, None, None, "Fixing Error", f"Failed to fix file: {e}", content[:500])
             validation_errors.append(fix_error)
             rprint(f"Error during fixing process for [cyan]{file_path}[/cyan]: {e}", file=sys.stderr)

    return validation_errors, fixes_applied # Return original validation errors, even if fix was attempted

def process_path(input_path: str, args: argparse.Namespace) -> List[ValidationError]:
    """Processes a single file or all SRT files in a directory."""
    all_errors: List[ValidationError] = []
    files_processed = 0
    files_with_errors = 0
    files_fixed = 0

    if os.path.isfile(input_path):
        if input_path.lower().endswith('.srt'):
            rprint(f"Processing file: [cyan]{input_path}[/cyan]")
            errors = process_srt_file(input_path, args)[0] # Only get errors list
            fixes = [] # Dummy value

            files_processed = 1
            if errors:
                 files_with_errors +=1
                 all_errors.extend(errors)
                 # Use sys.stdout.write for reliable output
                 sys.stdout.write(f"Errors found in {input_path}:\n")
                 for error in errors:
                     line_info = f"L{error.line_number}" if error.line_number else "N/A"
                     sub_info = f"Sub:{error.subtitle_index}" if error.subtitle_index is not None else "File-level"
                     sys.stdout.write(f"  - [{sub_info} ({line_info})] {error.error_type}: {error.message}\n")
                     if error.content and args.verbose:
                         sys.stdout.write(f"    Content: {error.content[:100]}{'...' if len(error.content)>100 else ''}\n")
                 sys.stdout.write("--- End Errors ---\n")

            else:
                 # Keep rich print for success
                 rprint(f"[green]Validation passed for:[/green] {input_path}")

            # Restore fix checking logic
            if fixes:
                 files_fixed += 1
            print("") # Newline separation between files

        else:
            rprint(f"[yellow]Skipping non-SRT file:[/yellow] {input_path}", file=sys.stderr)
    elif os.path.isdir(input_path):
        rprint(f"Processing directory: [cyan]{input_path}[/cyan]")
        for root, _, files in os.walk(input_path):
            for file in files:
                if file.lower().endswith('.srt'):
                    file_path = os.path.join(root, file)
                    rprint(f"--- Processing: [cyan]{file_path}[/cyan] ---")
                    # Restore original unpacking
                    errors, fixes = process_srt_file(file_path, args)
                    # errors = process_srt_file(file_path, args)[0] # Only get errors list
                    # fixes = [] # Dummy value

                    # --- Remove Immediate Debug Check --- #
                    # if errors:
                    #      print(f"DEBUG: process_srt_file returned errors for {file_path}")
                    # else:
                    #      print(f"DEBUG: process_srt_file returned NO errors for {file_path}")
                    # --- End Immediate Debug Check --- #

                    files_processed += 1
                    if errors:
                         files_with_errors +=1
                         all_errors.extend(errors)
                         # Use sys.stdout.write for reliable output
                         sys.stdout.write(f"Errors found in {file_path}:\n")
                         for error in errors:
                             line_info = f"L{error.line_number}" if error.line_number else "N/A"
                             sub_info = f"Sub:{error.subtitle_index}" if error.subtitle_index is not None else "File-level"
                             sys.stdout.write(f"  - [{sub_info} ({line_info})] {error.error_type}: {error.message}\n")
                             if error.content and args.verbose:
                                 sys.stdout.write(f"    Content: {error.content[:100]}{'...' if len(error.content)>100 else ''}\n")
                         sys.stdout.write("--- End Errors ---\n")

                    else:
                         # Keep rich print for success
                         rprint(f"[green]Validation passed for:[/green] {file_path}")

                    # Restore fix checking logic
                    if fixes:
                         files_fixed += 1
                    print("") # Newline separation between files

    else:
        rprint(f"[bold red]Error:[/bold red] Input path not found: {input_path}", file=sys.stderr)
        # Create a generic error if path doesn't exist
        all_errors.append(ValidationError(input_path, None, None, "Path Error", "Input path is not a valid file or directory."))


    # Final Summary using Rich
    rprint("\n[bold]--- Validation Summary ---[/bold]")
    rprint(f"Files Processed: {files_processed}")
    rprint(f"Files with Errors: {files_with_errors}")
    # Restore fix count reporting
    if args.fix:
        rprint(f"Files Modified by Fixing: {files_fixed}")

    rprint("[bold]--- End Summary ---[/bold]")

    return all_errors


def main():
    parser = argparse.ArgumentParser(description="Validate and optionally fix SRT subtitle files.")
    parser.add_argument("input_path", help="Path to the SRT file or directory containing SRT files.")
    parser.add_argument("--fix", action="store_true", help="Attempt to automatically fix detected issues.")
    parser.add_argument("--max-chars-per-line", type=int, default=DEFAULT_MAX_CHARS_PER_LINE,
                        help=f"Maximum characters allowed per line (default: {DEFAULT_MAX_CHARS_PER_LINE}).")
    parser.add_argument("--max-lines-per-sub", type=int, default=DEFAULT_MAX_LINES_PER_SUB,
                        help=f"Maximum lines allowed per subtitle (default: {DEFAULT_MAX_LINES_PER_SUB}).")
    parser.add_argument("--min-duration-ms", type=int, default=DEFAULT_MIN_SUB_DURATION_MS,
                        help=f"Minimum duration for a subtitle in milliseconds (default: {DEFAULT_MIN_SUB_DURATION_MS}).")
    parser.add_argument("--max-duration-ms", type=int, default=DEFAULT_MAX_SUB_DURATION_MS,
                        help=f"Maximum duration for a subtitle in milliseconds (default: {DEFAULT_MAX_SUB_DURATION_MS}).")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show more detailed error context.")


    if len(sys.argv) == 1:
         # If run with no arguments (e.g. just `python validate_srt.py`), show help.
         parser.print_help(sys.stderr)
         sys.exit(1)

    args = parser.parse_args()

    # Recommend using Pipenv if Pipfile exists but not active
    if os.path.exists("Pipfile") and "PIPENV_ACTIVE" not in os.environ:
         # Use rich for info message
         rprint("[yellow]INFO:[/yellow] Pipfile found but virtual environment not active.", file=sys.stderr)
         rprint("[yellow]INFO:[/yellow] Run using `pipenv run python validate_srt.py ...` for consistency.", file=sys.stderr)
         # Consider exiting here if strict environment enforcement is desired:
         # sys.exit(1)

    all_errors = process_path(args.input_path, args)

    if all_errors and not args.fix:
        rprint("\n[bold red]Validation finished with errors.[/bold red]", file=sys.stderr)
        sys.exit(1)
    elif all_errors and args.fix:
         rprint("\n[yellow]Fixing attempted, but some errors might remain or were introduced.[/yellow]", file=sys.stderr)
         # Decide if remaining errors after fixing should still cause non-zero exit code
         # For now, let's exit 0 if --fix was used, assuming user wanted modifications.
         sys.exit(0)
    else:
        rprint("\n[bold green]Validation finished successfully.[/bold green]")
        sys.exit(0)

if __name__ == "__main__":
    main()