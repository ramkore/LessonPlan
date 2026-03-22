import unittest
from pathlib import Path
from unittest.mock import patch

from src.file_detector import detect_file_type, validate_file_type
from src.utils import ProcessingError


class FileDetectorTests(unittest.TestCase):
    def test_detect_supported_pdf_extension(self) -> None:
        result = detect_file_type("example.pdf")
        self.assertEqual(result["extension"], ".pdf")
        self.assertEqual(result["type"], "pdf")
        self.assertEqual(result["category"], "document")

    def test_detect_supported_docx_extension(self) -> None:
        result = detect_file_type("report.docx")
        self.assertEqual(result["extension"], ".docx")
        self.assertEqual(result["type"], "docx")
        self.assertEqual(result["category"], "document")

    def test_detect_unsupported_extension_raises_error(self) -> None:
        with self.assertRaises(ProcessingError) as context:
            detect_file_type("archive.zip")
        self.assertIn("Unsupported file format", str(context.exception))

    def test_validate_empty_file_raises_error(self, tmp_path: Path = None) -> None:
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(b"")
            tmp_file = Path(tmp.name)
        try:
            with self.assertRaises(ProcessingError) as context:
                validate_file_type(tmp_file)
            self.assertIn("empty", str(context.exception))
        finally:
            tmp_file.unlink(missing_ok=True)

    def test_validate_nonexistent_file_raises_error(self) -> None:
        with self.assertRaises(ProcessingError) as context:
            validate_file_type("/nonexistent/path/file.pdf")
        self.assertIn("does not exist", str(context.exception))

    def test_validate_oversized_file_raises_error(self) -> None:
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(b"x" * 100)
            tmp_file = Path(tmp.name)
        try:
            with patch("src.file_detector.MAX_UPLOAD_SIZE_BYTES", 50):
                with self.assertRaises(ProcessingError) as context:
                    validate_file_type(tmp_file)
                self.assertIn("exceeds", str(context.exception))
        finally:
            tmp_file.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
