# 从 Sony 原厂 6.02 包重建 v3e2-once

只需自备 Sony α7 IV（ILCE-7M4）6.02 的原厂 `BODYDATA.DAT`。脚本会从 Sony 下载固定版本的 S709 LUT 数据。已有 `s709Cubes.zip` 时，可指定本地路径完成全程离线构建。

产物仅供离线研究。它是明文、未签名的 FDAT，`release_ready=false`。

## 1. 获取并核对原厂文件

从 [Sony 官方 6.02 下载页](https://support.sony.jp/electronics/support/software/00400195) 取得 `BODYDATA.DAT`。文件大小为 757,480,856 字节。文件名可以不同，SHA-256 必须为 `ad6df47a0a93a46336b9920a0d8891d0c766f8c96fa68ebda8685f6c21621188`。构建器会再次核对尺寸和摘要。

## 2. 准备 Python 环境

在仓库根目录运行。使用 Python 3.10–3.13。本地输出目录应支持硬链接（例如 APFS、ext4、NTFS），预留 3 GB 可用空间，不含原厂文件本身。FAT 或 exFAT 不支持所需的硬链接。

如尚未取得仓库，先运行 `git clone https://github.com/chengong-art/a7m4-lut-log-shooting.git`，再执行 `cd a7m4-lut-log-shooting`。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r tools/repack/requirements.txt
```

Windows 可用 `py -3.13 -m venv .venv`（按已安装的版本调整），并用 `.venv\Scripts\python.exe` 替换文中各步的 `.venv/bin/python`。

## 3. 从原厂包构建候选

将 `BODYDATA.DAT` 放在仓库根目录，或传入该文件的实际路径。

```sh
.venv/bin/python scripts/check_sha256.py BODYDATA.DAT ad6df47a0a93a46336b9920a0d8891d0c766f8c96fa68ebda8685f6c21621188
.venv/bin/python tools/repack/build_from_stock.py BODYDATA.DAT --output v3e2-once.fdat
```

如需使用本地 LUT 数据，在第二条命令末尾加上 `--s709-zip /path/to/s709Cubes.zip`。原始 ZIP 可从 [Sony 官方 S709 页面](https://www.sony.jp/ls-camera/knowledge/) 或 [Sony 下载链接](https://www.sony.jp/ls-camera/knowledge/data/s709Cubes.zip) 获取。脚本会核对 ZIP 和 `.cube` 成员的 SHA-256。输出路径已存在时请换一个文件名。

构建分四步。首先将原厂包解码为明文 FDAT。然后取出 AP 与 CP 分区并准备 LUT 文件。随后从原厂 `appFw.so` 重建候选 AP 分区。最后回填 AP 和原厂 CP，更新分区校验表，校验完整输出后才生成 `v3e2-once.fdat`。`v3b.fdat`、私有 QEMU 夹具和历史候选都无需准备。

## 4. 核对输出

```sh
.venv/bin/python scripts/check_sha256.py v3e2-once.fdat 22e8bf6a7039f6aed375b8c0bdf6c284cf0c0f83ff9a72d089ff007ba82e7a5f
```

通过时命令退出码为 `0`。该摘要标识已归档的历史候选。AP、CP、`appFw.so` 和校验表的摘要见 [证据状态](STATUS.md#已登记身份-sha-256)。

## 构建参数为何固定

归档候选的 ext2 分区包含特定的 inode、物理块分配和时间字段。一般文件系统工具即使写入相同文件，也可能产生不同的分区字节。[布局文件](../tools/repack/v3e2_ap_layout.json) 记录这份候选的文件位置、项目补丁和 ext2 元数据差量。其余 `appFw.so` 字节从读者提供的原厂包取得。两种 `.LUT` 由脚本生成，`.cube` 取自 Sony ZIP。归档的空闲块和块尾还留有旧测试数据与搬移残留，由公式和原厂字节还原。

`LUT008.LUT` 按归档候选的历史采样方式重建。该方式只采样原始 S709 立方体边长的 1/32，生成的 16 位字最大值为 23（单位值对应 8192）。复现保留这份近黑数据。项目另保留原样的 Sony S709 `.cube` 文件。

如已持有 `v3b` 的 AP 分区，可继续使用 `scripts/patch_v3b_p15.py` 做历史对照。低层容器提取和回填工具见 [组包器参考](../tools/repack/README.md)。

QEMU 和 Unicorn 的历史观察见 [证据状态](STATUS.md)。本构建指南验收的是文件字节。真实机身、自然菜单触发、CP MLUT 消费、预览与录像仍未验证。
