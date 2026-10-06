# Native component source

Source repository: https://github.com/kongbaiz/UETools-NTE

Base commit: bf7ffc7f06f1766e008c6a974d94c4fd4aa310d9. Modified working-tree input SHA-256: 65f0ed08f5117545c9424952cbfb6d88ddef6ecdb8a4563538a0faa8ad96aba7. The base alone does not reproduce this build.

Reviewed upstream reference: c6b30a17a46f0725ce4b4fc34cbdee96bca233b1. Selected changes include bounded HUD lookup and layout batches, native-mode definition-only skill reads, owned-event exclusion, batched idle Hook retirement, and optional performance spans and window summaries. The prior guarded-root, event empty-slot, skill-category and awakening-definition changes are retained.

The branch retains separate Combat/HUD plugins, native avatar-tree mounting, construction-context tracking and native-only wait states. Performance retains seven service kinds, Calc control and leases, and complete raw records by default. Diagnostic compaction requires explicit opt-in. Developer MCP tools and training controls are not included in this five-DLL bundle.

Five Release x64 DLLs use selected-function protection and four final-byte signatures. Targeted HUD fixtures, performance channel accounting, exact-DLL raw/diagnostic output and unload tests, and the signed-host dependency/tamper checks passed. Core and Loader are reused unchanged. No game deployment or real-game acceptance was performed; fixture counts are not frame-rate measurements.
