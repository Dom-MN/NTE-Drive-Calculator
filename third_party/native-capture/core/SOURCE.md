# Native Core component source

Source base commit: `cfa384983304e8a8e20dc4ad050a2f6ce6f348e7` in the private integration repository. The actual build also includes the two-file inventory packet fix from the independent working tree. Its staged binary patch SHA-256 is `258174e329130b933b6ec4210a0847a9fda579a1eca8c165e6497cd69a466a6b`; the base commit alone does not reproduce this executable. Private source and patch are not included in the Calc distribution.

Built as the Windows x64 `nte-core` CLI with `--locked --release --no-default-features --features cli` and remapped build paths. Protocol 1 and Core version 0.4.4 are unchanged. The build retains `capture_wait_v1` and `buff_snapshot_v1` while adding the inventory packet fix. It is paired with the declared native capture bundle, not a replacement for its DLL or Loader.

Rust library checks: 865 passed, 11 ignored. Direct executable handshake and idle Buff query were verified; real-game capture and native-pipe acceptance for this exact binary remain pending. Existing licenses and protocol apply.
