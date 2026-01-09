# SRT Validator and Fixer

A Python script to validate SubRip (`.srt`) subtitle files against common formatting and timing rules, with an option to automatically fix certain issues.

## Features

*   **Comprehensive Validation:**
    *   Checks for correct subtitle numbering sequence.
    *   Validates timecodes: Start time must be strictly less than end time.
    *   Detects overlapping subtitles (subsequent subtitle starting before the previous one ends).
    *   Checks subtitle duration against configurable minimum and maximum limits.
    *   Validates content formatting:
        *   Maximum characters per line.
        *   Maximum number of lines per subtitle block.
        *   Detects empty subtitle content blocks.
    *   Performs a basic check for unclosed common HTML tags (`<i>`, `<b>`, `<u>`, `<font>`).
    *   Handles SRT files with or without a Byte Order Mark (BOM).
*   **Optional Auto-Fixing (`--fix`):**
    *   Corrects sequential numbering.
    *   Adjusts overlapping timecodes (shifts the start time of the overlapping subtitle).
    *   Fixes basic formatting issues (removes carriage returns `\r`, collapses multiple blank lines, trims leading/trailing whitespace).
    *   Re-validates after fixing and fails if errors remain.
*   **Flexible Input:** Processes a single `.srt` file or recursively scans an entire directory.
*   **Configurable:** Validation parameters (line length, line count, duration limits) can be adjusted via command-line arguments.
*   **Clear Reporting:** Lists all validation errors found, including file path, subtitle index, and error type. Critical, unfixable errors are highlighted in red.
*   **Standard Exit Codes:** Returns exit code `0` when no errors are found (warnings do not fail by default) and `1` when errors are found. Use `--warnings-as-errors` to make warnings fail.

## Requirements

*   Python 3.10+ (Pipfile targets Python 3.13)
*   Pipenv

## Installation

1.  Clone this repository:
    ```bash
    git clone <repository_url> # Replace with your repository URL
    cd validate_srt_script
    ```
2.  Install dependencies using Pipenv:
    ```bash
    pipenv install
    ```
    This will create a virtual environment and install the required `srt` library.

## Usage

Always run the script using `pipenv run` to ensure it uses the correct virtual environment and dependencies.

**Basic Validation:**

```bash
pipenv run python validate_srt.py <path_to_file.srt>
```
or
```bash
pipenv run python validate_srt.py <path_to_directory>
```

**Validate and Automatically Fix Issues:**

```bash
pipenv run python validate_srt.py --fix <path_to_file_or_directory>
```
*Note: Fixing modifies the `.srt` files in place. Make backups if necessary.*

**Using Custom Validation Parameters:**

```bash
# Example: Allow 3 lines per subtitle and 50 chars per line
pipenv run python validate_srt.py --max-lines-per-sub 3 --max-chars-per-line 50 <path>

# Example: Set minimum duration to 0.5s and maximum to 10s
pipenv run python validate_srt.py --min-duration-ms 500 --max-duration-ms 10000 <path>
```

**Fail on Warnings:**

```bash
pipenv run python validate_srt.py --warnings-as-errors <path>
```

**Disable Color Output:**

```bash
pipenv run python validate_srt.py --no-color <path>
```

You can also set the `NO_COLOR` environment variable to disable color output.

**Get Help:**

```bash
pipenv run python validate_srt.py -h
```

## Project Structure

The project has been refactored for better maintainability:

*   `validate_srt.py`: The main command-line interface and entry point.
*   `validator/`: A package containing the core logic.
    *   `models.py`: Defines the `ValidationError` data class.
    *   `io.py`: Handles file reading and writing.
    *   `rules.py`: Contains all the validation logic.
    *   `fixer.py`: Contains the auto-fixing logic.
*   `test_validate_srt.py`: Contains the `pytest` unit tests for all functionality.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs, feature requests, or improvements.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
