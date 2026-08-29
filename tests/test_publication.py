"""Tests for atomic report-directory publication."""

from pathlib import Path
import tempfile
import unittest

from ppar.publication import atomic_output_directory


class AtomicOutputDirectoryTests(unittest.TestCase):
    """The prior report bundle survives failures and is replaced on success."""

    def test_success_replaces_complete_output(self) -> None:
        """A successful context publishes only the new files."""
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            output.mkdir()
            (output / "old.txt").write_text("old", encoding="utf-8")

            with atomic_output_directory(output) as staging:
                (staging / "new.txt").write_text("new", encoding="utf-8")

            self.assertEqual([path.name for path in output.iterdir()], ["new.txt"])

    def test_failure_preserves_prior_output(self) -> None:
        """An exception discards staging and leaves the prior bundle untouched."""
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            output.mkdir()
            (output / "old.txt").write_text("old", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "stop"):
                with atomic_output_directory(output) as staging:
                    (staging / "partial.txt").write_text("partial", encoding="utf-8")
                    raise RuntimeError("stop")

            self.assertEqual((output / "old.txt").read_text(encoding="utf-8"), "old")
            self.assertFalse((output / "partial.txt").exists())


if __name__ == "__main__":
    unittest.main()
