#!/usr/bin/env python3
"""Offline-only: replace two vetted v3b AArch64 words in a COPY of AP p15.

Not a full firmware builder, installer, or signing tool.
"""
from __future__ import annotations
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import sys
import tempfile

AP_SIZE = 378_580_992
OFFSET = 0x129E2704
OLD = bytes.fromhex("7306001014008052")
NEW = bytes.fromhex("5309001034008052")
EXPECTED_SHA256 = "76fbffb9c3b6a497261210eb4be98d5805bbf13f3b00347b334e99a58e055d66"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def run(source: Path, dest: Path) -> str:
    if not source.is_file() or source.is_symlink():
        raise ValueError("source must be a regular, non-symlink file")
    if source.stat().st_size != AP_SIZE:
        raise ValueError(f"expected {AP_SIZE} bytes for v3b AP p15")
    if dest.exists() or dest.is_symlink():
        raise ValueError("output already exists; refusing to overwrite")
    if source.resolve() == dest.resolve():
        raise ValueError("source and destination must differ")
    if not dest.parent.exists():
        raise ValueError("output directory does not exist")
    with source.open("rb") as inp:
        inp.seek(OFFSET)
        if inp.read(len(OLD)) != OLD:
            raise ValueError("unexpected original bytes; source is not known v3b p15")

    fd, temporary = tempfile.mkstemp(prefix=".v3e2.", suffix=".tmp", dir=str(dest.parent))
    os.close(fd)
    temp_path = Path(temporary)
    try:
        with source.open("rb") as inp, temp_path.open("r+b") as out:
            shutil.copyfileobj(inp, out, 1024 * 1024)
            out.seek(OFFSET)
            if out.read(len(OLD)) != OLD:
                raise ValueError("source changed while copying, aborting")
            out.seek(OFFSET)
            out.write(NEW)
            out.flush()
            os.fsync(out.fileno())
        digest = sha256_file(temp_path)
        if digest != EXPECTED_SHA256:
            raise ValueError(f"result SHA256 mismatch: {digest}; refusing to publish")
        # Atomic refusal to overwrite a destination created concurrently.
        os.link(temp_path, dest)
        return digest
    finally:
        temp_path.unlink(missing_ok=True)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("v3b_p15", type=Path, help="input partition image; never modified")
    p.add_argument("v3e2_p15", type=Path, help="new output path; must not exist")
    args = p.parse_args()
    try:
        digest = run(args.v3b_p15, args.v3e2_p15)
    except (OSError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"{digest}  {args.v3e2_p15}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
