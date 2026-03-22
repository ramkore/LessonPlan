"""Spreadsheet parsing for CSV and XLSX files."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .utils import ParsedDocument, ProcessingError, clean_dataframe


def parse_spreadsheet_file(file_path: str | Path) -> ParsedDocument:
    path = Path(file_path)
    tables: list[pd.DataFrame] = []
    text_sections: list[str] = []
    metadata: dict[str, object] = {"sheets": []}

    try:
        if path.suffix.lower() == ".csv":
            frame = clean_dataframe(pd.read_csv(path))
            if not frame.empty:
                tables.append(frame)
                text_sections.append(frame.to_string(index=False))
                metadata["sheets"] = ["CSV"]
        else:
            workbook = pd.read_excel(path, sheet_name=None)
            metadata["sheets"] = list(workbook.keys())
            for sheet_name, frame in workbook.items():
                cleaned = clean_dataframe(frame)
                if cleaned.empty:
                    continue
                cleaned.attrs["sheet_name"] = sheet_name
                tables.append(cleaned)
                text_sections.append(f"Sheet: {sheet_name}\n{cleaned.to_string(index=False)}")
    except Exception as exc:  # pragma: no cover - library behavior
        raise ProcessingError(f"Unable to parse spreadsheet '{path.name}': {exc}") from exc

    if not tables:
        raise ProcessingError(f"No readable data found in spreadsheet '{path.name}'.")

    return ParsedDocument(
        file_path=path,
        file_type="spreadsheet",
        raw_text="\n\n".join(text_sections),
        tables=tables,
        metadata=metadata,
    )
