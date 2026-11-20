# Third-party notices

The BODYDATA.DAT decoder (`stock_dat.py`) adapts read-only container parsing from the A7M4 Fastboot Toolkit by Erlla and contributors. Its source revision is `0332a1fa94175f17ef8b9287fa42317c95648791`. The upstream files used by the decoder retain their MIT grant. [Pinned source tree](https://github.com/Erlla/sony-a7m4-custom-firmware/tree/0332a1fa94175f17ef8b9287fa42317c95648791) · [MIT license text](LICENSE.erlla-a7m4-custom-firmware)

The previous notice confused the license of this pinned source with that of a later upstream `main` revision. The later revision uses GPL-3.0. The decoder is based on the MIT revision above. [Later upstream license](https://github.com/Erlla/sony-a7m4-custom-firmware/blob/3d80c87d3ad1cf7b44e117dcf77bc8ab1985eeaa/LICENSE)

The lower-level repacker was written with reference to the toolkit's TAR member lookup, checksum row format and FAT geometry. Project-authored material uses the [repository's PolyForm Noncommercial license](../../LICENSE). The upstream MIT material retains its MIT grant.

Sony firmware is supplied by the reader. Sony S709 LUT data is downloaded from the vendor or read from the reader's verified ZIP. These inputs retain their original rights. [Sony S709 source](https://www.sony.jp/ls-camera/knowledge/)
