import srt
from typing import List, Tuple, Optional
from .models import ValidationError


def read_srt_content(file_path: str) -> Tuple[Optional[str], Optional[ValidationError]]:
    """Reads SRT file content, handling potential file errors."""
    try:
        with open(
            file_path, "r", encoding="utf-8-sig"
        ) as file:  # Use utf-8-sig to handle BOM
            return file.read(), None
    except FileNotFoundError:
        return None, ValidationError(
            file_path, None, None, "File Error", f"File not found: {file_path}"
        )
    except Exception as e:
        return None, ValidationError(
            file_path, None, None, "File Error", f"Error reading file {file_path}: {e}"
        )


def write_srt(
    file_path: str, subtitles: List[srt.Subtitle]
) -> Optional[ValidationError]:
    """Writes SRT subtitles to a file."""
    try:
        content_to_write = srt.compose(subtitles, reindex=False)
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(content_to_write)
        return None
    except Exception as e:
        return ValidationError(
            file_path, None, None, "File Error", f"Error writing file {file_path}: {e}"
        )
