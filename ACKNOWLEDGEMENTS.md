# 致谢与开源依赖

这个项目能走到今天，靠的是一群把自己摸索出来的东西公开出来的研究者，以及一批长期维护的基础工具。以下只列**实际用到**的项目；仅检索到或只读过的资料不在其列。

> 这些项目各自按其原许可使用。它们的代码不由本仓库分发，本仓库的许可也不覆盖它们。

## 固件格式与设备接入

| 项目 | 我们用它做什么 |
|---|---|
| [Erlla/sony-a7m4-custom-firmware](https://github.com/Erlla/sony-a7m4-custom-firmware) | 本项目主机侧工具链的移植来源（固定提交 `0332a1fa…`）：fastboot 主机工具、SD 更新救砖入口、七份独立修改方法。我们的 macOS 移植只改驱动绑定、设备锁、BOOTSEL 卷与入口脚本，**固件配方、地址与哈希钉全部沿用未改**。许可为 GPL-3.0，详见下方说明。 |
| [DavidBuchanan314/ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE) | 串行启动、RP2040 桥、相机侧 fastboot payload 与 eMMC 访问。没有这条通道，后面的分区只读回读与写入都无从谈起。 |
| [DavidBuchanan314/fwtool.py（a7iv 分支）](https://github.com/DavidBuchanan314/fwtool.py/tree/a7iv) | A7 IV 升级包格式与容器解包。 |
| [ma1co/fwtool.py](https://github.com/ma1co/fwtool.py) | Sony 固件容器格式与解包的基础实现。 |
| [ma1co/Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) | 相机协议与服务模式的研究背景。 |
| [q19032/Sony-firmware-unpacker](https://github.com/q19032/Sony-firmware-unpacker) | 固件解密与密钥推导的研究参考。 |
| [AOSP fastboot](https://android.googlesource.com/platform/system/core/+/refs/heads/main/fastboot/) | 主机侧 fastboot 协议参考（我们用的是独立 host 实现）。 |

## 二进制分析

| 项目 | 我们用它做什么 |
|---|---|
| [Capstone](https://github.com/capstone-engine/capstone) | AArch64 反汇编：候选补丁的指令级判定、函数与间接调用核对。 |
| [Unicorn](https://github.com/unicorn-engine/unicorn) | 指令级回放：loader / init 路径的替身调用对拍。 |
| [pyelftools](https://github.com/eliben/pyelftools) | ELF 段表、重定位表与导出符号解析。 |
| [Keystone](https://github.com/keystone-engine/keystone) | 汇编侧参考（早期补丁试验使用）。 |

## 仿真

| 项目 | 我们用它做什么 |
|---|---|
| [QEMU](https://gitlab.com/qemu-project/qemu) | A7 IV 6.02 AP/CP 启动夹具，以及 TCG 只读观测插件的宿主。离线判定能成立，靠的是它。 |

## 文件系统与数据

| 项目 | 我们用它做什么 |
|---|---|
| [Dissect（extfs / util / cstruct）](https://github.com/fox-it/dissect) | ext2 分区的逐文件身份判定与同尺寸回填。 |
| [squashfs-tools-ng](https://github.com/AgentD/squashfs-tools-ng) | 更新器文件系统重建（作为外部程序调用）。 |
| [NumPy](https://github.com/numpy/numpy) | 批量字节比对与像素误差统计。 |

## 密码与传输

| 项目 | 我们用它做什么 |
|---|---|
| [cryptography](https://github.com/pyca/cryptography) | 升级包容器校验与签名材料处理。 |
| [pySerial](https://github.com/pyserial/pyserial) | RP2040 桥的串口传输。 |

## 桥与工具链

| 项目 | 我们用它做什么 |
|---|---|
| [Pico SDK](https://github.com/raspberrypi/pico-sdk) | RP2040 桥固件构建。 |
| [arduino-pico](https://github.com/earlephilhower/arduino-pico) | RP2040 桥固件构建。 |
| [arduino-cli](https://github.com/arduino/arduino-cli) | 上述构建的命令行驱动。 |

## 备份与恢复

| 项目 | 我们用它做什么 |
|---|---|
| [happyfrog2026/a74-recovery-tools](https://github.com/happyfrog2026/a74-recovery-tools) | A7M4 的备份 / 还原路线：「Camera Recovery」桌面应用，把整机备份做成可校验的 snapshot，并提供原厂固件恢复路径。我们对照它核对了备份粒度（含 boot0/boot1、分区表与 SHA）、RP2040 Multi 适配器接法与恢复前置条件，用来检查自己的备份与回滚方案有没有漏项。 |

## 运行时与测试

| 项目 | 我们用它做什么 |
|---|---|
| [CPython](https://github.com/python/cpython) | 全部离线工具与组包器（`tools/repack/` 仅用标准库）。 |
| [pytest](https://github.com/pytest-dev/pytest) | 参考实现的测试套件。 |

## 对照研究

| 项目 | 我们用它做什么 |
|---|---|
| [QAQLeonard/a7c2-fl23-research](https://github.com/QAQLeonard/a7c2-fl23-research) | A7C II 的 FL2/FL3 参数与安装研究；其历史配方作为本次 A7M4 的对照。未打包其 payload 或源码。 |
| [leogenot/sony-a7iv-feature-research](https://github.com/leogenot/sony-a7iv-feature-research) | 直接改变了本项目走向的一份研究：A7 IV 6.02 的产品类是 `PRODUCT_MODEL_LS`、Log Shooting 的 HAITA 规则列举 14 个产品类却不含 LS，属产品级排除。我们在它的结论上定位到具体规则字节码 `0x4364648` 与 `f9 60 c6 06 f9`。它标注的 "Experiment: none" 也是我们最终停下「完整 LS 功能」的直接依据。 |
| [DavidBuchanan314/Sony-ILCE-7M4-Linux](https://github.com/DavidBuchanan314/Sony-ILCE-7M4-Linux) | 平台 Linux 参考源码。 |

## 三点如实说明

- **ILCE-7M4-RE 在其源码树中未见明确许可。** 公开可见与署名都不等于再分发授权，因此本仓库只写独立 host 实现并外链，不搬运其 payload、UF2 或源码。若上游后续给出许可，这里会相应更新。
- **Erlla/sony-a7m4-custom-firmware 是 GPL-3.0。** 我们的本地移植目录原先自署 MIT，这对一个配方未改的 GPL-3.0 移植不成立；该目录已改为 GPL-3.0（逐字 gnu.org 全文，新增 `NOTICE` 记录出处与改动范围，`pyproject` 改 `GPL-3.0-only`，README/REFERENCES/两份示例说明同步）。本仓库不包含该移植的任何代码，只记录身份与结论。
- **QEMU（GPL-2.0）与 squashfs-tools-ng（GPL-3.0 / LGPL-3.0）以外部程序方式使用**，不与本仓库代码链接，也不随本仓库分发。

## 谢谢

特别感谢 **Erlla**：`sony-a7m4-custom-firmware` 把 fastboot 主机工具、救砖入口和七份修改方法整理成可审查的形态，我们的整个主机侧工作都站在它上面。

特别感谢 **DavidBuchanan314**：没有 ILCE-7M4-RE 里那套 BootROM 串行启动与 RP2040 桥，这个项目连门都进不去。

感谢 **ma1co**：`fwtool.py` 与 PMCA-RE 是所有人理解 Sony 固件容器的起点。

感谢 **leogenot**：那篇 feature research 里的产品级排除结论，让我们在第三轮无进展时停下并承认"这不是工程量问题"。承认做不成，比继续调参有价值。

感谢 **happyfrog2026**：把备份、校验与恢复做成一键路径，并明确写出「有效签名或菜单出现都不等于刷写安全」。这正是这个圈子最缺的那种冷静。

感谢 **Capstone、Unicorn、QEMU** 的维护者：让「离线判定一段指令到底会不会被执行」成为可以重复的实验，而不是猜测。

感谢 **fox-it** 把 Dissect 做成能直接读 ext2 的库，省掉了我们重复造解析器的时间。

也感谢每一位把自己的摸索过程写下来、把失败也一并公开的研究者——这个领域里，公开的否定结果和公开的成功结果一样有价值。
