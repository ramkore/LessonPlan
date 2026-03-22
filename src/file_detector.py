"""File type validation, extension checking, and size limits."""
from __future__ import annotations

from pathlib import Path

from .utils import MAX_UPLOAD_SIZE_BYTES, MAX_UPLOAD_SIZE_LABEL, SUPPORTED_EXTENSIONS, ProcessingError

DOCUMENT_TYPES = {'pdf', 'docx', 'text'}
IMAGE_TYPES = {'image'}
SPREADSHEET_TYPES = {'spreadsheet'}


def detect_file_type(file_path: str | Path) -> dict[str, str]:
    path = Path(file_path)
    extension = path.suffix.lower()
    file_type = SUPPORTED_EXTENSIONS.get(extension)

    if not file_type and extension == '' and path.exists() and path.is_file() and _looks_like_text_file(path):
        file_type = 'text'

    if not file_type:
        raise ProcessingError(
            f"Unsupported file format '{extension}'. Supported formats: PDF, DOCX, TXT, JPG, JPEG, PNG, XLSX, CSV."
        )

    if file_type in DOCUMENT_TYPES:
        category = 'document'
    elif file_type in IMAGE_TYPES:
        category = 'image'
    elif file_type in SPREADSHEET_TYPES:
        category = 'spreadsheet'
    else:
        raise ProcessingError(f"Unsupported file category for '{path.name}'.")

    return {
        'extension': extension,
        'type': file_type,
        'category': category,
        'name': path.name,
    }


def validate_file_type(file_path: str | Path) -> dict[str, str]:
    path = Path(file_path)
    if not path.exists():
        raise ProcessingError(f"File does not exist: {file_path}")
    size = path.stat().st_size
    if size == 0:
        raise ProcessingError(f"File '{path.name}' is empty.")
    if size > MAX_UPLOAD_SIZE_BYTES:
        size_mb = size / (1024 * 1024)
        raise ProcessingError(
            f"File '{path.name}' is {size_mb:.1f} MB, which exceeds the {MAX_UPLOAD_SIZE_LABEL} limit. "
            "Please reduce the file size or split it before uploading."
        )
    return detect_file_type(path)


def _looks_like_text_file(path: Path) -> bool:
    try:
        sample = path.read_bytes()[:4096]
    except OSError:
        return False

    if b'\x00' in sample:
        return False

    for encoding in ('utf-8', 'latin-1'):
        try:
            sample.decode(encoding)
            return True
        except UnicodeDecodeError:
            continue
    return False
