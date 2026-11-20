#!/usr/bin/env python3
"""Decode the official Sony ILCE-7M4 6.02 BODYDATA.DAT into its plaintext FDAT.

The published 6.02 update is a UFU stream with an AES-encrypted FDAT chunk.
This module performs the exact, byte-pinned decode:

    official container  ad6df47a0a93a46336b9920a0d8891d0c766f8c96fa68ebda8685f6c21621188
                        757,480,856 bytes
    plaintext FDAT      4fd810b8d20ea239e0df01aded90687baef1ca2c8df208a7f58c4989f85799c3
                        754,521,088 bytes

It reads the input only, never signs, never repacks and never contacts a camera.
The destination is published atomically, and only after every gate (UFU framing,
DEND checksum, both SHA256 pins and the plaintext header) passes.

Decode logic is trimmed from Erlla/sony-a7m4-custom-firmware at commit
0332a1fa94175f17ef8b9287fa42317c95648791, files a7m4/firmware.py and
a7m4/offline.py, which is MIT licensed; the upstream grant is reproduced
verbatim in LICENSE.erlla-a7m4-custom-firmware next to this file.

Dependencies: cryptography (AES-ECB/CBC decryption) and NumPy (batched block
validation).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
from pathlib import Path
from zlib import crc32

from repack_fdat import Refusal, private_scratch, publish, refuse, require_regular, sync_directory


OFFICIAL_SHA256 = "ad6df47a0a93a46336b9920a0d8891d0c766f8c96fa68ebda8685f6c21621188"
OFFICIAL_SIZE = 757_480_856
PLAINTEXT_SHA256 = "4fd810b8d20ea239e0df01aded90687baef1ca2c8df208a7f58c4989f85799c3"
PLAINTEXT_SIZE = 754_521_088
HEADER_SIZE = 512
SIGNATURE_SIZE = 256
BLOCK = 4 << 20
GROUP_BLOCKS = 4096
UFU_MAGIC = b"\x89UFU\r\n\x1a\n"
# Publicly researched CXD90057 container-format constants, not signing keys.
KEY_HEADER = bytes.fromhex("e3b0c44298fc1c149afbf4c8996fb924")
KEY_K8 = bytes.fromhex("434589432d319010f1132727353286ce4d7ede8b9c4f7217a0e0226e0f0edc69")

def exact(stream, size: int) -> bytes:
    data = stream.read(size)
    refuse(len(data) == size, "TRUNCATED", "unexpected end of file")
    return data

def contexts(iv: bytes):
    """AES-ECB for the first 512 B of the FDAT, AES-CBC for the rest."""
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ImportError:
        raise Refusal("DEPENDENCY", "cryptography is required for the AES container") from None
    pairs = (
        Cipher(algorithms.AES(KEY_HEADER), modes.ECB()),
        Cipher(algorithms.AES(KEY_K8), modes.CBC(iv)),
    )
    return [cipher.decryptor() for cipher in pairs]

def layout(stream, total: int) -> tuple[int, int, int]:
    """Bounded UFU chunk parser returning (FDAT start, signature, DEND start)."""
    stream.seek(0)
    refuse(exact(stream, 8) == UFU_MAGIC, "UFU", "invalid UFU magic")
    chunks: list[tuple[bytes, int, int]] = []
    position = 8
    while position < total:
        stream.seek(position)
        header = stream.read(8)
        refuse(len(header) == 8, "UFU", "truncated chunk header")
        size, tag = struct.unpack(">I4s", header)
        refuse(position + 8 + size <= total, "UFU", "chunk exceeds file")
        chunks.append((tag, position + 8, size))
        position += 8 + size
    refuse(position == total, "UFU", "chunk stream does not end at the file boundary")
    refuse(len(chunks) >= 2 and chunks[-1][0] == b"DEND" and chunks[-1][2] == 4,
           "UFU", "expected a final DEND checksum")
    fdat = [row for row in chunks if row[0] == b"FDAT"]
    refuse(len(fdat) == 1 and chunks[-2] == fdat[0]
           and fdat[0][2] >= HEADER_SIZE + 16 + SIGNATURE_SIZE,
           "UFU", "expected exactly one FDAT immediately before DEND")
    refuse(sum(1 for row in chunks if row[0] == b"DEND") == 1, "UFU", "duplicate DEND")
    _, start, size = fdat[0]
    dend = chunks[-1][1] - 8
    refuse(dend == total - 12, "UFU", "unexpected DEND placement")
    return start, start + size - SIGNATURE_SIZE, dend

def block_payload(plain: bytes, base: int, number: int, count: int, np) -> bytes:
    """Validate one batch of 1024-byte blocks and return their payload bytes."""
    array = np.frombuffer(plain, dtype=np.uint8).reshape(number, 1024)
    words = array.view("<u2").reshape(number, 512)
    flags = words[:, 1]
    sizes = flags & 0x7FFF
    full = number - 1 if base + number == count else number
    refuse(bool(np.all(sizes[:full] == 1020) and np.all(flags[:full] < 0x8000)),
           "UFU", "nonfinal block layout mismatch")
    if full != number:
        refuse(int(flags[-1]) & 0x8000 != 0 and 0 < int(sizes[-1]) <= 1020,
               "UFU", "invalid final block")
    refuse(bool(np.all((words[:, 1:].sum(axis=1, dtype=np.uint64) & 0xFFFF) == words[:, 0])),
           "UFU", "block checksum mismatch")
    payload = array[:full, 4:].tobytes()
    if full != number:
        payload += array[-1, 4:4 + int(sizes[-1])].tobytes()
    return payload

def verify_plain_header(header: bytes, size: int) -> tuple[int, int]:
    refuse(len(header) == HEADER_SIZE and header[:8] == b"UDTRFIRM",
           "HEADER", "invalid UDTRFIRM header")
    refuse(struct.unpack_from("<I", header, 8)[0] == crc32(header[12:]),
           "HEADER", "header CRC mismatch")
    refuse(all((value & 15) <= 9 and (value >> 4) <= 9 for value in header[0x20:0x22]),
           "HEADER", "invalid BCD version")
    offset, length, number = struct.unpack_from("<III", header, 48)
    refuse(HEADER_SIZE <= offset <= offset + length <= size, "HEADER", "firmware region outside file")
    refuse(number <= 28, "HEADER", "unexpected filesystem count")
    for index in range(number):
        _, member_offset, member_size, _ = struct.unpack_from("<4sIII", header, 64 + 16 * index)
        refuse(member_offset + member_size <= size, "HEADER", "filesystem outside plaintext")
    return offset, length

def _decode(source: Path, destination: Path) -> dict:
    require_regular(source)
    refuse(not destination.exists() and not destination.is_symlink(),
           "EXISTS", "output already exists")
    refuse(destination.parent.is_dir(), "OUTPUT", f"output directory does not exist: {destination.parent}")
    total = source.stat().st_size
    refuse(total == OFFICIAL_SIZE, "SIZE",
           f"expected the {OFFICIAL_SIZE}-byte official container, found {total} bytes")

    try:
        import numpy as np
    except ImportError:
        raise Refusal("DEPENDENCY", "NumPy is required to validate FDAT blocks") from None

    with source.open("rb") as stream:
        start, signature, dend = layout(stream, total)
        encrypted = signature - start - 16
        refuse(encrypted > 0 and encrypted % 1024 == 0, "UFU", "invalid FDAT block length")
        count = encrypted // 1024
        stream.seek(dend + 8)
        stored_crc = struct.unpack(">I", exact(stream, 4))[0]
        stream.seek(signature - 16)
        ecb, cbc = contexts(exact(stream, 16))

        scratch = None
        try:
            descriptor, scratch = private_scratch(destination.parent)
            source_hash, plain_hash = hashlib.sha256(), hashlib.sha256()
            checksum, plain_size, header = 0, 0, bytearray()
            with os.fdopen(descriptor, "wb") as target:
                stream.seek(0)
                remaining = start
                while remaining:
                    data = exact(stream, min(BLOCK, remaining))
                    source_hash.update(data)
                    checksum = crc32(data, checksum)
                    remaining -= len(data)
                for base in range(0, count, GROUP_BLOCKS):
                    number = min(GROUP_BLOCKS, count - base)
                    data = exact(stream, number * 1024)
                    source_hash.update(data)
                    checksum = crc32(data, checksum)
                    plain = ecb.update(data[:512]) + cbc.update(data[512:]) if base == 0 else cbc.update(data)
                    payload = block_payload(plain, base, number, count, np)
                    if len(header) < HEADER_SIZE:
                        header.extend(payload[:HEADER_SIZE - len(header)])
                    plain_hash.update(payload)
                    plain_size += len(payload)
                    target.write(payload)
                remaining = dend - (signature - 16)
                refuse(remaining >= 0, "UFU", "DEND precedes the FDAT signature")
                while remaining:
                    data = exact(stream, min(BLOCK, remaining))
                    source_hash.update(data)
                    checksum = crc32(data, checksum)
                    remaining -= len(data)
                remaining = total - dend
                while remaining:
                    data = exact(stream, min(BLOCK, remaining))
                    source_hash.update(data)
                    remaining -= len(data)
                target.flush()
                os.fsync(target.fileno())
            refuse(ecb.finalize() == b"" and cbc.finalize() == b"", "UFU", "unexpected cipher tail")
            refuse(checksum == stored_crc, "UFU", "DEND CRC mismatch")
            refuse(source_hash.hexdigest() == OFFICIAL_SHA256, "BASELINE",
                   "only the exact official A7M4 6.02 container is supported")
            refuse(plain_size == PLAINTEXT_SIZE, "DECODE", "unexpected plaintext length")
            refuse(plain_hash.hexdigest() == PLAINTEXT_SHA256, "BASELINE",
                   "plaintext identity mismatch")
            offset, length = verify_plain_header(bytes(header), PLAINTEXT_SIZE)
            publish(scratch, destination)
        finally:
            if scratch is not None:
                scratch.unlink(missing_ok=True)
        sync_directory(destination.parent)

    return {
        "official_sha256": source_hash.hexdigest(),
        "plaintext_sha256": plain_hash.hexdigest(),
        "plaintext_size": plain_size,
        "firmware_offset": offset,
        "firmware_length": length,
        "blocks": count,
        "camera_io": False,
    }

def decode_stock(source: Path, destination: Path) -> None:
    """Decode the exact official 6.02 BODYDATA.DAT into the pinned plaintext FDAT.

    Raises Refusal (with a stable code) for every rejected input or output and
    leaves no partial destination behind.
    """
    _decode(Path(source), Path(destination))

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Decode the official Sony ILCE-7M4 6.02 BODYDATA.DAT to plaintext FDAT.")
    parser.add_argument("source", type=Path, help="the exact official BODYDATA.DAT")
    parser.add_argument("destination", type=Path, help="new plaintext FDAT path")
    args = parser.parse_args(argv)
    try:
        report = _decode(args.source, args.destination)
    except Refusal as error:
        print(f"refused {error.code}: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
