# 离线 FDAT 组包器（最小实现）

给**已经持有 v3b 与官方明文 FDAT** 的人一条可以自己算出 `22e8bf6a…` 的路径。仅标准库，Python 3.10+。

它只做一件事：在官方明文 FDAT 的副本里，按相同尺寸替换 `dev/nflasha15` 与 `dev/nflasha8` 两个成员，并改写它们在 `part_image.sum` 中对应的 CRC32 行。不构建、不签名、不安装。

## 三个子命令

```sh
# 打印成员名、大小与数据偏移
python3 tools/repack/repack_fdat.py list /path/to/fdat

# 取出一个成员（成员名原样，含目录前缀）
python3 tools/repack/repack_fdat.py extract /path/to/fdat 0700_part_image/dev/nflasha15 out.img

# 用官方 FDAT + 两个分区镜像重组
python3 tools/repack/repack_fdat.py build /path/to/official.fdat \
  --ap v3e2-p15.img --ap-sha256 76fbffb9c3b6a497261210eb4be98d5805bbf13f3b00347b334e99a58e055d66 \
  --cp stock-p8.img  --cp-sha256 62d16a76ac949e7f9ec5b9b1a46c7cdc65148b1a169b8d617c83c441d7806aee \
  --output v3e2-once.fdat
```

## 实测收据（2026-11-21，本机离线）

输入：官方明文 FDAT `4fd810b8d20ea239e0df01aded90687baef1ca2c8df208a7f58c4989f85799c3`；v3b 候选 FDAT `84a96f461a89acd799ba01dca0acfc4d7f0b9adb21461c230a3049a9e838a20c`。

```sh
repack_fdat.py list official.fdat
#   378580992      97698304  0700_part_image/dev/nflasha15
#    22777856     722952192  0700_part_image/dev/nflasha8
#         454     745731072  0701_part_image_sum/part_image.sum

repack_fdat.py extract v3b.fdat 0700_part_image/dev/nflasha15 v3b-p15.img
repack_fdat.py extract official.fdat 0700_part_image/dev/nflasha8 stock-p8.img
python3 scripts/patch_v3b_p15.py v3b-p15.img v3e2-p15.img
repack_fdat.py build official.fdat --ap v3e2-p15.img --ap-sha256 76fbffb9… \
  --cp stock-p8.img --cp-sha256 62d16a76… --output v3e2-rebuilt.fdat
```

结果：`v3e2-rebuilt.fdat` = `22e8bf6a7039f6aed375b8c0bdf6c284cf0c0f83ff9a72d089ff007ba82e7a5f`，与归档的 `v3e2-once.fdat` **逐字节相同**（`cmp` 无差异）。输出的 FDAT 头、tar 布局与成员偏移全部沿用官方件，未重排、未重签。

## 它不做什么

- **不能从官方 FDAT 造出 v3b。** v3b 的代码洞、`PT_LOAD` 扩段、ext2 内 `data/lut` 注入与 LUT 数据件都不在本仓库；v3b 仍需你自行取得。
- 不改 FDAT 头，不重算头部 CRC（成员尺寸不变，头部无需变），不重排 tar，不签名。
- AP 只查 ext2 超级块魔数与不兼容位；不逐文件校验 ext2 内容。CP 只查 FAT 几何与多份 FAT 副本一致；不校验目录树。
- 输出不是可安装升级包，不可写入机身。

## 安全门

| 门 | 行为 |
|---|---|
| 输入形态 | 拒绝符号链接与非普通文件 |
| 官方件身份 | 尺寸必须为 754,521,088 字节且 SHA256 命中；复制过程中再算一次 |
| 成员几何 | 两个成员必须存在且尺寸与表一致；分区镜像尺寸必须相同（不做伸缩） |
| 分区镜像 | SHA256 必须命中调用者给出的值 |
| AP | ext2 魔数 `0x53EF`；不兼容位只允许 FILETYPE |
| CP | FAT 引导签名、几何合法、簇数 < 4085、多份 FAT 一致 |
| 校验表 | 旧 CRC32 必须与文件内实际字节相符；新行长必须与旧行相同 |
| 输出 | 目标已存在即拒绝；失败时删除半成品 |

## 测试

```sh
python3 -B -m unittest discover -s tools/repack/tests -v
```

11 项，跑在合成的 12 KiB 容器上（不接触真实镜像）：成员替换、校验行改写、同字节输入零差异、以及 8 类拒绝路径（已存在输出、尺寸不符、摘要不符、非 ext2、ext3/ext4 位、非 FAT12、FAT 副本不一致、头部篡改、校验行篡改）。

## 来源说明

成员定位、校验表改写与 ext2/FAT 几何判定的算法参照 MIT 许可的 A7M4 Fastboot Toolkit（`a7m4/firmware.py` 的 `tar_index` / `update_sum`、`a7m4/fat.py` 的 FAT 几何推导）；本目录为独立重写，不复制其代码，也不引入其 cryptography / dissect 依赖。见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
