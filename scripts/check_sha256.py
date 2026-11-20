#!/usr/bin/env python3
"""Offline-only file identity check; not a firmware safety or installation check."""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import re

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("file",type=Path)
    p.add_argument("expected_sha256",help="64 hexadecimal digits")
    a=p.parse_args()
    if not re.fullmatch("[0-9a-fA-F]{64}",a.expected_sha256):
        p.error("expected 64 hexadecimal SHA256 characters")
    h=hashlib.sha256()
    with a.file.open('rb') as f:
        for data in iter(lambda:f.read(1024*1024),b''):
            h.update(data)
    actual=h.hexdigest()
    print(f"{actual}  {a.file}")
    return 0 if actual==a.expected_sha256.lower() else 1

if __name__=='__main__':
    raise SystemExit(main())
