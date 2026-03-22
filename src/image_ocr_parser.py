"""Image OCR parsing using pytesseract for scanned documents."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from .utils import ParsedDocument, ProcessingError, clean_dataframe, normalize_whitespace, table_to_dataframe

try:
    import cv2
except ImportError:  # pragma: no cover - depends on local environment
    cv2 = None

try:
    from PIL import Image
except ImportError:  # pragma: no cover - depends on local environment
    Image = None

try:
    import pytesseract
except ImportError:  # pragma: no cover - depends on local environment
    pytesseract = None


TESSERACT_ERROR_MESSAGE = 'Tesseract OCR engine was not found. Install Tesseract and add it to the system PATH.'


def ensure_ocr_dependencies() -> None:
    if cv2 is None or Image is None or pytesseract is None:
        raise ProcessingError('Image OCR dependencies are missing. Install opencv-python, Pillow, and pytesseract.')


def preprocess_cv_image(image):
    ensure_ocr_dependencies()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, None, 12, 7, 21)
    _, threshold = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return threshold


def pil_to_cv_image(image: Image.Image):
    ensure_ocr_dependencies()
    rgb_image = image.convert('RGB')
    return cv2.cvtColor(np.array(rgb_image), cv2.COLOR_RGB2BGR)


def ocr_processed_pil_image(image: Image.Image, source_name: str = 'image') -> str:
    ensure_ocr_dependencies()
    try:
        text = pytesseract.image_to_string(image, config='--psm 6', timeout=30)
    except pytesseract.TesseractNotFoundError as exc:  # pragma: no cover - depends on local environment
        raise ProcessingError(TESSERACT_ERROR_MESSAGE) from exc
    except RuntimeError as exc:  # pragma: no cover - timeout
        raise ProcessingError(f"OCR timed out on '{source_name}': {exc}") from exc
    except Exception as exc:  # pragma: no cover - library behavior
        raise ProcessingError(f"Unable to perform OCR on '{source_name}': {exc}") from exc

    cleaned = text.strip()
    if not cleaned:
        raise ProcessingError(f"OCR completed but no text could be extracted from '{source_name}'.")
    return cleaned


def ocr_pil_image(image: Image.Image, source_name: str = 'image') -> str:
    processed = preprocess_cv_image(pil_to_cv_image(image))
    return ocr_processed_pil_image(Image.fromarray(processed), source_name)


def parse_image_file(file_path: str | Path) -> ParsedDocument:
    path = Path(file_path)
    ensure_ocr_dependencies()

    image = cv2.imread(str(path))
    if image is None:
        raise ProcessingError(f"Unable to read image '{path.name}'.")

    processed = preprocess_cv_image(image)
    text = ocr_processed_pil_image(Image.fromarray(processed), path.name)
    tables = _extract_tables_from_image(image, processed, path.name)

    return ParsedDocument(
        file_path=path,
        file_type='image',
        raw_text=text,
        tables=tables,
        metadata={'ocr': True, 'table_count': len(tables)},
    )


def _extract_tables_from_image(image, processed_image, source_name: str) -> list[pd.DataFrame]:
    ensure_ocr_dependencies()
    binary_inverted = _binary_inverted(image)
    table_box = _find_largest_table_box(binary_inverted)
    if not table_box:
        return []

    x, y, width, height = table_box
    processed_roi = processed_image[y : y + height, x : x + width]
    binary_roi = binary_inverted[y : y + height, x : x + width]

    horizontal_lines, vertical_lines = _extract_line_masks(binary_roi)
    x_positions = _group_positions(np.where((vertical_lines > 0).sum(axis=0) > height * 0.20)[0])
    y_positions = _group_positions(np.where((horizontal_lines > 0).sum(axis=1) > width * 0.20)[0])

    if len(x_positions) < 3 or len(y_positions) < 3:
        return []

    matrix: list[list[str]] = []
    for row_index in range(len(y_positions) - 1):
        row: list[str] = []
        top = y_positions[row_index] + 4
        bottom = y_positions[row_index + 1] - 4
        for column_index in range(len(x_positions) - 1):
            left = x_positions[column_index] + 4
            right = x_positions[column_index + 1] - 4
            if bottom <= top or right <= left:
                row.append('')
                continue
            cell = processed_roi[top:bottom, left:right]
            row.append(_ocr_cell(cell, source_name))
        matrix.append(row)

    frame = _matrix_to_frame(matrix)
    return [frame] if not frame.empty else []


def _binary_inverted(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, threshold = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return threshold


def _extract_line_masks(binary_inverted):
    height, width = binary_inverted.shape[:2]
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(30, width // 20), 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(30, height // 20)))
    horizontal_lines = cv2.morphologyEx(binary_inverted, cv2.MORPH_OPEN, horizontal_kernel)
    vertical_lines = cv2.morphologyEx(binary_inverted, cv2.MORPH_OPEN, vertical_kernel)
    return horizontal_lines, vertical_lines


def _find_largest_table_box(binary_inverted):
    horizontal_lines, vertical_lines = _extract_line_masks(binary_inverted)
    grid = cv2.add(horizontal_lines, vertical_lines)
    contours, _ = cv2.findContours(grid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    image_height, image_width = binary_inverted.shape[:2]
    minimum_area = image_height * image_width * 0.05
    candidates = []
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        area = width * height
        if area < minimum_area:
            continue
        if width < image_width * 0.30 or height < image_height * 0.15:
            continue
        candidates.append((x, y, width, height))

    if not candidates:
        return None
    return max(candidates, key=lambda item: item[2] * item[3])


def _group_positions(indices: np.ndarray, max_gap: int = 5) -> list[int]:
    if len(indices) == 0:
        return []

    grouped: list[int] = []
    start = int(indices[0])
    previous = int(indices[0])
    for value in indices[1:]:
        current = int(value)
        if current - previous > max_gap:
            grouped.append((start + previous) // 2)
            start = current
        previous = current
    grouped.append((start + previous) // 2)
    return grouped


def _ocr_cell(cell_image, source_name: str) -> str:
    if cell_image.size == 0:
        return ''
    if np.mean(cell_image < 245) < 0.01:
        return ''

    pil_image = Image.fromarray(cell_image)
    try:
        text = pytesseract.image_to_string(pil_image, config='--psm 7', timeout=10).strip()
        if not text:
            text = pytesseract.image_to_string(pil_image, config='--psm 6', timeout=10).strip()
    except pytesseract.TesseractNotFoundError as exc:  # pragma: no cover - depends on local environment
        raise ProcessingError(TESSERACT_ERROR_MESSAGE) from exc
    except RuntimeError as exc:  # pragma: no cover - timeout
        raise ProcessingError(f"OCR cell timed out on '{source_name}': {exc}") from exc
    except Exception as exc:  # pragma: no cover - library behavior
        raise ProcessingError(f"Unable to perform OCR on a table cell in '{source_name}': {exc}") from exc
    return normalize_whitespace(text)


def _matrix_to_frame(rows: list[list[str]]) -> pd.DataFrame:
    trimmed_rows = _trim_matrix(rows)
    if not trimmed_rows:
        return pd.DataFrame()

    if _should_merge_header_rows(trimmed_rows):
        headers = _merge_header_rows(trimmed_rows[0], trimmed_rows[1])
        data_rows = trimmed_rows[2:]
    elif _looks_like_header_row(trimmed_rows[0]):
        headers = [_normalize_header_name(value, index) for index, value in enumerate(trimmed_rows[0])]
        data_rows = trimmed_rows[1:]
    else:
        return table_to_dataframe(trimmed_rows)

    if not data_rows:
        return pd.DataFrame(columns=headers)

    width = max(len(headers), max(len(row) for row in data_rows))
    padded_headers = _pad_row(headers, width, use_fallback_names=True)
    padded_rows = [_pad_row(row, width) for row in data_rows]
    frame = pd.DataFrame(padded_rows, columns=padded_headers)
    return clean_dataframe(frame)


def _trim_matrix(rows: list[list[str]]) -> list[list[str]]:
    normalized_rows = [[normalize_whitespace(cell) for cell in row] for row in rows]
    normalized_rows = [row for row in normalized_rows if any(cell for cell in row)]
    if not normalized_rows:
        return []

    non_empty_columns = [index for index in range(max(len(row) for row in normalized_rows)) if any(index < len(row) and row[index] for row in normalized_rows)]
    if not non_empty_columns:
        return []

    trimmed = []
    for row in normalized_rows:
        trimmed.append([row[index] if index < len(row) else '' for index in non_empty_columns])
    return trimmed


def _should_merge_header_rows(rows: list[list[str]]) -> bool:
    if len(rows) < 2:
        return False
    combined = ' '.join(rows[0] + rows[1]).lower()
    header_hints = ('description', 'duration', 'from', 'to', 'date', 'occasion', 'day')
    return any(hint in combined for hint in header_hints)


def _looks_like_header_row(row: list[str]) -> bool:
    combined = ' '.join(row).lower()
    header_hints = ('description', 'from', 'to', 'date', 'occasion', 'day', 'duration')
    return any(hint in combined for hint in header_hints)


def _merge_header_rows(first_row: list[str], second_row: list[str]) -> list[str]:
    width = max(len(first_row), len(second_row))
    merged: list[str] = []
    for index in range(width):
        top = first_row[index] if index < len(first_row) else ''
        bottom = second_row[index] if index < len(second_row) else ''
        top_clean = '' if top.lower() == 'duration' and bottom else top
        header = f'{top_clean} {bottom}' if top_clean and bottom else bottom or top_clean
        merged.append(_normalize_header_name(header, index))
    return merged


def _normalize_header_name(value: str, index: int) -> str:
    lowered = normalize_whitespace(value).lower()
    if not lowered:
        return f'column_{index + 1}'
    if 'description' in lowered:
        return 'Description'
    if 'occasion' in lowered:
        return 'Occasion'
    if re.search(r'\bfrom\b', lowered):
        return 'From'
    if re.search(r'\bto\b', lowered):
        return 'To'
    if re.search(r'\bdate\b', lowered):
        return 'Date'
    if re.search(r'\bday\b', lowered):
        return 'Day'
    if lowered.startswith('s.no') or lowered in {'sno', 's no', 'sl no', 'serial no'}:
        return 'S.No'
    return value.strip() or f'column_{index + 1}'


def _pad_row(values: list[str], width: int, use_fallback_names: bool = False) -> list[str]:
    padded = list(values[:width])
    while len(padded) < width:
        if use_fallback_names:
            padded.append(f'column_{len(padded) + 1}')
        else:
            padded.append('')
    return padded
