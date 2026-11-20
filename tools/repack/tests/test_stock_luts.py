"""Protect the archived identity LUT's packed axis order."""
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_luts import build_payload, identity_17_grid  # noqa: E402


class StockLutTest(unittest.TestCase):
    def test_identity_payload_matches_archived_bytes(self):
        payload = build_payload(identity_17_grid())
        self.assertEqual(
            hashlib.sha256(payload).hexdigest(),
            "c14036d10d22481f4e73a0853b64014c42e141807c0e2f777489820300ffb247",
        )
