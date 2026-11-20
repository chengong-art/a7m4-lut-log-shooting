# Third-party notices

## A7M4 Fastboot Toolkit (MIT)

`tools/repack/repack_fdat.py` is an independent reimplementation, but its member
discovery, checksum-row rewrite and ext2/FAT geometry rules follow:

- `a7m4/firmware.py` — `tar_index`, `update_sum`
- `a7m4/fat.py` — FAT12/16 geometry derivation

Those files are distributed under the MIT License, reproduced below as required.

```
MIT License

Copyright (c) 2026 A7M4 Fastboot Toolkit contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

No Sony firmware, extracted library, donor colour data or other third-party
binary is covered by this notice or by the MIT grant.

## How the licenses layer

The repository as a whole is offered under the PolyForm Noncommercial License
1.0.0 (`../../LICENSE`).

`tools/repack/repack_fdat.py` is this project's own code. It was written from the
observable behaviour of the toolkit above — member discovery, checksum rows,
ext2/FAT geometry — not copied from it, so no upstream source is vendored here.
The notice is reproduced for attribution.

One provenance correction worth recording: the local toolkit tree declares MIT
in its own `LICENSE`, but that tree is a port of
[Erlla/sony-a7m4-custom-firmware](https://github.com/Erlla/sony-a7m4-custom-firmware),
which is GPL-3.0. That internal inconsistency is the port's, not this
repository's, and it is unresolved as of this writing. Anyone who needs the port
itself should treat it under the upstream GPL-3.0 terms.

Nothing here grants a commercial license for the PolyForm-covered material, and
nothing here relicenses GPL-3.0 upstream code.
