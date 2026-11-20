# A7M4 / A7 IV 6.02 · LUT & Log Shooting Research

> **研究阶段 / Research only · Not flashable · `release_ready=false`**
>
> 这是面向技术社区的 **离线复现与代码审查项目**，不是可供相机安装的固件发布。请勿向实机刷入此项目生成的明文 FDAT 候选文件。

[中文](README.md) · Sony α7 IV / ILCE-7M4 · 固件基线 6.02 · Candidate `v3e2-once`

## 项目目标

探索 Sony A7 IV（A7M4）固件中 LUT 与 Log Shooting 相关实现，邀请熟悉 ELF/AArch64、Linux/QEMU、文件系统、逆向分析及色彩管线的朋友**共同开展离线验证**。

本公开仓库是从私人研究项目中选出的、适合公共协作的**独立材料包**，不继承原私有仓库的 Git 历史，不包含 Sony 原厂或改造后的固件镜像。

## 2026-11-20 研究进展（以原研究记录为准）

- 已给出 `v3e2-once` 的离线构建方案与输入/输出 SHA-256 身份信息。
- **离线完整构建**：从 Sony 原厂 `BODYDATA.DAT` 获取起始字节，通过 `cmp` 验证产物与候选归档逐字节一致。
- **QEMU 夹具**：观察到 AP 侧 `libmpr` 的 LUT 包头及 `ELUT` 标记，**不代表自然机内 LUT 功能可用**。
- **Unicorn 替身调用**：记录了 `S709C → init → LUT001` 路径；真实 `mpr Init` 及 LUT001 后续加载结果未被同一回放完整观测到。
- **尚未验证**：真实机身、自然菜单触发、CP MLUT 消费、预览/录像色彩应用、正常签名与安装途径。

详细边界、已知值与证据说明： [docs/STATUS.md](docs/STATUS.md)。

## 从原厂包开始构建

准备 Sony A7 IV 6.02 原厂 `BODYDATA.DAT`，按 [复现指南](docs/REPRODUCE.md) 安装 Python 依赖、运行构建器并核对输出。Sony S709 数据由构建器从官方来源取得，也可使用预先下载的同一份 ZIP。

- [`tools/repack/build_from_stock.py`](tools/repack/build_from_stock.py) 从原厂包直接生成 `v3e2-once.fdat`，预期 SHA-256 为 `22e8bf6a…`。
- [`scripts/check_sha256.py`](scripts/check_sha256.py) 独立检查原厂包和候选包的摘要。
- [底层 FDAT 工具与测试](tools/repack/README.md) 提供本地文件提取、重组和回归测试。

## 招募哪类贡献？

1. 审计 AArch64 指令解码、控制流、ELF 映射与重定位解释。
2. 检查离线文件一致性、哈希计算及防误操作门禁。
3. 核对已公开的 QEMU 和 Unicorn 观察范围。历史仿真的完整夹具与运行脚本未随本仓库提供。
4. 建立来源清晰的公开测试收据（命令、工具版本、输入身份、退出码、日志中非敏感片段）。

请通过 Issues 提交结果：**明确是静态分析、离线模拟，还是自然硬件观察**。不要把模拟/注入得出的 PASS 标成实机 PASS。

## 安全与版权

- 不提供 Sony 原厂固件、解密镜像、第三方私有 blob 或序列号。
- 不提供、接受或鼓励真实机身刷机、服务接口写入或绕过签名的现场测试报告；当前阶段只做离线测试。
- 不会以研究结果承诺机身可恢复或功能可用；自行承担损坏风险并遵守当地法律和相关权利。
- 如发现私密信息、未经授权资料等，请先私下联系维护者，不要在公开 Issue 中张贴。详见 [SECURITY.md](SECURITY.md)。

## 许可

本仓库原创内容（文档、脚本、测试）按 **PolyForm Noncommercial License 1.0.0** 提供：允许个人研究、学习、实验与非商业组织使用，**不允许商业用途**。全文见 [LICENSE](LICENSE)，SPDX 标识 `PolyForm-Noncommercial-1.0.0`。

- 这不是 OSI 定义的开源许可——它限制了使用目的，准确说法是「源码可用（source-available）」。
- 分发时必须一并转交 `LICENSE` 及其中以 `Required Notice:` 开头的行。
- 提交 Issue / PR 即表示你的贡献按同一许可授权本项目再分发。
- 原厂包解码器采用 Erlla 工具链固定修订中的 MIT 代码，保留原许可与署名。详见 [第三方许可和来源](tools/repack/THIRD_PARTY_NOTICES.md)。
- 本许可不覆盖 Sony 固件、解密镜像、donor 色彩数据等第三方材料；这些材料不由本仓库分发。
- 构建过程中用到的开源项目与其作者，见 [ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md)。

## 版本来源

研究仓库：`chengong-art/camera-firmware-research`（原仓库为私有，未公开）。

文档依据：`docs/log-shooting-v3e2-once.md`，研究分支 `chengong-art/log-shooting-v3e2-once-20261120`，修正提交 `48e1ee320f63959315ea8ff602d132e914506bca`。本仓库为独立整理稿，不代表原始研究证据已经全部公开。

> 本项目与 Sony 无从属或官方认可关系，索尼及 Alpha 等名称仅用于技术识别。
