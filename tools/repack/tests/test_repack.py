#!/usr/bin/env python3
"""Regression tests for the offline FDAT repacker.

The cases run on a synthetic 12 KiB container, never on a real camera image:
they cover the offset arithmetic, the checksum-row rewrite, and each refusal.
"""
from __future__ import annotations

import errno
import io
import struct
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from zlib import crc32

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import repack_fdat  # noqa: E402
from repack_fdat import Refusal, build, main, read_region, scan_members  # noqa: E402

PREFIX = "0700_part_image/"
SUM = "0701_part_image_sum/part_image.sum"
AP = "dev/nflasha15"
CP = "dev/nflasha8"
AP_SIZE = 4096
CP_SIZE = 32768


def ext2_stub(payload: bytes = b"") -> bytes:
    image = bytearray(AP_SIZE)
    image[1080:1082] = b"\x53\xef"
    image[1088:1092] = struct.pack("<I", 2)
    image[1200:1200 + len(payload)] = payload
    return bytes(image)


def fat12_stub() -> bytes:
    image = bytearray(CP_SIZE)
    image[0:3] = b"\xeb\x3c\x90"
    struct.pack_into("<H", image, 11, 512)
    image[13] = 1
    struct.pack_into("<H", image, 14, 1)
    image[16] = 2
    struct.pack_into("<H", image, 17, 16)
    struct.pack_into("<H", image, 19, 64)
    image[21] = 0xF8
    struct.pack_into("<H", image, 22, 1)
    image[510:512] = b"\x55\xaa"
    return bytes(image)


def sum_table(ap: bytes, cp: bytes) -> bytes:
    rows = [
        "5,ffffffff,00000000,000001ed,00000000,000003e8,root,root,-1,-1,dev,\n",
        f"0,{crc32(ap):08x},{AP_SIZE:08x},000001a4,00000000,000003e8,root,root,-1,-1,{AP},\n",
        f"0,{crc32(cp):08x},{CP_SIZE:08x},000001a4,00000000,000003e8,root,root,-1,-1,{CP},\n",
        "0,61bfcf5a,0c8d9880,000001a4,00000000,000003e8,root,root,-1,-1,dev/nflasha5,\n",
    ]
    return "".join(rows).encode("ascii")


