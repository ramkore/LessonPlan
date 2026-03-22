import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from src import utils
from src.utils import load_parsed_document, project_root


class ParsedDocumentCacheTests(unittest.TestCase):
    def _workspace_temp_dir(self) -> Path:
        path = project_root() / "tmp" / "test_cache" / uuid4().hex
        path.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(path, ignore_errors=True))
        return path

    def test_load_parsed_document_reuses_cache_for_text_file(self) -> None:
        temp_dir = self._workspace_temp_dir()
        path = temp_dir / "sample.txt"
        path.write_text("Alpha content", encoding="utf-8")
        cache_path = utils._parsed_document_cache_path(path.resolve())
        cache_path.unlink(missing_ok=True)

        first = load_parsed_document(path)

        with patch("src.doc_parser.parse_document_file", side_effect=AssertionError("cache was not used")):
            second = load_parsed_document(path)

        self.assertEqual(first.raw_text, "Alpha content")
        self.assertEqual(second.raw_text, "Alpha content")
        self.assertTrue(cache_path.exists())

        cache_path.unlink(missing_ok=True)

    def test_load_parsed_document_invalidates_cache_when_source_changes(self) -> None:
        temp_dir = self._workspace_temp_dir()
        path = temp_dir / "sample.txt"
        path.write_text("First version", encoding="utf-8")
        cache_path = utils._parsed_document_cache_path(path.resolve())
        cache_path.unlink(missing_ok=True)

        initial = load_parsed_document(path)
        self.assertEqual(initial.raw_text, "First version")

        path.write_text("Second version", encoding="utf-8")
        stat = path.stat()
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))

        refreshed = load_parsed_document(path)

        self.assertEqual(refreshed.raw_text, "Second version")
        cache_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
