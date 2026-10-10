"""Actual-filesystem coverage for sibling historical diagnostic output creation.

Only packet computation is controlled in the three CLI tests. Namespace checks,
serialization and file creation remain real. Crank helpers use a one-pixel codec
fixture, not source evidence; these tests do not exercise copyrighted-video
extraction, source identity checks, motion measurement or native geometry.
"""
from contextlib import redirect_stdout
import gzip
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
SENTINEL = b"original sentinel must survive\x00\xff\r\n"


def load_script(filename, name):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def packet():
    return {
        "kind": "historical-source-track-receipt",
        "historicalDiagnostic": True,
        "publishable": False,
        "productionIntegrated": False,
        "summary": {"count": 2},
        "sourceMeasurementCounts": {"count": 2},
        "fileIoFixture": {"text": "caf\u00e9\nsecond line", "values": [1.25, -0.0, None]},
    }


def text_bytes(contents):
    # Path.write_text's default newline translation is part of the old format.
    return contents.replace("\n", os.linesep).encode("utf-8")


def legacy_calibration_bytes(value, suffix):
    contents = json.dumps(value, indent=2) + "\n"
    if suffix != ".json.gz":
        return text_bytes(contents)
    encoded = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=encoded,
                       compresslevel=9, mtime=0) as compressed:
        compressed.write(contents.encode("utf-8"))
    return encoded.getvalue()


class HistoricalCliOutputCreationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        analysis = load_script("generate-analysis-bank-source-controls.py",
                               "historical_output_analysis")
        spin = load_script("generate-spin-source-controls.py", "historical_output_spin")
        calibration = load_script("NAsM30MAHLg-calibrate-static.py",
                                  "historical_output_calibration")
        cls.cases = (
            (analysis, "build_packet", ".json", False),
            (spin, "build_packet", ".json", False),
            (calibration, "run", ".json", True),
            (calibration, "run", ".json.gz", True),
        )

    def invoke(self, module, hook, destination, compute):
        arguments = [module.__file__, "--historical-diagnostic",
                     "--output", str(destination)]
        with patch.object(sys, "argv", arguments), \
                patch.object(module, hook, side_effect=compute) as computation, \
                redirect_stdout(io.StringIO()):
            try:
                module.main()
            finally:
                computation.assert_called_once()
                self.assertIs(computation.call_args.kwargs["historical_diagnostic"], True)

    def test_computation_time_leaf_symlink_insertion_refuses_and_preserves_sentinel(self):
        for module, hook, suffix, _ in self.cases:
            with self.subTest(script=Path(module.__file__).name, suffix=suffix), \
                    tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                destination = root / ("receipt" + suffix)
                sentinel = root / "sentinel.bin"
                sentinel.write_bytes(SENTINEL)

                def compute(*args, **kwargs):
                    self.assertFalse(destination.exists())
                    destination.symlink_to(sentinel)
                    return packet()

                with self.assertRaises((ValueError, OSError)):
                    self.invoke(module, hook, destination, compute)
                self.assertTrue(destination.is_symlink())
                self.assertEqual(sentinel.read_bytes(), SENTINEL)
                self.assertEqual(destination.read_bytes(), SENTINEL)

    def test_successful_outputs_preserve_exact_serialization(self):
        for module, hook, suffix, pretty in self.cases:
            with self.subTest(script=Path(module.__file__).name, suffix=suffix), \
                    tempfile.TemporaryDirectory() as directory:
                destination = Path(directory).resolve() / ("receipt" + suffix)
                value = packet()
                self.invoke(module, hook, destination, lambda *args, **kwargs: value)
                expected = (legacy_calibration_bytes(value, suffix) if pretty else
                            text_bytes(json.dumps(value, separators=(",", ":"),
                                                  allow_nan=False) + "\n"))
                self.assertEqual(destination.read_bytes(), expected)
                if suffix == ".json.gz":
                    self.assertEqual(gzip.decompress(expected),
                                     (json.dumps(value, indent=2) + "\n").encode("utf-8"))

    def test_existing_files_are_not_overwritten(self):
        for module, hook, suffix, _ in self.cases:
            with self.subTest(script=Path(module.__file__).name, suffix=suffix), \
                    tempfile.TemporaryDirectory() as directory:
                destination = Path(directory).resolve() / ("receipt" + suffix)
                destination.write_bytes(SENTINEL)
                with self.assertRaises(FileExistsError):
                    self.invoke(module, hook, destination,
                                lambda *args, **kwargs: packet())
                self.assertEqual(destination.read_bytes(), SENTINEL)

    def test_compact_clis_still_refuse_nonfinite_json_before_creation(self):
        for module, hook, suffix, pretty in self.cases:
            if pretty:
                continue
            with self.subTest(script=Path(module.__file__).name), \
                    tempfile.TemporaryDirectory() as directory:
                destination = Path(directory).resolve() / ("receipt" + suffix)
                value = packet()
                value["fileIoFixture"]["values"].append(float("nan"))
                with self.assertRaises(ValueError):
                    self.invoke(module, hook, destination,
                                lambda *args, **kwargs: value)
                self.assertFalse(destination.exists())


class CrankOutputCreationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.crank = load_script("6dW6VYXp9HM-visible-crank-extract.py",
                                "historical_output_crank")

    def pin(self, destination):
        return self.crank.common.fresh.check_namespace(
            destination, historical_diagnostic=True, output=True)

    def make_support(self, root):
        declared = root / "receipt-source-pixel-support"
        pinned = self.pin(declared)
        self.crank.create_support_directory(pinned, declared_path=declared)
        return declared, pinned

    def codec_image(self):
        # A generic codec-only pixel, never substituted for a source frame.
        return self.crank.np.array([[[211, 137, 83]]], dtype="uint8")

    def test_receipt_and_measurements_preserve_exact_compact_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            declared_support, support = self.make_support(root)
            value = packet()
            for declared in (root / "receipt.json", declared_support / "measurements.json"):
                with self.subTest(name=declared.name):
                    self.crank.save(self.pin(declared), value, declared_path=declared)
                    self.assertEqual(declared.read_bytes(), text_bytes(
                        json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n"))
            self.assertTrue(support.is_dir())

    def test_receipt_and_measurements_refuse_leaf_symlinks_inserted_during_serialization(self):
        real_dumps = json.dumps
        for name in ("receipt.json", "measurements.json"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                declared_support, _ = self.make_support(root)
                declared = (root / name if name == "receipt.json" else
                            declared_support / name)
                pinned = self.pin(declared)
                sentinel = root / "sentinel.bin"
                sentinel.write_bytes(SENTINEL)

                def serialize(*args, **kwargs):
                    declared.symlink_to(sentinel)
                    return real_dumps(*args, **kwargs)

                # The hook controls serialization timing, not guards or writing.
                with patch.object(self.crank.json, "dumps", side_effect=serialize), \
                        self.assertRaises((ValueError, OSError)):
                    self.crank.save(pinned, packet(), declared_path=declared)
                self.assertTrue(declared.is_symlink())
                self.assertEqual(sentinel.read_bytes(), SENTINEL)

    def test_preview_preserves_actual_opencv_png_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            declared_support, _ = self.make_support(Path(directory).resolve())
            declared = declared_support / "track-contact.png"
            image = self.codec_image()
            encoded, expected = self.crank.cv2.imencode(".png", image)
            self.assertTrue(encoded)
            self.crank.save_preview(self.pin(declared), image, declared_path=declared)
            self.assertEqual(declared.read_bytes(), expected.tobytes())

    def test_preview_refuses_leaf_symlink_inserted_during_real_png_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            declared_support, _ = self.make_support(root)
            declared = declared_support / "track-contact.png"
            pinned = self.pin(declared)
            sentinel = root / "sentinel.bin"
            sentinel.write_bytes(SENTINEL)
            real_imencode = self.crank.cv2.imencode

            def encode(extension, image):
                result = real_imencode(extension, image)
                self.assertTrue(result[0])
                declared.symlink_to(sentinel)
                return result

            with patch.object(self.crank.cv2, "imencode", side_effect=encode), \
                    self.assertRaises((ValueError, OSError)):
                self.crank.save_preview(pinned, self.codec_image(), declared_path=declared)
            self.assertTrue(declared.is_symlink())
            self.assertEqual(sentinel.read_bytes(), SENTINEL)

    def test_support_creation_refuses_existing_directory_and_file(self):
        for directory_entry in (False, True):
            with self.subTest(directory=directory_entry), \
                    tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                declared = root / "receipt-source-pixel-support"
                pinned = self.pin(declared)
                sentinel = declared / "sentinel.bin" if directory_entry else declared
                if directory_entry:
                    declared.mkdir()
                sentinel.write_bytes(SENTINEL)
                with self.assertRaises(FileExistsError):
                    self.crank.create_support_directory(pinned, declared_path=declared)
                self.assertEqual(sentinel.read_bytes(), SENTINEL)

    def test_support_creation_refuses_existing_and_dangling_directory_aliases(self):
        for dangling in (False, True):
            with self.subTest(dangling=dangling), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                target = root / "alias-target"
                if not dangling:
                    target.mkdir()
                    (target / "sentinel.bin").write_bytes(SENTINEL)
                declared = root / "receipt-source-pixel-support"
                declared.symlink_to(target, target_is_directory=True)
                pinned = self.pin(declared)
                with self.assertRaises(FileExistsError):
                    self.crank.create_support_directory(pinned, declared_path=declared)
                self.assertTrue(declared.is_symlink())
                if dangling:
                    self.assertFalse(target.exists())
                else:
                    self.assertEqual((target / "sentinel.bin").read_bytes(), SENTINEL)

    def test_support_creation_rechecks_resolution_after_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            declared = root / "receipt-source-pixel-support"
            pinned = self.pin(declared)
            target = root / "alias-target"
            target.mkdir()
            (target / "sentinel.bin").write_bytes(SENTINEL)
            declared.symlink_to(target, target_is_directory=True)
            with self.assertRaises(ValueError):
                self.crank.create_support_directory(pinned, declared_path=declared)
            self.assertTrue(declared.is_symlink())
            self.assertEqual((target / "sentinel.bin").read_bytes(), SENTINEL)

    def test_support_mkdir_is_exclusive_if_alias_appears_after_revalidation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            declared = root / "receipt-source-pixel-support"
            pinned = self.pin(declared)
            target = root / "alias-target"
            target.mkdir()
            (target / "sentinel.bin").write_bytes(SENTINEL)
            real_mkdir = Path.mkdir

            def insert_before_mkdir(path, *args, **kwargs):
                if path == pinned:
                    declared.symlink_to(target, target_is_directory=True)
                return real_mkdir(path, *args, **kwargs)

            # Keep the real mkdir syscall; inject only its racing filesystem entry.
            with patch.object(Path, "mkdir", new=insert_before_mkdir), \
                    self.assertRaises(FileExistsError):
                self.crank.create_support_directory(pinned, declared_path=declared)
            self.assertTrue(declared.is_symlink())
            self.assertEqual((target / "sentinel.bin").read_bytes(), SENTINEL)

    def test_support_mkdir_refuses_racing_dangling_directory_alias_without_creating_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            declared = root / "receipt-source-pixel-support"
            pinned = self.pin(declared)
            target = root / "missing-alias-target"
            self.assertFalse(target.exists())
            real_mkdir = Path.mkdir
            inserted = False

            def insert_before_mkdir(path, *args, **kwargs):
                nonlocal inserted
                if path == pinned and not inserted:
                    declared.symlink_to(target, target_is_directory=True)
                    inserted = True
                return real_mkdir(path, *args, **kwargs)

            # Inject once, including if pathlib retries after a missing-parent error.
            # The real mkdir must refuse the dangling directory entry itself.
            with patch.object(Path, "mkdir", new=insert_before_mkdir), \
                    self.assertRaises(FileExistsError):
                self.crank.create_support_directory(pinned, declared_path=declared)
            self.assertTrue(inserted)
            self.assertTrue(declared.is_symlink())
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
