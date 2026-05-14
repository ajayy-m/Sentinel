from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

try:
    import pyarrow.parquet as pq
except ImportError:  # pragma: no cover - dependency checked in runtime
    pq = None

from sentinel.core.archive import run_archive
from sentinel.core.storage import Storage


@unittest.skipIf(pq is None, "pyarrow is required for archive tests")
class TestArchive(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp_dir.name) / "sentinel_archive_test.db"
        self.output_dir = Path(self._tmp_dir.name) / "archive"
        self.storage = Storage(str(self.db_path))

    def tearDown(self) -> None:
        self.storage.close()
        self._tmp_dir.cleanup()

    def test_archive_writes_parquet_and_manifest(self) -> None:
        self.storage.store_payload(
            {
                "node": {"node_id": "node-a"},
                "timestamp_utc": "2026-05-04T00:00:00Z",
                "metrics": {"cpu": {"usage_percent": 42.0}},
            }
        )

        config = {"collector": {"sqlite_path": str(self.db_path)}}
        stdout = StringIO()
        with redirect_stdout(stdout):
            run_archive(
                config,
                before="2099-01-01",
                output_dir=str(self.output_dir),
                dry_run=False,
            )

        parquet_file = self.output_dir / "metric_payloads" / "before=2099-01-01" / "metric_payloads.parquet"
        manifest_file = self.output_dir / "manifest-before=2099-01-01.json"

        self.assertTrue(parquet_file.exists())
        self.assertTrue(manifest_file.exists())

        table = pq.read_table(parquet_file)
        self.assertEqual(table.num_rows, 1)
        self.assertEqual(table.column("node_id").to_pylist()[0], "node-a")


if __name__ == "__main__":
    unittest.main()
