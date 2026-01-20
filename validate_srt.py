import argparse
import io
import json
import os
import sys
from dataclasses import dataclass
from typing import List, Optional, TextIO, Tuple

import srt
from rich.console import Console
from rich.markup import escape as escape_markup

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


@dataclass
class ValidationSummary:
    files_processed: int = 0
    files_with_errors: int = 0
    files_with_warnings: int = 0
    files_fixed: int = 0


def build_console(no_color: bool, file: Optional[TextIO] = None) -> Console:
    force_terminal = False if no_color else None
    return Console(no_color=no_color, file=file, force_terminal=force_terminal)


def _strip_wrapping_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def normalize_input_path(input_path: str) -> str:
    path = input_path.strip()
    expanded = os.path.expandvars(os.path.expanduser(path))
    if os.path.exists(expanded):
        return expanded

    candidate = expanded
    for _ in range(2):
        unwrapped = _strip_wrapping_quotes(candidate)
        if unwrapped == candidate:
            break
        expanded_unwrapped = os.path.expandvars(os.path.expanduser(unwrapped))
        if os.path.exists(expanded_unwrapped):
            return expanded_unwrapped
        candidate = unwrapped

    return expanded


def validation_error_to_dict(
    error: ValidationError, include_content: bool
) -> dict[str, Optional[object]]:
    return {
        "file_path": error.file_path,
        "subtitle_index": error.subtitle_index,
        "line_number": error.line_number,
        "error_type": error.error_type,
        "message": error.message,
        "severity": error.severity,
        "content": error.content if include_content else None,
        "is_breaking": error.error_type in CRITICAL_ERROR_TYPES,
    }


def build_json_report(
    *,
    input_path: str,
    issues: List[ValidationError],
    summary: ValidationSummary,
    warnings_as_errors: bool,
    fail_on_warnings: bool,
    fix: bool,
    verbose: bool,
    exit_code: int,
) -> dict[str, object]:
    errors = [issue for issue in issues if issue.severity == "error"]
    warnings = [issue for issue in issues if issue.severity == "warning"]
    return {
        "input_path": input_path,
        "files_processed": summary.files_processed,
        "files_with_errors": summary.files_with_errors,
        "files_with_warnings": summary.files_with_warnings,
        "files_fixed": summary.files_fixed,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "warnings_as_errors": warnings_as_errors,
        "fail_on_warnings": fail_on_warnings,
        "fix": fix,
        "exit_code": exit_code,
        "issues": [
            validation_error_to_dict(issue, include_content=verbose) for issue in issues
        ],
    }


def print_validation_errors(
    errors: List[ValidationError],
    file_path: str,
    verbose: bool,
    console: Optional[Console] = None,
):
    """Prints validation issues using rich formatting."""
    console = console or Console()
    has_errors = any(error.severity == "error" for error in errors)
    header = "Errors found in" if has_errors else "Warnings found in"
    console.print(f"[bold]{header} [cyan]{escape_markup(file_path)}[/cyan]:[/bold]")

    for error in errors:
        is_breaking = error.error_type in CRITICAL_ERROR_TYPES
        color = "bold red" if is_breaking else "yellow"

        line_info = f"L{error.line_number}" if error.line_number else "N/A"
        sub_info = (
            f"Sub:{error.subtitle_index}"
            if error.subtitle_index is not None
            else "File-level"
        )

        label = escape_markup(f"[{sub_info} ({line_info})]")
        message = escape_markup(error.message)
        console.print(f"  - [{color}]{label} {error.error_type}: {message}[/{color}]")
        if error.content and verbose:
            content_preview = error.content.replace("\n", " ")
            content_label = escape_markup(
                f"Content: {content_preview[:100]}{'...' if len(content_preview) > 100 else ''}"
            )
            console.print(f"    [{color}]{content_label}[/{color}]")
    console.print("[bold]--- End Errors ---[/bold]")


def process_srt_file(
    file_path: str,
    args: argparse.Namespace,
    console: Optional[Console] = None,
    err_console: Optional[Console] = None,
) -> Tuple[List[ValidationError], List[str]]:
    """Validates and optionally fixes a single SRT file."""
    console = console or Console()
    err_console = err_console or Console(file=sys.stderr)
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
    has_errors = any(error.severity == "error" for error in validation_errors)
    has_blocking_errors = any(
        error.error_type in {"Timecode Format Error", "Parsing Error"}
        for error in validation_errors
    )

    if args.fix and has_errors and not has_blocking_errors:
        console.print(f"Attempting to fix [cyan]{escape_markup(file_path)}[/cyan]...")
        try:
            subtitles_to_fix = list(srt.parse(content))
            fixed_subtitles, fixes_applied = fix_srt_subtitles(subtitles_to_fix)
            if fixes_applied:
                write_error = write_srt(file_path, fixed_subtitles)
                if write_error:
                    validation_errors.append(write_error)
                else:
                    console.print(
                        f"Fixes applied ([green]{', '.join(fixes_applied)}[/green]) to: [cyan]{escape_markup(file_path)}[/cyan]"
                    )
                    fixed_content, reread_error = read_srt_content(file_path)
                    if reread_error:
                        return [reread_error], fixes_applied
                    if fixed_content is None:
                        return [
                            ValidationError(
                                file_path,
                                None,
                                None,
                                "Internal Error",
                                "Failed to read content after writing unexpectedly.",
                            )
                        ], fixes_applied
                    validation_errors = validate_srt_content(
                        file_path,
                        fixed_content,
                        args.max_chars_per_line,
                        args.max_lines_per_sub,
                        args.min_duration_ms,
                        args.max_duration_ms,
                    )
            else:
                console.print(
                    f"No automatic fixes applied for: [cyan]{escape_markup(file_path)}[/cyan]"
                )
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
            err_console.print(
                f"Error during fixing process for [cyan]{escape_markup(file_path)}[/cyan]: {escape_markup(str(e))}",
            )

    return validation_errors, fixes_applied


