import os
import sys
import srt
import argparse
from typing import List, Tuple
from rich import print as rprint

from validator.models import ValidationError
from validator.io import read_srt_content, write_srt
from validator.rules import validate_srt_content
from validator.fixer import fix_srt_subtitles

# Validation Parameters (Defaults)
DEFAULT_MAX_CHARS_PER_LINE = 42
DEFAULT_MAX_LINES_PER_SUB = 2
DEFAULT_MIN_SUB_DURATION_MS = 1000  # 1 second
DEFAULT_MAX_SUB_DURATION_MS = 7000  # 7 seconds

CRITICAL_ERROR_TYPES = {
    "File Error",
    "Timecode Format Error",
    "Parsing Error",
    "Content Error",
    "Fixing Error",
    "Internal Error",
    "Path Error",
}


def print_validation_errors(
    errors: List[ValidationError], file_path: str, verbose: bool
):
    """Prints a list of validation errors using rich formatting."""
    rprint(f"[bold]Errors found in [cyan]{file_path}[/cyan]:[/bold]")
    for error in errors:
        is_critical = error.error_type in CRITICAL_ERROR_TYPES
        color = "bold red" if is_critical else "yellow"

        line_info = f"L{error.line_number}" if error.line_number else "N/A"
        sub_info = (
            f"Sub:{error.subtitle_index}"
            if error.subtitle_index is not None
            else "File-level"
        )

        rprint(
            f"  - [{color}][{sub_info} ({line_info})] {error.error_type}: {error.message}[/{color}]"
        )
        if error.content and verbose:
            content_preview = error.content.replace("\n", " ")
            rprint(
                f"    [{color}]Content: {content_preview[:100]}{'...' if len(content_preview)>100 else ''}[/{color}]"
            )
    rprint("[bold]--- End Errors ---[/bold]")


def process_srt_file(
    file_path: str, args: argparse.Namespace
) -> Tuple[List[ValidationError], List[str]]:
    """Validates and optionally fixes a single SRT file."""
    content, read_error = read_srt_content(file_path)
    if read_error:
        return [read_error], []

    if content is None:
        return [
            ValidationError(
                file_path,
                None,
                None,
                "Internal Error",
                "Failed to read content unexpectedly.",
            )
        ], []

    validation_errors = validate_srt_content(
        file_path,
        content,
        args.max_chars_per_line,
        args.max_lines_per_sub,
        args.min_duration_ms,
        args.max_duration_ms,
    )

    fixes_applied: List[str] = []
    if validation_errors and args.fix:
        rprint(f"Attempting to fix [cyan]{file_path}[/cyan]...")
        try:
            subtitles_to_fix = list(srt.parse(content))
            fixed_subtitles, fixes_applied = fix_srt_subtitles(subtitles_to_fix)
            if fixes_applied:
                write_error = write_srt(file_path, fixed_subtitles)
                if write_error:
                    validation_errors.append(write_error)
                else:
                    rprint(
                        f"Fixes applied ([green]{', '.join(fixes_applied)}[/green]) to: [cyan]{file_path}[/cyan]"
                    )
            else:
                rprint(f"No automatic fixes applied for: [cyan]{file_path}[/cyan]")
        except Exception as e:
            fix_error = ValidationError(
                file_path,
                None,
                None,
                "Fixing Error",
                f"Failed to fix file: {e}",
                content[:500],
            )
            validation_errors.append(fix_error)
            rprint(
                f"Error during fixing process for [cyan]{file_path}[/cyan]: {e}",
                file=sys.stderr,
            )

    return validation_errors, fixes_applied


