# 离线复现说明（不涉及真实相机）

本仓库公开**核心指令修正和输入身份约束**，并非一键构建完成的发行仓库。

## 输入前提

- 具备用户自己合法获得且独立验证身份的 Sony A7 IV 6.02 原厂明文 FDAT：SHA256 `4fd810b8d20ea239e0df01aded90687baef1ca2c8df208a7f58c4989f85799c3`。
- 具备原研究 v3b 生成物的合法副本（**不在本仓库提供**），FDAT SHA256 `84a96f461a89acd799ba01dca0acfc4d7f0b9adb21461c230a3049a9e838a20c`。
- 能够从 v3b 与原厂 FDAT 中提取 `dev/nflasha15`（AP ext2）和 `dev/nflasha8`（CP FAT12）。提取与改组包由本仓库的 [`tools/repack/repack_fdat.py`](../tools/repack/repack_fdat.py) 完成，仅需 Python 标准库。
- 空余磁盘空间足够容纳多个约 754 MB 的明文 FDAT 和 379 MB 的 AP 分区。所有操作仅针对文件副本。

## v3b → v3e2 的两条指令修正

基于原记录：v3b 在 `lib/appFw.so` 的 `0x50BBB04` 和 `0x50BBB08` 两处，依次对应其 AP p15 分区副本上偏移 `0x129E2704` 开始的 8 字节。

| 位置 | v3b（小端字节） | v3e2（小端字节） |
|---|---|---|
| `0x129E2704` | `73 06 00 10` — `adr x19,0x50BBBD0` | `53 09 00 10` — `adr x19,0x50BBC2C` |
| `0x129E2708` | `14 00 80 52` — `mov w20,#0` | `34 00 80 52` — `mov w20,#1` |

**示例（仅对已提取的 AP 文件副本，不操作相机或原厂设备）：**

```sh
python3 scripts/patch_v3b_p15.py /path/to/v3b-p15.img /path/to/v3e2-p15.img
```

脚本会检验 AP 文件大小、原始 8 字节，并对目标完整文件计算 SHA256；只有生成结果符合文档身份时才成功发布。它不会在原输入文件上修改，且拒绝覆盖现有目标文件。

## 重组 FDAT：现已可独立复跑

```sh
python3 tools/repack/repack_fdat.py extract v3b.fdat 0700_part_image/dev/nflasha15 v3b-p15.img
python3 tools/repack/repack_fdat.py extract official.fdat 0700_part_image/dev/nflasha8 stock-p8.img
python3 scripts/patch_v3b_p15.py v3b-p15.img v3e2-p15.img
python3 tools/repack/repack_fdat.py build official.fdat \
  --ap v3e2-p15.img --ap-sha256 76fbffb9c3b6a497261210eb4be98d5805bbf13f3b00347b334e99a58e055d66 \
  --cp stock-p8.img  --cp-sha256 62d16a76ac949e7f9ec5b9b1a46c7cdc65148b1a169b8d617c83c441d7806aee \
  --output v3e2-once.fdat
```

组包器按官方 FDAT 的原有布局做同尺寸回填，并改写 `part_image.sum` 中两个分区的 CRC32 行；输出头、tar 布局与成员偏移全部沿用官方件。它拒绝尺寸不符、摘要不符、非 ext2 AP、非 FAT12 CP 与已存在的输出。

实测（2026-11-21，离线）：上述命令在本机复现 `22e8bf6a7039f6aed375b8c0bdf6c284cf0c0f83ff9a72d089ff007ba82e7a5f`，与归档的 `v3e2-once.fdat` 逐字节相同。细节与安全门见 [`tools/repack/README.md`](../tools/repack/README.md)。

这是离线文件身份检查，既不是签名，也不表示可以安装。

## 仍未公开的部分

**从官方 FDAT 生成 v3b 的链路没有公开**：注入代码洞、扩 `PT_LOAD`、在 ext2 内新建 `data/lut` 并放入四个数据件、改 thunk 指向，都不在本仓库。原研究使用的 `tools/build_log_shooting_candidate.py` 与 `ports/erlla-a7m4-macos/a7m4/` 只是当时的实现，不是本仓库的依赖。

因此外部人员能走到「官方 FDAT + 已持有的 v3b → v3e2 并自行核对 `22e8bf6a…`」，但无法从官方件独立造出 v3b，也就无法独立审查 v3b 本身。这是当前公开范围的边界，不是工具缺陷。

如果你能在合法和离线条件下做独立验证，请提交 Issue，记录哈希、工具版本与可复现命令，并且**不要公开任何原厂二进制**。

## 证据限制

QEMU 只确认了 AP 侧特定观察点的 LUT 包头；没有证明真实 `mpr Init` 返回、第二 LUT 加载、自然机身 UI、CP/ISP/录像。严禁把模拟器观察写成机身功能已实现。