def process_path(
    input_path: str,
    args: argparse.Namespace,
    summary: Optional[ValidationSummary] = None,
    console: Optional[Console] = None,
    err_console: Optional[Console] = None,
) -> List[ValidationError]:
    """Processes a single file or all SRT files in a directory."""
    input_path = normalize_input_path(input_path)
    console = console or Console()
    err_console = err_console or Console(file=sys.stderr)
    summary = summary or ValidationSummary()
    all_errors: List[ValidationError] = []
    files_to_process: List[str] = []

    if os.path.isfile(input_path):
        if input_path.lower().endswith(".srt"):
            files_to_process.append(input_path)
        else:
            err_console.print(
                f"[yellow]Skipping non-SRT file:[/yellow] {escape_markup(input_path)}",
            )
    elif os.path.isdir(input_path):
        console.print(f"Processing directory: [cyan]{escape_markup(input_path)}[/cyan]")
        for root, _, files in os.walk(input_path):
            for file in sorted(files):
                if file.lower().endswith(".srt"):
                    files_to_process.append(os.path.join(root, file))
    else:
        err_console.print(
            f"[bold red]Error:[/bold red] Input path not found: {escape_markup(input_path)}",
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

    for file_path in files_to_process:
        console.print(f"--- Processing: [cyan]{escape_markup(file_path)}[/cyan] ---")
        summary.files_processed += 1

        errors, fixes = process_srt_file(
            file_path, args, console=console, err_console=err_console
        )
        has_errors = any(error.severity == "error" for error in errors)
        has_warnings = any(error.severity == "warning" for error in errors)

        if has_errors:
            summary.files_with_errors += 1
            all_errors.extend(errors)
            print_validation_errors(errors, file_path, args.verbose, console=console)
        elif has_warnings:
            summary.files_with_warnings += 1
            all_errors.extend(errors)
            print_validation_errors(errors, file_path, args.verbose, console=console)
        else:
            console.print(
                f"[green]Validation passed for:[/green] {escape_markup(file_path)}"
            )

        if fixes:
            summary.files_fixed += 1

        console.print("")

    console.print("\n[bold]--- Validation Summary ---[/bold]")
    console.print(f"Files Processed: {summary.files_processed}")
    console.print(f"Files with Errors: {summary.files_with_errors}")
    console.print(f"Files with Warnings: {summary.files_with_warnings}")
    if args.fix:
        console.print(f"Files Modified by Fixing: {summary.files_fixed}")
    console.print("[bold]--- End Summary ---[/bold]")

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
    parser.add_argument(
        "--warnings-as-errors",
        action="store_true",
        help="Return a failing exit code if warnings are found.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON to stdout.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        default=os.environ.get("NO_COLOR") is not None,
        help="Disable colorized output (also respects NO_COLOR).",
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()
    args.input_path = normalize_input_path(args.input_path)
    if args.json:
        args.no_color = True

        null_stream = io.StringIO()
        console = build_console(True, file=null_stream)
        err_console = build_console(True, file=null_stream)
        summary = ValidationSummary()

        all_issues = process_path(
            args.input_path,
            args,
            summary=summary,
            console=console,
            err_console=err_console,
        )
        errors = [issue for issue in all_issues if issue.severity == "error"]
        warnings = [issue for issue in all_issues if issue.severity == "warning"]
        fail_on_warnings = args.warnings_as_errors and bool(warnings)
        exit_code = 0 if not errors and not fail_on_warnings else 1

        report = build_json_report(
            input_path=args.input_path,
            issues=all_issues,
            summary=summary,
            warnings_as_errors=args.warnings_as_errors,
            fail_on_warnings=fail_on_warnings,
            fix=args.fix,
            verbose=args.verbose,
            exit_code=exit_code,
        )
        print(json.dumps(report))
        sys.exit(exit_code)

    console = build_console(args.no_color)
    err_console = build_console(args.no_color, file=sys.stderr)

    if os.path.exists("Pipfile") and "PIPENV_ACTIVE" not in os.environ:
        err_console.print(
            "[yellow]INFO:[/yellow] Pipfile found but virtual environment not active.",
        )
        err_console.print(
            "[yellow]INFO:[/yellow] Run using `pipenv run python validate_srt.py ...` for consistency.",
        )

    all_issues = process_path(
        args.input_path, args, console=console, err_console=err_console
    )
    errors = [issue for issue in all_issues if issue.severity == "error"]
    warnings = [issue for issue in all_issues if issue.severity == "warning"]
    fail_on_warnings = args.warnings_as_errors and bool(warnings)

    if not errors and not fail_on_warnings:
        if warnings:
            console.print("\n[yellow]Validation finished with warnings.[/yellow]")
        else:
            console.print(
                "\n[bold green]Validation finished successfully.[/bold green]"
            )
        sys.exit(0)

    if errors:
        message = (
            "\n[bold red]Fixing attempted, but errors remain.[/bold red]"
            if args.fix
            else "\n[bold red]Validation finished with errors.[/bold red]"
        )
    else:
        message = (
            "\n[bold red]Fixing finished with warnings (treated as errors).[/bold red]"
            if args.fix
            else "\n[bold red]Validation finished with warnings (treated as errors).[/bold red]"
        )

    err_console.print(message)
    sys.exit(1)


if __name__ == "__main__":
    main()
