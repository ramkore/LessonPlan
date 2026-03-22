"""PDF text and table extraction using pdfplumber and PyPDF2."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .image_ocr_parser import ocr_pil_image
from .logger import get_logger
from .utils import ParsedDocument, ProcessingError, table_to_dataframe

logger = get_logger(__name__)

MAX_OCR_PAGES = 20

try:
    import pdfplumber
except ImportError:  # pragma: no cover - depends on local environment
    pdfplumber = None

try:
    from PyPDF2 import PdfReader
except ImportError:  # pragma: no cover - depends on local environment
    PdfReader = None

try:
    import fitz
except ImportError:  # pragma: no cover - depends on local environment
    fitz = None

try:
    from PIL import Image
except ImportError:  # pragma: no cover - depends on local environment
    Image = None


def parse_pdf_file(file_path: str | Path) -> ParsedDocument:
    path = Path(file_path)
    text_parts: list[str] = []
    tables: list[pd.DataFrame] = []

    if pdfplumber is not None:
        try:
            with pdfplumber.open(path) as pdf:
                for page_number, page in enumerate(pdf.pages, start=1):
                    page_text = page.extract_text() or ''
                    if page_text.strip():
                        text_parts.append(page_text)

                    extracted_tables = page.extract_tables() or []
                    for table in extracted_tables:
                        frame = table_to_dataframe(table)
                        if not frame.empty:
                            frame.attrs['source_page'] = page_number
                            tables.append(frame)
        except Exception as exc:  # pragma: no cover - library behavior
            raise ProcessingError(f"Unable to parse PDF '{path.name}' with pdfplumber: {exc}") from exc

    if not text_parts and PdfReader is not None:
        try:
            reader = PdfReader(str(path))
            for page in reader.pages:
                page_text = page.extract_text() or ''
                if page_text.strip():
                    text_parts.append(page_text)
        except Exception as exc:  # pragma: no cover - library behavior
            raise ProcessingError(f"Unable to extract text from PDF '{path.name}': {exc}") from exc

    metadata = {'page_count': len(text_parts) or len(tables)}
    if not text_parts and not tables:
        ocr_texts = _ocr_scanned_pdf(path)
        if ocr_texts:
            text_parts = ocr_texts
            metadata['ocr'] = True
            metadata['page_count'] = len(ocr_texts)

    if not text_parts and not tables:
        if pdfplumber is None and PdfReader is None and fitz is None:
            raise ProcessingError('PDF support is unavailable. Install pdfplumber, PyPDF2, or PyMuPDF.')
        raise ProcessingError(f"No readable text or tables found in '{path.name}'.")

    return ParsedDocument(
        file_path=path,
        file_type='pdf',
        raw_text='\n\n'.join(text_parts),
        tables=tables,
        metadata=metadata,
    )


def _ocr_scanned_pdf(path: Path) -> list[str]:
    if fitz is None or Image is None:
        return []

    try:
        document = fitz.open(path)
    except Exception as exc:  # pragma: no cover - library behavior
        raise ProcessingError(f"Unable to open scanned PDF '{path.name}' for OCR: {exc}") from exc

    texts: list[str] = []
    page_limit = min(document.page_count, MAX_OCR_PAGES)
    if document.page_count > MAX_OCR_PAGES:
        logger.warning("PDF '%s' has %d pages; OCR limited to first %d", path.name, document.page_count, MAX_OCR_PAGES)
    try:
        for page_number in range(page_limit):
            page = document.load_page(page_number)
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
            pil_image = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
            page_text = ocr_pil_image(pil_image, f'{path.name} page {page_number + 1}')
            texts.append(page_text)
    except ProcessingError:
        raise
    except Exception as exc:  # pragma: no cover - library behavior
        raise ProcessingError(f"Unable to OCR scanned PDF '{path.name}': {exc}") from exc
    finally:
        document.close()

    return texts
