# v3e2-once 研究状态和证据边界

离线构建于 2026-11-21 验证。历史仿真依据原研究仓库 `chengong-art/log-shooting-v3e2-once-20261120` 分支的文档修订 `48e1ee3`。

| 项目 | 已记录结果 | 证据类别 | 是否实机确认 |
|---|---|---|---|
| 版本 / FDAT 成员身份 | 产物和 p15/p8/SUM SHA-256 已记录 | 离线哈希 / 身份表 | 否 |
| 从原厂 `BODYDATA.DAT` 重建 v3e2 | macOS arm64、Python 3.10。自动下载 Sony LUT ZIP 与读取本地 ZIP 各构建一份，`cmp` 均与归档逐字节相同（754,521,088 字节） | 离线构建 | 否 |
| 进入 LUT 相关 AP 通路 | QEMU 观察到非零 `BUF` 和 `ELUT` 包头。同一回放中的 `INIT_EXIT=0` 来自 SD 初始化 | QEMU 夹具 | 否 |
| `S709C → Init → LUT001` 路径 | Unicorn 模拟替身调用符合预期 | 人工调用 / 模拟 | 否 |
| 真实 `mpr Init` 返回、LUT001 后续加载 | 未完整观测 | 未验证 | 否 |
| 自然菜单 / 模式 UI | 未验证 | 未验证 | 否 |
| 目标 LUT 槽 / CP MLUT 硬件消费 | 未验证 | 未验证 | 否 |
| 真实预览与录像像素 | 未验证 | 未验证 | 否 |
| Sony 原厂升级机制支持 | 候选是**未签名的明文 FDAT** | 不支持安装声明 | 否 |

**`release_ready=false`，禁止真实机身刷写。**

## v3b 组件验证的范围

v3b 复核只确认了测试工装直接调用 setter 的路径，以及 QEMU 客体 CPU 上三线性测试程序的像素比对。自然菜单触发、目标槽实际写入、CP MLUT 消费、预览和录像仍待验证。v3b 完整功能的复核结论为 `UNVERIFIED`。

## 已登记身份 SHA-256

| 对象 | SHA-256 |
|---|---|
| Sony 官方 6.02 `BODYDATA.DAT` | `ad6df47a0a93a46336b9920a0d8891d0c766f8c96fa68ebda8685f6c21621188` |
| 原厂明文 FDAT 基线 | `4fd810b8d20ea239e0df01aded90687baef1ca2c8df208a7f58c4989f85799c3` |
| 历史 v3b 候选 FDAT（用于 v3b 对照） | `84a96f461a89acd799ba01dca0acfc4d7f0b9adb21461c230a3049a9e838a20c` |
| **v3e2-once FDAT** | `22e8bf6a7039f6aed375b8c0bdf6c284cf0c0f83ff9a72d089ff007ba82e7a5f` |
| v3e2 p15 / `dev/nflasha15` | `76fbffb9c3b6a497261210eb4be98d5805bbf13f3b00347b334e99a58e055d66` |
| 原厂 p8 / `dev/nflasha8`（未变） | `62d16a76ac949e7f9ec5b9b1a46c7cdc65148b1a169b8d617c83c441d7806aee` |
| `part_image.sum` | `a7532719f25647679352570bdda6c2e1069073de158d9a473c4028b524e1d540` |
| v3e2 `lib/appFw.so` | `8f028645da512fcf7adb7eff22eb0add864f5399e6a198eb197186e4dda82574` |

按 [公开复现指南](REPRODUCE.md) 可核对原厂包与产物身份。整包字节一致性属于离线验收。
