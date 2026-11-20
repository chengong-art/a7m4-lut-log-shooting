#!/usr/bin/env python3
"""Offline, same-size plaintext FDAT member repacker.

Research tooling only: not a builder for arbitrary firmware, not a signer, and
not an installer. It replaces two partition members of the exact official A7 IV
6.02 plaintext FDAT with caller-supplied images of identical size, updates the
matching checksum rows, and refuses everything else.
"""
from __future__ import annotations

import argparse
import hashlib
import math
import os
import stat
import struct
import sys
import tempfile
from pathlib import Path
from zlib import crc32

HEADER_SIZE = 512
BLOCK = 1024 * 1024
MAGIC = b"UDTRFIRM"
PREFIX = "0700_part_image/"
SUM_MEMBER = "0701_part_image_sum/part_image.sum"
OFFICIAL_SIZE = 754_521_088
OFFICIAL_SHA256 = "4fd810b8d20ea239e0df01aded90687baef1ca2c8df208a7f58c4989f85799c3"
PARTITION_MEMBERS = (("dev/nflasha15", 378_580_992), ("dev/nflasha8", 22_777_856))


class Refusal(Exception):
    """A deliberate gate refusal; the caller turns it into a non-zero exit."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def refuse(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise Refusal(code, message)


def digest_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(BLOCK), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def require_regular(path: Path) -> None:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        raise Refusal("INPUT", f"missing input file: {path}") from None
    except OSError as error:
        raise Refusal("INPUT", f"cannot stat {path}: {error}") from None
    refuse(stat.S_ISREG(info.st_mode), "INPUT", f"expected a regular file: {path}")
    refuse(not path.is_symlink(), "INPUT", f"refusing a symlink: {path}")


def private_scratch(directory: Path) -> tuple[int, Path]:
    """Create an exclusive 0600 scratch file next to the destination."""
    try:
        descriptor, name = tempfile.mkstemp(dir=directory, prefix=".repack-", suffix=".part")
    except OSError as error:
        raise Refusal("OUTPUT", f"cannot create a scratch file in {directory}: {error}") from None
    return descriptor, Path(name)


def stage_input(path: Path, directory: Path, expected: int, scratch: list[Path]) -> tuple[Path, str, int]:
    """Copy a mutable input once and measure the copy, not the caller's file.

    Re-reading a file the caller may rewrite mid-run would let the accepted
    SHA256 and the copied bytes disagree, so every check and every write below
    uses this private snapshot instead.
    """
    descriptor, copy = private_scratch(directory)
    scratch.append(copy)
    digest = hashlib.sha256()
    checksum, size = 0, 0
    with os.fdopen(descriptor, "wb") as target, path.open("rb") as source:
        while chunk := source.read(BLOCK):
            size += len(chunk)
            refuse(size <= expected, "SIZE", f"expected {expected} bytes in {path}")
            target.write(chunk)
            digest.update(chunk)
            checksum = crc32(chunk, checksum)
        target.flush()
        os.fsync(target.fileno())
    refuse(size == expected, "SIZE", f"expected {expected} bytes in {path}")
    return copy, digest.hexdigest(), checksum


def publish(scratch: Path, output: Path) -> None:
    """Give the finished scratch inode the requested name, only if it is free.

    `os.link` fails rather than replacing, so a concurrent creator's file is
    never overwritten; the caller unlinks only its own scratch name afterwards.
    Filesystems without hard links are refused instead of falling back to a
    rename, which could not promise that exclusivity.
    """
    refuse(not output.exists() and not output.is_symlink(), "EXISTS", "output already exists")
    try:
        os.link(scratch, output)
    except FileExistsError:
        raise Refusal("EXISTS", "output already exists") from None
    except OSError as error:
        raise Refusal("OUTPUT", f"cannot create {output}: {error}") from None


def sync_directory(directory: Path) -> None:
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def read_region(stream, size: int) -> tuple[int, int]:
    """Validate the 512-byte plaintext header and return the tar region."""
    refuse(size >= HEADER_SIZE, "HEADER", "truncated container")
    stream.seek(0)
    header = stream.read(HEADER_SIZE)
    refuse(len(header) == HEADER_SIZE, "HEADER", "truncated header")
    refuse(header[:8] == MAGIC, "HEADER", "not a UDTRFIRM plaintext container")
    refuse(struct.unpack_from("<I", header, 8)[0] == crc32(header[12:]), "HEADER", "header CRC mismatch")
    refuse(all((v & 15) <= 9 and (v >> 4) <= 9 for v in header[0x20:0x22]), "HEADER", "invalid BCD version")
    offset, length, number = struct.unpack_from("<III", header, 48)
    refuse(HEADER_SIZE <= offset <= offset + length <= size, "HEADER", "firmware region outside file")
    refuse(number <= 28, "HEADER", "unexpected filesystem count")
    return offset, length


def parse_octal(field: bytes, label: str) -> int:
    text = field.split(b"\0", 1)[0].strip()
    refuse(not text or set(text) <= set(b"01234567"), "TAR", f"invalid octal {label}")
    return int(text or b"0", 8)


def tar_checksum_ok(header: bytes) -> bool:
    stored = parse_octal(header[148:156], "checksum")
    computed = sum(header[:148]) + 32 * 8 + sum(header[156:])
    return stored == computed


def scan_members(stream, offset: int, length: int) -> dict[str, tuple[int, int]]:
    """Return {member name: (absolute data offset, size)} for regular files."""
    members: dict[str, tuple[int, int]] = {}
    position, end = offset, offset + length
    while position + HEADER_SIZE <= end:
        stream.seek(position)
        header = stream.read(HEADER_SIZE)
        if header == b"\0" * HEADER_SIZE:
            break
        refuse(tar_checksum_ok(header), "TAR", "tar header checksum mismatch")
        name = header[:100].split(b"\0", 1)[0].decode("ascii", "strict")
        prefix = header[345:500].split(b"\0", 1)[0].decode("ascii", "strict")
        name = f"{prefix}/{name}" if prefix else name
        name = name.removeprefix("./")
        size = parse_octal(header[124:136], "size")
        data = position + HEADER_SIZE
        refuse(name and not name.startswith("/") and ".." not in Path(name).parts, "TAR", "unsafe member name")
        refuse(name not in members, "TAR", f"duplicate member: {name}")
        if header[156:157] in (b"0", b"\0"):
            refuse(data + size <= end, "TAR", f"member outside firmware region: {name}")
            members[name] = (data, size)
        position = data + (size + HEADER_SIZE - 1) // HEADER_SIZE * HEADER_SIZE
    return members


def check_ext2(head: bytes) -> None:
    refuse(len(head) >= 2048, "EXT2", "truncated AP image")
    refuse(head[1080:1082] == b"\x53\xef", "EXT2", "missing ext2 superblock magic")
    refuse(struct.unpack_from("<I", head, 1120)[0] & ~0x02 == 0, "EXT2", "unsupported ext2 incompatible features")


def check_fat12(head: bytes, path: Path, size: int) -> None:
    refuse(len(head) >= 512 and head[510:512] == b"\x55\xaa", "FAT", "missing FAT boot signature")
    bps = struct.unpack_from("<H", head, 11)[0]
    spc = head[13]
    reserved = struct.unpack_from("<H", head, 14)[0]
    nfat = head[16]
    roots = struct.unpack_from("<H", head, 17)[0]
    sectors = struct.unpack_from("<H", head, 19)[0] or struct.unpack_from("<I", head, 32)[0]
    spf = struct.unpack_from("<H", head, 22)[0]
    refuse(bps in (512, 1024, 2048, 4096) and spc in (1, 2, 4, 8, 16, 32, 64, 128) and nfat in (1, 2)
           and spf and reserved and roots, "FAT", "unsupported FAT geometry")
    fat_start, fat_size = reserved * bps, spf * bps
    data_start = fat_start + nfat * fat_size + math.ceil(roots * 32 / bps) * bps
    total = sectors * bps
    refuse(data_start < total <= size, "FAT", "FAT geometry outside partition")
    refuse((total - data_start) // (bps * spc) < 4085, "FAT", "expected a FAT12 cluster count")
    with path.open("rb") as stream:
        stream.seek(fat_start)
        first = stream.read(fat_size)
        for index in range(1, nfat):
            stream.seek(fat_start + index * fat_size)
            refuse(stream.read(fat_size) == first, "FAT", "FAT copies disagree")


def update_sum_rows(content: bytes, changes: dict[str, tuple[int, int, int]]) -> bytes:
    """Rewrite fields[1] (CRC32) for the named partitions; keep every length."""
    lines = content.decode("ascii").splitlines(keepends=True)
    matched: set[str] = set()
    for index, line in enumerate(lines):
        fields = line.split(",")
        if len(fields) <= 10 or fields[10] not in changes:
            continue
        name = fields[10]
        old_crc, size, new_crc = changes[name]
        refuse(name not in matched and len(fields[1]) == 8 and int(fields[1], 16) == old_crc
               and int(fields[2], 16) == size, "MANIFEST", f"unexpected checksum row for {name}")
        fields[1] = f"{new_crc:08x}"
        lines[index] = ",".join(fields)
        matched.add(name)
    refuse(matched == set(changes), "MANIFEST", "missing checksum row")
    result = "".join(lines).encode("ascii")
    refuse(len(result) == len(content), "MANIFEST", "checksum table resized")
    return result


def copy_region(source: Path, target, offset: int, size: int) -> None:
    """Overwrite [offset, offset+size) of the open target with a pinned file."""
    with source.open("rb") as stream:
        written = 0
        while written < size:
            chunk = stream.read(min(BLOCK, size - written))
            refuse(bool(chunk), "SIZE", f"input shrank while reading: {source}")
            target.seek(offset + written)
            target.write(chunk)
            written += len(chunk)
        refuse(not stream.read(1), "SIZE", f"input grew while reading: {source}")


def read_at(stream, offset: int, size: int) -> bytes:
    stream.seek(offset)
    data = stream.read(size)
    refuse(len(data) == size, "SIZE", "short read")
    return data


def write_at(stream, offset: int, payload: bytes) -> None:
    stream.seek(offset)
    stream.write(payload)


def crc_region(stream, offset: int, size: int) -> int:
    """CRC32 of one container region, in bounded chunks instead of one read."""
    stream.seek(offset)
    value, remaining = 0, size
    while remaining:
        chunk = stream.read(min(BLOCK, remaining))
        refuse(bool(chunk), "SIZE", "container shrank while reading")
        value = crc32(chunk, value)
        remaining -= len(chunk)
    return value


def build(official: Path, ap: Path, ap_sha: str, cp: Path, cp_sha: str, output: Path, *,
          official_size: int = OFFICIAL_SIZE, official_sha: str = OFFICIAL_SHA256,
          members: tuple[tuple[str, int], ...] = PARTITION_MEMBERS,
          sum_member: str = SUM_MEMBER, prefix: str = PREFIX) -> str:
    for path in (official, ap, cp):
        require_regular(path)
    refuse(not output.exists() and not output.is_symlink(), "EXISTS", "output already exists")
    refuse(output.parent.is_dir(), "EXISTS", "output directory does not exist")
    refuse(official.stat().st_size == official_size, "SIZE", f"expected the {official_size}-byte official FDAT")
    refuse(digest_file(official) == official_sha, "BASELINE", "official FDAT identity mismatch")

    scratch: list[Path] = []
    try:
        with official.open("rb") as source:
            region = read_region(source, official_size)
            index = scan_members(source, *region)
            refuse(sum_member in index, "TAR", "missing checksum member")
            wanted = {f"{prefix}{name}": size for name, size in members}
            for name, size in wanted.items():
                refuse(name in index and index[name][1] == size, "TAR", f"unexpected member geometry: {name}")

            staged: dict[str, tuple[Path, str, int]] = {}
            for name, path, pin in (("dev/nflasha15", ap, ap_sha), ("dev/nflasha8", cp, cp_sha)):
                copy, digest, checksum = stage_input(path, output.parent, wanted[f"{prefix}{name}"], scratch)
                refuse(pin.lower() == digest, "HASH", f"supplied SHA256 mismatch for {name}")
                staged[name] = (copy, digest, checksum)

            ap_copy = staged["dev/nflasha15"][0]
            cp_copy, _, _ = staged["dev/nflasha8"]
            with ap_copy.open("rb") as stream:
                check_ext2(stream.read(2048))
            with cp_copy.open("rb") as stream:
                check_fat12(stream.read(512), cp_copy, wanted[f"{prefix}dev/nflasha8"])

            sums: dict[str, tuple[int, int, int]] = {}
            for name in ("dev/nflasha15", "dev/nflasha8"):
                data_offset, size = index[f"{prefix}{name}"]
                sums[name] = (crc_region(source, data_offset, size), size, staged[name][2])

            descriptor, scratch_output = private_scratch(output.parent)
            scratch.append(scratch_output)
            with os.fdopen(descriptor, "w+b") as target:
                hasher = hashlib.sha256()
                source.seek(0)
                remaining = official_size
                while remaining:
                    chunk = source.read(min(BLOCK, remaining))
                    refuse(bool(chunk), "SIZE", "official FDAT shrank while reading")
                    target.write(chunk)
                    hasher.update(chunk)
                    remaining -= len(chunk)
                refuse(hasher.hexdigest() == official_sha, "BASELINE", "official FDAT changed during copy")
                for name in ("dev/nflasha15", "dev/nflasha8"):
                    copy_region(staged[name][0], target, *index[f"{prefix}{name}"])
                sum_offset, sum_size = index[sum_member]
                write_at(target, sum_offset, update_sum_rows(read_at(target, sum_offset, sum_size), sums))
                target.flush()
                os.fsync(target.fileno())
            result = digest_file(scratch_output)
            publish(scratch_output, output)
            sync_directory(output.parent)
    finally:
        for path in scratch:
            path.unlink(missing_ok=True)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    listing = commands.add_parser("list", help="print members of a plaintext FDAT")
    listing.add_argument("fdat", type=Path)

    extract = commands.add_parser("extract", help="stream one member out of a plaintext FDAT")
    extract.add_argument("fdat", type=Path)
    extract.add_argument("member")
    extract.add_argument("output", type=Path)

    pack = commands.add_parser("build", help="replace both partition members and their checksum rows")
    pack.add_argument("official", type=Path, help="official plaintext A7 IV 6.02 FDAT; never modified")
    pack.add_argument("--ap", type=Path, required=True, help="AP ext2 image for dev/nflasha15")
    pack.add_argument("--ap-sha256", required=True, help="64 hex digits pinning the AP image")
    pack.add_argument("--cp", type=Path, required=True, help="CP FAT12 image for dev/nflasha8")
    pack.add_argument("--cp-sha256", required=True, help="64 hex digits pinning the CP image")
    pack.add_argument("--output", type=Path, required=True, help="new FDAT path; must not exist")

    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            require_regular(args.fdat)
            with args.fdat.open("rb") as stream:
                index = scan_members(stream, *read_region(stream, args.fdat.stat().st_size))
            for name, (offset, size) in sorted(index.items()):
                print(f"{size:>12}  {offset:>12}  {name}")
            return 0
        if args.command == "extract":
            require_regular(args.fdat)
            refuse(args.output.parent.is_dir(), "EXISTS", "output directory does not exist")
            refuse(not args.output.exists() and not args.output.is_symlink(), "EXISTS", "output already exists")
            descriptor, scratch_output = private_scratch(args.output.parent)
            try:
                with args.fdat.open("rb") as stream:
                    index = scan_members(stream, *read_region(stream, args.fdat.stat().st_size))
                    refuse(args.member in index, "TAR", f"no such member: {args.member}")
                    offset, size = index[args.member]
                    hasher = hashlib.sha256()
                    with os.fdopen(descriptor, "wb") as target:
                        stream.seek(offset)
                        remaining = size
                        while remaining:
                            chunk = stream.read(min(BLOCK, remaining))
                            refuse(bool(chunk), "SIZE", "short read")
                            target.write(chunk)
                            hasher.update(chunk)
                            remaining -= len(chunk)
                        target.flush()
                        os.fsync(target.fileno())
                publish(scratch_output, args.output)
                sync_directory(args.output.parent)
            finally:
                scratch_output.unlink(missing_ok=True)
            print(f"{hasher.hexdigest()}  {args.member}  {args.output}")
            return 0
        print(f"{build(args.official, args.ap, args.ap_sha256, args.cp, args.cp_sha256, args.output)}  {args.output}")
        return 0
    except Refusal as error:
        print(f"REFUSED {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
