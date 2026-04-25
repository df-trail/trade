from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from ztrade.env import load_env_file


class EnvLoaderTests(unittest.TestCase):
    def test_load_env_file_sets_missing_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / ".env"
            path.write_text("ZTRADE_TEST_KEY='abc123'\n# comment\nEMPTY=\n", encoding="utf-8")
            os.environ.pop("ZTRADE_TEST_KEY", None)
            load_env_file(path)
            self.assertEqual(os.environ["ZTRADE_TEST_KEY"], "abc123")
            self.assertEqual(os.environ["EMPTY"], "")
            os.environ.pop("ZTRADE_TEST_KEY", None)
            os.environ.pop("EMPTY", None)

    def test_load_env_file_does_not_override_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / ".env"
            path.write_text("ZTRADE_TEST_KEY=new\n", encoding="utf-8")
            os.environ["ZTRADE_TEST_KEY"] = "existing"
            load_env_file(path)
            self.assertEqual(os.environ["ZTRADE_TEST_KEY"], "existing")
            os.environ.pop("ZTRADE_TEST_KEY", None)


if __name__ == "__main__":
    unittest.main()
