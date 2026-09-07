# nte-core 对应源码

当前 `bin/nte-core.exe` 对应 `ternary-chen/nte-dps-toolkit` 的采集修复整合源码。

- 上游项目：<https://github.com/kongbaiz/nte-dps-toolkit>
- Fork：<https://github.com/ternary-chen/nte-dps-toolkit>
- 二进制版本：`0.4.4`；CLI 协议 / 数据版本：`1` / `1`；战斗读取契约：`5`
- 对应源码：[08ed371add4e5b189fdadee61965bbe7181524bd](https://github.com/ternary-chen/nte-dps-toolkit/commit/08ed371add4e5b189fdadee61965bbe7181524bd)
- 整合分支：`codex/integrate-capture-fixes`；包含覆纹归属、同帧逐击身份、结算去重与背包分片时钟修复
- 构建日期：`2026-09-07`；工具链：Rust `1.98.0-x86_64-pc-windows-msvc`
- 构建命令：`cargo build --release --locked --bin nte-core --no-default-features --features cli`
- 未压缩 SHA-256：`cc26755e11f2c32e08fac5668b0edd3cf821791ec6b8e7ca087f57b868a68c19`
- 压缩：UPX 5.2.0 `--best --lzma`；压缩后大小：`650240` 字节
- 压缩后 SHA-256：`6de93fbd8ec98b65ebf610acffeb24647cb080c91d90ae266a93f556d1e09e1d`
- 许可证：本目录 `LICENSE`（AGPL-3.0）

上述提交完整记录生成该二进制的源码，不依赖未提交补丁。再分发时保留对应源码入口与许可证材料。
