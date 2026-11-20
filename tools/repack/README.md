# A7 IV 6.02 离线构建工具

从 Sony 官方 `BODYDATA.DAT` 开始，请看 [完整复现指南](../../docs/REPRODUCE.md)。入口是 `build_from_stock.py`，负责解码、分区提取、LUT 生成、AP 文件及 ext2 布局重建、整包回填和完整 SHA-256 校验。

## 明文 FDAT 的底层工具

`repack_fdat.py` 使用 Python 3.10+ 标准库。它提供以下命令，可在仓库根目录运行。

```sh
python3 tools/repack/repack_fdat.py list official.fdat
python3 tools/repack/repack_fdat.py extract official.fdat 0700_part_image/dev/nflasha15 stock-p15.img
python3 tools/repack/repack_fdat.py build --help
```

`build` 接受固定摘要的原厂明文 FDAT，以及由调用者提供、尺寸相同的 AP ext2 和 CP FAT12 分区，回填对应成员并更新 `part_image.sum` 的 CRC32。FDAT 头、TAR 布局和其他成员沿用原厂文件。对于标准候选，`build_from_stock.py` 会自行准备分区输入并调用这个接口。

组包器使用同一份分区快照计算 SHA-256、CRC32 并写入产物。构建完成后通过硬链接提交输出，因此既有文件和同时创建的文件都不会被覆盖。输出目录应位于支持硬链接的本地文件系统。

## 测试

```sh
python3 -B -m unittest discover -s tools/repack/tests -v
```

组包器回归覆盖分区尺寸、摘要与格式、校验表、输出竞争、输入变更和清理。测试使用合成文件。用真实原厂输入验证完整候选，请执行上面的复现指南并比对最终 SHA-256。

## 来源

解码器采用 Erlla 工具链固定 MIT 提交中的容器解析依据。组包器在 Python 标准库中实现同尺寸成员回填。上游固定修订与许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
