#!/usr/bin/env python3
"""Rebuild the exact unsigned A7 IV 6.02 v3e2-once FDAT from Sony BODYDATA.DAT."""
from __future__ import annotations

import argparse
import json
import os
import struct
import sys
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from repack_fdat import Refusal, build, digest_file, read_region, scan_members

RECIPE = Path(__file__).with_name("v3e2_ap_layout.json")
PART_PREFIX = "0700_part_image/dev/"
STOCK_AP_SHA = "b33408130538b6b34b3fe196d455bfce6f404a207a5567a0ab13e933024c8637"
STOCK_APP_SHA = "1e1b9202eaa69198f20df03dbfdab2f103b206cc4ebcd2e7bd817e6a710018a2"
TARGET_APP_SHA = "8f028645da512fcf7adb7eff22eb0add864f5399e6a198eb197186e4dda82574"
TARGET_AP_SHA = "76fbffb9c3b6a497261210eb4be98d5805bbf13f3b00347b334e99a58e055d66"
STOCK_CP_SHA = "62d16a76ac949e7f9ec5b9b1a46c7cdc65148b1a169b8d617c83c441d7806aee"
TARGET_SHA = "22e8bf6a7039f6aed375b8c0bdf6c284cf0c0f83ff9a72d089ff007ba82e7a5f"


def check_digest(label: str, actual: str, expected: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} SHA-256 mismatch: got {actual}, expected {expected}")


def extract_partitions(plain: Path, ap: Path, cp: Path) -> None:
    with plain.open("rb") as source:
        members = scan_members(source, *read_region(source, plain.stat().st_size))
        for name, output, expected in (("nflasha15", ap, STOCK_AP_SHA), ("nflasha8", cp, STOCK_CP_SHA)):
            offset, remaining = members[PART_PREFIX + name]
            source.seek(offset)
            digest = sha256()
            with output.open("xb") as target:
                while remaining:
                    chunk = source.read(min(remaining, 1024 * 1024))
                    if not chunk:
                        raise ValueError(f"short read for {name}")
                    digest.update(chunk)
                    target.write(chunk)
                    remaining -= len(chunk)
            check_digest(name, digest.hexdigest(), expected)


def read_bytes_at(stream, offset: int, size: int) -> bytes:
    stream.seek(offset)
    data = stream.read(size)
    if len(data) != size:
        raise ValueError(f"short read at AP offset {offset}")
    return data


def overlay(stream, offset: int, data) -> None:
    stream.seek(offset)
    stream.write(data)


def write_file_ranges(stream, mapping, data) -> None:
    with memoryview(data) as content:
        for logical, offset, size in mapping:
            overlay(stream, offset, content[logical:logical + size])


def write_archive_residue(stream, stock_app_tail: bytes) -> None:
    """Reproduce archival ext2 free-space bytes left by earlier synthetic tests."""
    block = 1024
    head = bytes.fromhex("41374d34444941470100004044494147")
    diag = head + bytes((i * 29 + 0x8a) % 256 for i in range(len(head), 16 * block - 32))
    diag += sha256(diag).digest()
    overlay(stream, 62208 * block, diag[:12 * block])
    overlay(stream, 62220 * block, struct.pack("<4I", 62221, 62222, 62223, 62224) + bytes(block - 16))
    overlay(stream, 62221 * block, diag[12 * block:])

    # The relocated stock app left one copied block in the free-space image.
    overlay(stream, 336191 * block, stock_app_tail)
    # A deleted synthetic 17-grid identity ELUT left this portion of its data.
    grid = range(17)
    nodes = b"".join(struct.pack("<fff", r / 16, g / 16, b / 16) for b in grid for g in grid for r in grid)
    elut = struct.pack(">I", len(nodes) + 0xd00) + b"ELUT" + bytes(37) + nodes + bytes(0xd00)
    overlay(stream, 336239 * block + 896, bytes(128))
    overlay(stream, 336240 * block, elut[48128:59392])


def assemble_ap(path: Path, luts: dict[str, bytes]) -> None:
    layout = json.loads(RECIPE.read_text(encoding="utf-8"))
    app = layout["app"]
    with path.open("r+b") as image:
        # Read all source runs first because the destination overlaps them.
        data = bytearray(app["size"])
        for logical, offset, size in app["stock_read"]:
            data[logical:logical + size] = read_bytes_at(image, offset, size)
        stock_app_tail = read_bytes_at(image, 347051008, 1024)
        check_digest("stock appFw.so", sha256(data).hexdigest(), STOCK_APP_SHA)
        for offset, expected, new_hex in app["edits"]:
            new = bytes.fromhex(new_hex)
            with memoryview(data)[offset:offset + len(new)] as old:
                check_digest(f"appFw.so preimage at 0x{offset:x}", sha256(old).hexdigest(), expected)
            data[offset:offset + len(new)] = new
        check_digest("v3e2 appFw.so", sha256(data).hexdigest(), TARGET_APP_SHA)
        write_file_ranges(image, app["write"], data)

        for name, spec in layout["luts"].items():
            data = luts[name]
            if len(data) != spec["size"]:
                raise ValueError(f"unexpected size of {name}")
            check_digest(name, sha256(data).hexdigest(), spec["sha256"])
            write_file_ranges(image, spec["write"], data)

        write_archive_residue(image, stock_app_tail)
        for block, changes in layout["metadata"]:
            for offset, new in changes:
                overlay(image, block * 1024 + offset, bytes.fromhex(new))
    check_digest("v3e2 AP partition", digest_file(path), TARGET_AP_SHA)


def rebuild(source: Path, output: Path, lut_zip: Path | None) -> None:
    from stock_dat import decode_stock
    from stock_luts import load_luts

    if os.path.lexists(output):
        raise ValueError(f"output already exists: {output}")
    with TemporaryDirectory(prefix=".v3e2-build-", dir=output.parent) as directory:
        work = Path(directory)
        plain, ap, cp, candidate = (work / name for name in ("official.fdat", "ap.img", "cp.img", "candidate.fdat"))
        print("[1/4] Checking and decoding Sony BODYDATA.DAT", flush=True)
        decode_stock(source, plain)
        print("[2/4] Extracting the stock AP and CP partitions and verifying the Sony S709 source", flush=True)
        extract_partitions(plain, ap, cp)
        luts = load_luts(lut_zip)
        print("[3/4] Reconstructing and checking the v3e2 AP partition", flush=True)
        assemble_ap(ap, luts)
        print("[4/4] Repacking and checking the complete FDAT", flush=True)
        digest = build(plain, ap, TARGET_AP_SHA, cp, STOCK_CP_SHA, candidate)
        check_digest("v3e2 FDAT", digest, TARGET_SHA)
        os.link(candidate, output)
    print(f"{TARGET_SHA}  {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bodydata", type=Path, help="exact Sony ILCE-7M4 version 6.02 BODYDATA.DAT")
    parser.add_argument("--output", type=Path, required=True, help="new .fdat file on a filesystem supporting hard links")
    parser.add_argument("--s709-zip", type=Path, help="use a local copy of Sony's pinned s709Cubes.zip instead of fetching it")
    args = parser.parse_args()
    try:
        rebuild(args.bodydata, args.output, args.s709_zip)
    except (Refusal, ValueError, OSError, ImportError) as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
