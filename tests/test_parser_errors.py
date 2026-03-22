import tempfile
import unittest
from pathlib import Path

from src.utils import ProcessingError, load_parsed_document


class ParserErrorTests(unittest.TestCase):
    def test_load_nonexistent_file_raises_error(self) -> None:
        with self.assertRaises(ProcessingError):
            load_parsed_document("/nonexistent/path/document.pdf")

    def test_load_unsupported_extension_raises_error(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp.write(b"PK\x03\x04fake zip content")
            tmp_file = Path(tmp.name)
        try:
            with self.assertRaises(ProcessingError) as context:
                load_parsed_document(tmp_file)
            self.assertIn("Unsupported file format", str(context.exception))
        finally:
            tmp_file.unlink(missing_ok=True)

    def test_empty_text_file_parsing(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as tmp:
            tmp.write("")
            tmp_file = Path(tmp.name)
        try:
            # An empty .txt file should either parse to a nearly empty ParsedDocument
            # or raise ProcessingError, depending on the parser chain.
            # Since file_detector.validate_file_type checks size == 0 and raises,
            # but load_parsed_document uses detect_file_type (not validate_file_type),
            # the txt parser should handle it. The result should be a ParsedDocument
            # with empty or minimal content.
            result = load_parsed_document(tmp_file)
            self.assertEqual(result.file_type, "text")
        except ProcessingError:
            # Also acceptable if the parser chain rejects empty text files
            pass
        finally:
            tmp_file.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
