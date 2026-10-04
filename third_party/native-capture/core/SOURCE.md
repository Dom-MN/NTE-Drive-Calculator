# Native Core component source

Source base commit: `cfa384983304e8a8e20dc4ad050a2f6ce6f348e7` in the private integration repository. The actual build includes the low-risk inventory packet fix and the restored 1042 character/equipment-plan resources in the linked Core worktree. Combined source diff SHA-256: `7fc554c54d007c290b06b639f8572bbac33067d0e758b9a67deabd6f2e56e3e7`. The base commit alone does not reproduce this executable. Private source and patch are not included in the Calc distribution.

Built as the Windows x64 `nte-core` CLI with `--locked --release --no-default-features --features cli` and remapped build paths. Protocol 1 and Core version 0.4.4 are unchanged. The binary keeps `capture_wait_v1` and `buff_snapshot_v1` while retaining the packet fix. It is paired with the declared native capture DLL and Loader.

The exact binary passed packet-mode handshake and capture-environment detection. In the same live game session, the prior Core returned `NATIVE_MAPPING_UNSUPPORTED` on inventory projection; this Core returned a complete 355/355 inventory projection. Full packet capture, character field synchronization, installation upgrade and release validation remain pending. Existing licenses and protocol apply.
