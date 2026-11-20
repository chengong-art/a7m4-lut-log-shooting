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
1.0.0 (`../../LICENSE`). `tools/repack/repack_fdat.py` is this project's own
code, written from the behaviour of the MIT-licensed toolkit above rather than
copied from it, so the MIT notice is reproduced here for attribution.

If any portion of this directory is ever found to be a substantial copy of MIT
code, that portion stays available under MIT as well; the rest of the
repository is unaffected. Nothing here grants a commercial license for the
PolyForm-covered material.
