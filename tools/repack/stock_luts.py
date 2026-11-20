#!/usr/bin/env python3
"""Build the four LUT assets of the candidate AP partition from Sony's s709Cubes.zip.

Offline research tooling. It reads Sony's published S709 cube archive (or a local
copy), verifies every digest, and returns the four byte-exact files that
``v3e2_ap_layout.json`` places into the candidate AP image:

    LUT001.LUT    48,000 B    identity 17-grid payload   c14036d1…
    LUT008.LUT    48,000 B    S709 17-grid payload       b90c1388…
    LUT001.cube  970,360 B    the archive member, unmodified
    S709C.cube   970,360 B    the archive member, unmodified

No vendor binary is bundled: the payloads are rebuilt from the archive's text
mesh with the closed ``.LUT`` layout — 3 channels x 8 parity phases x 1000 slots,
word = ``round(output * 8192)`` — and the 17-grid intermediate is sampled the
same way as the pinned artifacts.

Arithmetic, pinned by the archived receipts:

  * 17-grid text: one ``TITLE`` line, ``LUT_3D_SIZE 17``, then ``%.9f`` triplets
    in (b, g, r) loop order, each a trilinear sample of the 33^3 mesh at
    ``(r/16, g/16, b/16)`` *source node* coordinates;
  * identity 17-grid: ``LUT_3D_SIZE 17`` plus ``%.9g`` of ``k/16``, same loop
    order, no ``TITLE``;
  * payload: word index ``(channel*8 + 4*pr + 2*pg + pb)*1000 + slice*100 +
    row*10 + col``, 9 nodes per axis for an even parity and 8 for an odd one,
    coordinate ``2*index + parity``, 13-bit round-half-up.

The normalized sample coordinates span only the first 1/32 of the source mesh
edge, so LUT008.LUT carries near-black values (maximum 23 of 8192). That is the
pinned artifact, not a usable S709 conversion.

Dependencies: Python 3.10+ standard library; ``certifi`` is used for TLS roots
when present (python.org builds ship no CA store of their own).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import math
import ssl
import struct
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from repack_fdat import Refusal, refuse, require_regular

ZIP_URL = "https://www.sony.jp/ls-camera/knowledge/data/s709Cubes.zip"
ZIP_SHA256 = "2cc7b61b7f8b6222a18f752c020e6a84225531029748155824859e34f1cb72c4"
ZIP_MAX_BYTES = 32 << 20
CUBE_MEMBER = "s709Cubes/SL3SG3Ctos709.cube"
CUBE_SIZE = 970_360
CUBE_SHA256 = "519c6c2c90ff0b7de4a2df6c56b1d1f11b93dc9d2d086eb2f6f844b850448875"
SOURCE_GRID = 33
GRID = 17
PAYLOAD_SIZE = 48_000
QUANTA = 8192
SLOTS = 1000
BLOCK = 1 << 20
FETCH_TIMEOUT = 60
USER_AGENT = "a7m4-lut-offline-rebuild/1 (offline research)"

# Pinned intermediates: byte-identical 17-grid texts prove the sampling recipe.
IDENTITY_GRID_SHA256 = "eacbb26c873bff7b16091637acdb4690893a0f756e451c25fc371f39448d6fc2"
S709_GRID_SHA256 = "1e6a7ae43838cf67f137e7b5265a2db93ef07b9fd1a7509ecfa40f387f35f8a7"
LUT001_SHA256 = "c14036d10d22481f4e73a0853b64014c42e141807c0e2f777489820300ffb247"
LUT008_SHA256 = "b90c13886d4c55e7b77e31ccfec307fc50a05e7b4c2f3217bb3dc00cc338c405"

# Part of the byte-pinned intermediate; it does not name a tool in this repository.
S709_GRID_TITLE = 'TITLE "s709 17-grid derived using existing cube_to_record.node_lookup"'
DOMAINS = {
    "DOMAIN_MIN": (0.0, 0.0, 0.0),
    "DOMAIN_MAX": (1.0, 1.0, 1.0),
    "LUT_3D_INPUT_RANGE": (0.0, 1.0),
}
MAX_TEXT = 4 << 20
ASSET_ORDER = ("LUT001.LUT", "LUT008.LUT", "LUT001.cube", "S709C.cube")


def check_digest(label: str, actual: str, expected: str) -> None:
    refuse(actual == expected, "SHA", f"{label} SHA-256 mismatch: got {actual}, expected {expected}")


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ssl_context() -> ssl.SSLContext:
    """Default verification, with certifi's roots when installed."""
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def _open(request: urllib.request.Request, timeout: float, context: ssl.SSLContext):
    return urllib.request.urlopen(request, timeout=timeout, context=context)