def tar_bytes(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size, info.mtime, info.mode = len(data), 0, 0o644
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def container(members: dict[str, bytes]) -> bytes:
    tar = tar_bytes(members)
    header = bytearray(512)
    header[:8] = b"UDTRFIRM"
    header[0x20:0x22] = b"\x00\x00"
    struct.pack_into("<III", header, 48, 512, len(tar), 0)
    struct.pack_into("<I", header, 8, crc32(bytes(header[12:])))
    return bytes(header) + tar


class RepackTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.ap, self.cp = ext2_stub(b"v3b"), fat12_stub()
        self.official = self.root / "official.fdat"
        self.official.write_bytes(container({
            f"{PREFIX}{AP}": self.ap,
            f"{PREFIX}{CP}": self.cp,
            SUM: sum_table(self.ap, self.cp),
        }))
        self.new_ap = ext2_stub(b"v3e2")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def pack_args(self, name: str = "out.fdat", **overrides) -> dict:
        covering = {AP: self.ap, CP: self.cp} | overrides.pop("partitions", {})
        for member, data in covering.items():
            target = self.root / ("ap.img" if member == AP else "cp.img")
            target.write_bytes(data)
        arguments = {
            "official": self.official,
            "ap": self.root / "ap.img",
            "ap_sha": _sha(self.root / "ap.img"),
            "cp": self.root / "cp.img",
            "cp_sha": _sha(self.root / "cp.img"),
            "output": self.root / name,
            "official_size": self.official.stat().st_size,
            "official_sha": _sha_bytes(self.official.read_bytes()),
            "members": ((AP, AP_SIZE), (CP, CP_SIZE)),
            "prefix": PREFIX,
            "sum_member": SUM,
        }
        arguments.update(overrides)
        return arguments

    def pack(self, name: str = "out.fdat", **overrides) -> Path:
        arguments = self.pack_args(name, **overrides)
        build(**arguments)
        return arguments["output"]

    def members(self, path: Path) -> dict[str, bytes]:
        with path.open("rb") as stream:
            index = scan_members(stream, *read_region(stream, path.stat().st_size))
            return {name: (stream.seek(offset), stream.read(size))[1] for name, (offset, size) in index.items()}

    def test_replaces_both_members_and_checksum_rows(self) -> None:
        output = self.pack(partitions={AP: self.new_ap})
        before, after = self.members(self.official), self.members(output)
        self.assertEqual(after[f"{PREFIX}{AP}"], self.new_ap)
        self.assertEqual(after[f"{PREFIX}{CP}"], self.cp)
        self.assertEqual(len(after[SUM]), len(before[SUM]))
        rows = after[SUM].decode("ascii").splitlines()
        self.assertEqual([row.split(",")[1] for row in rows],
                         ["ffffffff", f"{crc32(self.new_ap):08x}", f"{crc32(self.cp):08x}", "61bfcf5a"])
        self.assertNotEqual(_sha_bytes(before[f"{PREFIX}{AP}"]), _sha_bytes(after[f"{PREFIX}{AP}"]))
        self.assertEqual(output.stat().st_size, self.official.stat().st_size)

    def test_identical_partitions_change_only_the_rewritten_rows(self) -> None:
        output = self.pack()
        self.assertEqual(output.read_bytes(), self.official.read_bytes())

    def test_extract_round_trip_preserves_member_bytes(self) -> None:
        members = self.members(self.official)
        self.assertEqual(members[f"{PREFIX}{AP}"], self.ap)
        self.assertEqual(members[f"{PREFIX}{CP}"], self.cp)

    def test_refuses_existing_output(self) -> None:
        (self.root / "out.fdat").write_bytes(b"x")
        with self.assertRaises(Refusal) as caught:
            self.pack()
        self.assertEqual(caught.exception.code, "EXISTS")
        self.assertEqual((self.root / "out.fdat").read_bytes(), b"x")

    def test_refuses_wrong_partition_size(self) -> None:
        with self.assertRaises(Refusal) as caught:
            self.pack(partitions={AP: ext2_stub(b"v3e2") + b"\0"})
        self.assertEqual(caught.exception.code, "SIZE")
        self.assertFalse((self.root / "out.fdat").exists())

    def test_refuses_sha_mismatch(self) -> None:
        with self.assertRaises(Refusal) as caught:
            self.pack(ap_sha="0" * 64)
        self.assertEqual(caught.exception.code, "HASH")
        self.assertFalse((self.root / "out.fdat").exists())

    def test_refuses_non_ext2_ap(self) -> None:
        broken = bytearray(self.new_ap)
        broken[1080:1082] = b"\x00\x00"
        with self.assertRaises(Refusal) as caught:
            self.pack(partitions={AP: bytes(broken)})
        self.assertEqual(caught.exception.code, "EXT2")
        self.assertFalse((self.root / "out.fdat").exists())

    def test_refuses_ext3_or_ext4_ap(self) -> None:
        broken = bytearray(self.new_ap)
        struct.pack_into("<I", broken, 1120, 0x40)
        with self.assertRaises(Refusal) as caught:
            self.pack(partitions={AP: bytes(broken)})
        self.assertEqual(caught.exception.code, "EXT2")

    def test_refuses_non_fat12_cp(self) -> None:
        broken = bytearray(fat12_stub())
        struct.pack_into("<H", broken, 19, 0)
        struct.pack_into("<I", broken, 32, 65535 * 512)
        with self.assertRaises(Refusal) as caught:
            self.pack(partitions={CP: bytes(broken)})
        self.assertEqual(caught.exception.code, "FAT")

    def test_refuses_mismatched_fat_copies(self) -> None:
        broken = bytearray(fat12_stub())
        broken[512 + 4] = 0xFF
        with self.assertRaises(Refusal) as caught:
            self.pack(partitions={CP: bytes(broken)})
        self.assertEqual(caught.exception.code, "FAT")

    def test_refuses_tampered_header_or_checksum_row(self) -> None:
        corrupted = bytearray(self.official.read_bytes())
        corrupted[0x30] ^= 0xFF
        self.official.write_bytes(bytes(corrupted))
        with self.assertRaises(Refusal) as caught:
            self.pack()
        self.assertEqual(caught.exception.code, "HEADER")

        self.official = self.root / "official2.fdat"
        self.official.write_bytes(container({
            f"{PREFIX}{AP}": self.ap,
            f"{PREFIX}{CP}": self.cp,
            SUM: sum_table(self.ap, self.cp).replace(f"{crc32(self.ap):08x}".encode(), b"deadbeef"),
        }))
        with self.assertRaises(Refusal) as caught:
            self.pack(name="out2.fdat")
        self.assertEqual(caught.exception.code, "MANIFEST")

    def test_concurrent_creator_keeps_its_output(self) -> None:
        output = self.root / "out.fdat"
        original_link = repack_fdat.os.link

        def racing_link(source, destination, *arguments, **keywords):
            Path(destination).write_bytes(b"peer")
            return original_link(source, destination, *arguments, **keywords)

        with mock.patch.object(repack_fdat.os, "link", side_effect=racing_link):
            with self.assertRaises(Refusal) as caught:
                self.pack()
        self.assertEqual(caught.exception.code, "EXISTS")
        self.assertEqual(output.read_bytes(), b"peer")
        self.assertEqual(list(self.root.glob(".repack-*")), [])

    def test_linkless_filesystem_is_refused_without_residue(self) -> None:
        def unsupported(*arguments, **keywords):
            raise OSError(errno.EPERM, "Operation not permitted")

        with mock.patch.object(repack_fdat.os, "link", side_effect=unsupported):
            with self.assertRaises(Refusal) as caught:
                self.pack()
        self.assertEqual(caught.exception.code, "OUTPUT")
        self.assertFalse((self.root / "out.fdat").exists())
        self.assertEqual(list(self.root.glob(".repack-*")), [])

    def test_input_rewrite_after_pin_cannot_change_output(self) -> None:
        ap_image, ap_path = self.new_ap, self.root / "ap.img"
        real_stage = repack_fdat.stage_input

        def stage_then_mutate(path, directory, expected, scratch):
            staged = real_stage(path, directory, expected, scratch)
            if path == ap_path:
                path.write_bytes(ext2_stub(b"evil"))
            return staged

        arguments = self.pack_args(partitions={AP: ap_image})
        with mock.patch.object(repack_fdat, "stage_input", side_effect=stage_then_mutate):
            digest = build(**arguments)
        written = self.members(arguments["output"])
        self.assertEqual(written[f"{PREFIX}{AP}"], ap_image)
        self.assertEqual(written[SUM].decode("ascii").splitlines()[1].split(",")[1],
                         f"{crc32(ap_image):08x}")
        self.assertEqual(digest, _sha(arguments["output"]))
        self.assertEqual(list(self.root.glob(".repack-*")), [])

    def test_refusal_after_staging_leaves_no_partial_output(self) -> None:
        broken = bytearray(self.new_ap)
        broken[1080:1082] = b"\x00\x00"
        with self.assertRaises(Refusal) as caught:
            self.pack(partitions={AP: bytes(broken)})
        self.assertEqual(caught.exception.code, "EXT2")
        self.assertFalse((self.root / "out.fdat").exists())
        self.assertEqual(list(self.root.glob(".repack-*")), [])

    def test_cli_reports_missing_files_as_input_refusals(self) -> None:
        missing = self.root / "absent.fdat"
        errors = io.StringIO()
        with mock.patch.object(sys, "stderr", errors), mock.patch.object(sys, "stdout", io.StringIO()):
            listing = main(["list", str(missing)])
            packing = main(["build", str(self.official), "--ap", str(missing), "--ap-sha256", "0" * 64,
                            "--cp", str(self.root / "cp.img"), "--cp-sha256", "0" * 64,
                            "--output", str(self.root / "cli.fdat")])
        self.assertEqual((listing, packing), (1, 1))
        self.assertEqual(errors.getvalue().count("REFUSED INPUT"), 2)
        self.assertFalse((self.root / "cli.fdat").exists())

    def test_cli_extract_is_atomic(self) -> None:
        target = self.root / "member.bin"
        with mock.patch.object(sys, "stdout", io.StringIO()):
            self.assertEqual(main(["extract", str(self.official), f"{PREFIX}{AP}", str(target)]), 0)
        self.assertEqual(target.read_bytes(), self.ap)
        self.assertEqual(list(self.root.glob(".repack-*")), [])

        errors, absent = io.StringIO(), self.root / "absent.bin"
        with mock.patch.object(sys, "stderr", errors), mock.patch.object(sys, "stdout", io.StringIO()):
            self.assertEqual(main(["extract", str(self.official), "no/such", str(absent)]), 1)
        self.assertFalse(absent.exists())
        self.assertEqual(list(self.root.glob(".repack-*")), [])


def _sha_bytes(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


def _sha(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


if __name__ == "__main__":
    unittest.main(verbosity=2)