def process_path(input_path: str, args: argparse.Namespace) -> List[ValidationError]:
    """Processes a single file or all SRT files in a directory."""
    all_errors: List[ValidationError] = []
    files_to_process: List[str] = []

    if os.path.isfile(input_path):
        if input_path.lower().endswith(".srt"):
            files_to_process.append(input_path)
        else:
            rprint(
                f"[yellow]Skipping non-SRT file:[/yellow] {input_path}", file=sys.stderr
            )
    elif os.path.isdir(input_path):
        rprint(f"Processing directory: [cyan]{input_path}[/cyan]")
        for root, _, files in os.walk(input_path):
            for file in sorted(files):
                if file.lower().endswith(".srt"):
                    files_to_process.append(os.path.join(root, file))
    else:
        rprint(
            f"[bold red]Error:[/bold red] Input path not found: {input_path}",
            file=sys.stderr,
        )
        return [
            ValidationError(
                input_path,
                None,
                None,
                "Path Error",
                "Input path is not a valid file or directory.",
            )
        ]

    files_processed = 0
    files_with_errors = 0
    files_fixed = 0

    for file_path in files_to_process:
        rprint(f"--- Processing: [cyan]{file_path}[/cyan] ---")
        files_processed += 1

        errors, fixes = process_srt_file(file_path, args)

        if errors:
            files_with_errors += 1
            all_errors.extend(errors)
            print_validation_errors(errors, file_path, args.verbose)
        else:
            rprint(f"[green]Validation passed for:[/green] {file_path}")

        if fixes:
            files_fixed += 1

        print("")

    rprint("\n[bold]--- Validation Summary ---[/bold]")
    rprint(f"Files Processed: {files_processed}")
    rprint(f"Files with Errors: {files_with_errors}")
    if args.fix:
        rprint(f"Files Modified by Fixing: {files_fixed}")
    rprint("[bold]--- End Summary ---[/bold]")

    return all_errors


def main():
    parser = argparse.ArgumentParser(
        description="Validate and optionally fix SRT subtitle files."
    )
    parser.add_argument(
        "input_path", help="Path to the SRT file or directory containing SRT files."
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Attempt to automatically fix detected issues.",
    )
    parser.add_argument(
        "--max-chars-per-line",
        type=int,
        default=DEFAULT_MAX_CHARS_PER_LINE,
        help=f"Maximum characters allowed per line (default: {DEFAULT_MAX_CHARS_PER_LINE}).",
    )
    parser.add_argument(
        "--max-lines-per-sub",
        type=int,
        default=DEFAULT_MAX_LINES_PER_SUB,
        help=f"Maximum lines allowed per subtitle (default: {DEFAULT_MAX_LINES_PER_SUB}).",
    )
    parser.add_argument(
        "--min-duration-ms",
        type=int,
        default=DEFAULT_MIN_SUB_DURATION_MS,
        help=f"Minimum duration for a subtitle in milliseconds (default: {DEFAULT_MIN_SUB_DURATION_MS}).",
    )
    parser.add_argument(
        "--max-duration-ms",
        type=int,
        default=DEFAULT_MAX_SUB_DURATION_MS,
        help=f"Maximum duration for a subtitle in milliseconds (default: {DEFAULT_MAX_SUB_DURATION_MS}).",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show more detailed error context."
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    if os.path.exists("Pipfile") and "PIPENV_ACTIVE" not in os.environ:
        rprint(
            "[yellow]INFO:[/yellow] Pipfile found but virtual environment not active.",
            file=sys.stderr,
        )
        rprint(
            "[yellow]INFO:[/yellow] Run using `pipenv run python validate_srt.py ...` for consistency.",
            file=sys.stderr,
        )

    all_errors = process_path(args.input_path, args)

    if not all_errors:
        rprint("\n[bold green]Validation finished successfully.[/bold green]")
        sys.exit(0)

    # Check for remaining critical errors after fixing
    has_critical_errors = any(e.error_type in CRITICAL_ERROR_TYPES for e in all_errors)

    if args.fix:
        if has_critical_errors:
            rprint(
                "\n[bold red]Fixing attempted, but critical errors remain.[/bold red]",
                file=sys.stderr,
            )
            sys.exit(1)
        else:
            rprint(
                "\n[yellow]Fixing finished. All correctable errors have been addressed.[/yellow]"
            )
            sys.exit(0)
    else:
        rprint(
            "\n[bold red]Validation finished with errors.[/bold red]", file=sys.stderr
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