def fetch_archive(url: str = ZIP_URL) -> bytes:
    """Download the archive, refusing anything beyond the fixed size bound."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with _open(request, FETCH_TIMEOUT, _ssl_context()) as response:
            declared = response.headers.get("Content-Length")
            if declared is not None:
                try:
                    advertised = int(declared)
                except ValueError:
                    raise Refusal("ZIP", f"{url} sent an unreadable Content-Length: {declared!r}") from None
                refuse(advertised <= ZIP_MAX_BYTES, "ZIP", f"{url} advertises {advertised} bytes")
            chunks: list[bytes] = []
            size = 0
            while chunk := response.read(BLOCK):
                size += len(chunk)
                refuse(size <= ZIP_MAX_BYTES, "ZIP", f"{url} exceeds the {ZIP_MAX_BYTES}-byte bound")
                chunks.append(chunk)
    except (urllib.error.URLError, ssl.SSLError, TimeoutError) as error:
        raise Refusal("NET", f"cannot fetch {url}: {error}") from None
    data = b"".join(chunks)
    refuse(bool(data), "ZIP", f"empty download from {url}")
    return data


def read_archive(path: Path) -> bytes:
    require_regular(path)
    size = path.stat().st_size
    refuse(size <= ZIP_MAX_BYTES, "ZIP", f"{path} is larger than the {ZIP_MAX_BYTES}-byte bound")
    with path.open("rb") as stream:
        data = stream.read(ZIP_MAX_BYTES + 1)
    refuse(len(data) == size, "ZIP", f"{path} changed while it was read")
    return data


def extract_cube(archive: bytes) -> bytes:
    """Return the S709 member, gated on its exact size and digest."""
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            try:
                info = bundle.getinfo(CUBE_MEMBER)
            except KeyError:
                raise Refusal("ZIP", f"archive has no member {CUBE_MEMBER}") from None
            refuse(info.file_size == CUBE_SIZE, "CUBE", f"{CUBE_MEMBER} is {info.file_size} bytes, expected {CUBE_SIZE}")
            with bundle.open(info) as stream:
                data = stream.read(CUBE_SIZE + 1)
    except zipfile.BadZipFile as error:
        raise Refusal("ZIP", f"not a readable ZIP: {error}") from None
    refuse(len(data) == CUBE_SIZE, "SIZE", f"{CUBE_MEMBER} yielded {len(data)} bytes")
    check_digest(CUBE_MEMBER, digest_bytes(data), CUBE_SHA256)
    return data


def parse_cube(text: str) -> tuple[int, list[tuple[float, float, float]]]:
    """Strict unit-domain .cube parser; nodes stay in file order (first axis fastest)."""
    refuse(len(text.encode("utf-8")) <= MAX_TEXT, "CUBE", "cube text is implausibly large")
    size: int | None = None
    nodes: list[tuple[float, float, float]] = []
    headers: set[str] = set()
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        words = line.split()
        tag = words[0]
        if tag == "TITLE":
            refuse(not nodes and tag not in headers, "CUBE", "late or duplicate TITLE")
            headers.add(tag)
            continue
        if tag in ("LUT_3D_SIZE", *DOMAINS):
            refuse(not nodes and tag not in headers, "CUBE", f"late or duplicate {tag}")
            headers.add(tag)
            if tag == "LUT_3D_SIZE":
                refuse(len(words) == 2, "CUBE", "LUT_3D_SIZE takes one argument")
                try:
                    size = int(words[1])
                except ValueError:
                    raise Refusal("CUBE", f"unreadable LUT_3D_SIZE: {words[1]!r}") from None
                refuse(2 <= size <= 129, "CUBE", f"unsupported grid size {size}")
            else:
                try:
                    actual = tuple(float(x) for x in words[1:])
                except ValueError:
                    raise Refusal("CUBE", f"unreadable {tag} value") from None
                refuse(actual == DOMAINS[tag], "CUBE", f"only the unit {tag} is supported")
            continue
        refuse(size is not None, "CUBE", "missing LUT_3D_SIZE")
        refuse(len(words) == 3, "CUBE", f"expected an R G B triplet, got {len(words)} fields")
        try:
            rgb = tuple(float(x) for x in words)
        except ValueError:
            raise Refusal("CUBE", f"unreadable triplet: {line!r}") from None
        refuse(all(math.isfinite(v) for v in rgb), "CUBE", "non-finite mesh value")
        nodes.append(rgb)  # type: ignore[arg-type]
        refuse(len(nodes) <= size ** 3, "CUBE", "more mesh nodes than LUT_3D_SIZE allows")
    refuse(size is not None, "CUBE", "missing LUT_3D_SIZE")
    assert size is not None
    refuse(len(nodes) == size ** 3, "CUBE", f"grid needs {size ** 3} nodes, found {len(nodes)}")
    return size, nodes


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def sample_mesh(
    size: int, nodes: list[tuple[float, float, float]], r: float, g: float, b: float
) -> tuple[float, float, float]:
    """Trilinear sample at source node coordinates ``0..size-1``.

    The first argument indexes the *slowest* axis of the stored node list, which
    is the transposed convention of the historical sampler. It is kept on
    purpose: it is what makes the derived 17-grid text byte-identical to the
    pinned intermediate, and it does not affect the payload builder, which reads
    the .cube file order (R fastest) directly.
    """

    def clampi(value: int) -> int:
        return 0 if value < 0 else (size - 1 if value > size - 1 else value)

    def at(ri: int, gi: int, bi: int, channel: int) -> float:
        return nodes[(ri * size + gi) * size + bi][channel]

    r = min(max(r, 0.0), size - 1.0)
    g = min(max(g, 0.0), size - 1.0)
    b = min(max(b, 0.0), size - 1.0)
    r0, g0, b0 = int(math.floor(r)), int(math.floor(g)), int(math.floor(b))
    r1, g1, b1 = clampi(r0 + 1), clampi(g0 + 1), clampi(b0 + 1)
    fr, fg, fb = r - r0, g - g0, b - b0
    out = []
    for channel in range(3):
        c00 = _lerp(at(r0, g0, b0, channel), at(r1, g0, b0, channel), fr)
        c10 = _lerp(at(r0, g1, b0, channel), at(r1, g1, b0, channel), fr)
        c01 = _lerp(at(r0, g0, b1, channel), at(r1, g0, b1, channel), fr)
        c11 = _lerp(at(r0, g1, b1, channel), at(r1, g1, b1, channel), fr)
        out.append(_lerp(_lerp(c00, c10, fg), _lerp(c01, c11, fg), fb))
    return out[0], out[1], out[2]


def derive_s709_17_grid(cube_text: str) -> str:
    """Down-sample the official 33^3 mesh to the pinned 17-grid text."""
    size, nodes = parse_cube(cube_text)
    refuse(size == SOURCE_GRID, "CUBE", f"expected a {SOURCE_GRID}^3 source mesh, got {size}^3")
    step = 1.0 / (GRID - 1)
    lines = [S709_GRID_TITLE, f"LUT_3D_SIZE {GRID}"]
    for b in range(GRID):
        for g in range(GRID):
            for r in range(GRID):
                lines.append("%.9f %.9f %.9f" % sample_mesh(size, nodes, r * step, g * step, b * step))
    return "\n".join(lines) + "\n"


def identity_17_grid() -> str:
    """The full identity 17^3 cube in the format the pinned control uses."""
    lines = [f"LUT_3D_SIZE {GRID}"]
    for b in range(GRID):
        for g in range(GRID):
            for r in range(GRID):
                lines.append("%.9g %.9g %.9g" % (r / (GRID - 1), g / (GRID - 1), b / (GRID - 1)))
    return "\n".join(lines) + "\n"


def build_payload(grid_text: str) -> bytes:
    """Pack a 17^3 cube text into the 48,000-byte polyphase payload."""
    size, nodes = parse_cube(grid_text)
    refuse(size == GRID, "LUT", f"expected a {GRID}^3 mesh, got {size}^3")
    words = [0] * (3 * 8 * SLOTS)
    for channel in range(3):
        for phase in range(8):
            parity_r, parity_g, parity_b = (phase >> 2) & 1, (phase >> 1) & 1, phase & 1
            slices = 9 - parity_r
            rows = 9 - parity_g
            columns = 9 - parity_b
            base = (channel * 8 + phase) * SLOTS
            for slice_index in range(slices):
                for row in range(rows):
                    for column in range(columns):
                        r = 2 * slice_index + parity_r
                        g = 2 * row + parity_g
                        b = 2 * column + parity_b
                        # .cube file order: R fastest, B slowest; same as (b*size + g)*size + r.
                        value = int(math.floor(nodes[r + size * (g + size * b)][channel] * QUANTA + 0.5))
                        refuse(0 <= value <= QUANTA, "LUT", f"output {value} out of 13-bit range at ({r}, {g}, {b})")
                        words[base + slice_index * 100 + row * 10 + column] = value
    payload = struct.pack(f"<{len(words)}H", *words)
    refuse(len(payload) == PAYLOAD_SIZE, "LUT", f"payload is {len(payload)} bytes, expected {PAYLOAD_SIZE}")
    return payload


def load_luts(archive_path: Path | None) -> dict[str, bytes]:
    """Return the four LUT assets, keyed by the names the AP layout expects.

    ``archive_path`` may be a local ``s709Cubes.zip``; when omitted the pinned
    Sony URL is fetched once and bounded to ``ZIP_MAX_BYTES``.
    """
    archive = fetch_archive() if archive_path is None else read_archive(Path(archive_path))
    check_digest("s709Cubes.zip", digest_bytes(archive), ZIP_SHA256)
    cube = extract_cube(archive)
    try:
        cube_text = cube.decode("utf-8")
    except UnicodeDecodeError as error:
        raise Refusal("CUBE", f"{CUBE_MEMBER} is not UTF-8 text: {error}") from None

    identity_text = identity_17_grid()
    check_digest("identity 17-grid", digest_bytes(identity_text.encode("utf-8")), IDENTITY_GRID_SHA256)
    s709_text = derive_s709_17_grid(cube_text)
    check_digest("S709 17-grid", digest_bytes(s709_text.encode("utf-8")), S709_GRID_SHA256)

    lut001 = build_payload(identity_text)
    check_digest("LUT001.LUT", digest_bytes(lut001), LUT001_SHA256)
    lut008 = build_payload(s709_text)
    check_digest("LUT008.LUT", digest_bytes(lut008), LUT008_SHA256)
    return {"LUT001.LUT": lut001, "LUT008.LUT": lut008, "LUT001.cube": cube, "S709C.cube": cube}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build LUT001.LUT, LUT008.LUT, LUT001.cube and S709C.cube from Sony's s709Cubes.zip.")
    parser.add_argument("--s709-zip", type=Path, help="local s709Cubes.zip; downloaded when omitted")
    parser.add_argument("--output", type=Path, required=True, help="existing directory for the four files; none may already exist")
    args = parser.parse_args(argv)
    try:
        refuse(args.output.is_dir(), "OUTPUT", f"output directory does not exist: {args.output}")
        assets = load_luts(args.s709_zip)
        for name in ASSET_ORDER:
            target = args.output / name
            refuse(not target.exists() and not target.is_symlink(), "EXISTS", f"output already exists: {target}")
        for name in ASSET_ORDER:
            target = args.output / name
            with target.open("xb") as stream:
                stream.write(assets[name])
            print(f"{digest_bytes(assets[name])}  {len(assets[name]):>9}  {target}")
        return 0
    except Refusal as error:
        print(f"REFUSED {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
