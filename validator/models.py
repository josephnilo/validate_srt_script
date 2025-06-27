from typing import NamedTuple, Optional


class ValidationError(NamedTuple):
    file_path: str
    subtitle_index: Optional[int]
    line_number: Optional[int]  # Line number in the original file
    error_type: str
    message: str
    content: Optional[str] = None  # problematic content/line
