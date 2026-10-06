# nte-core 组件记录

本目录的 `bin/nte-core.exe` 与原生组件整包中的 Core 是同一交付文件。
程序哈希、文件大小、配套 DLL、能力和来源摘要以
[原生组件清单](../native-capture/component-bundle.json) 为唯一事实源。

Core 保留抓包和原生入口，负责协议校验、业务数据转换与原始证据保存。
公共事件中的未知 payload 原样保留，不在 Core 中解释 Buff 公式；普通事件不能成为 hit 状态基线。
查询基础值和聚合属性读数不自动证明逐击应用，完整传输不等于完整游戏事件覆盖。

构建、专项验证与实际游戏验收边界见 [Core 来源说明](../native-capture/core/SOURCE.md)。
许可证与来源见 [SOURCE.md](SOURCE.md)。组件晋升和本机部署不代表公开发布或真实游戏验收；不改写历史战报。
