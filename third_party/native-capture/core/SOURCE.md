# Native Core component source

This local Calc trial candidate was built from private integration commit
`b7b24d3cba264b1f10e3e6aa98a078e6758b5df7` on `dev/hxwd`, plus uncommitted
Core/catalog changes. The SHA-256 of `git diff --binary -- Cargo.toml Cargo.lock
src res` at build time is
`e1a6307554ff0beb843b40f65c0acd3596c7ee98f691222d06e3790ad23a0e36`.
The base commit alone does not reproduce this executable. Private source and
patch are not included in the Calc component package.

Built for Windows x64 with
`cargo build --locked --release --no-default-features --features cli --bin nte-core`.
The build process used `--remap-path-prefix` for the workspace and user paths.
Core version 0.4.4 and JSON-RPC protocol 1 are unchanged. The executable
SHA-256 is `63b9f7098ed7d35ba030ef422961611984d20503453b4db2c30cbfc14d70ee48`.

The packet entry now advertises `inventory_observed_items_v1` and supports
`inventory.get_observed_items` for current-session, incomplete item quantities.
These observations are not a complete inventory or the native all-items archive.
The existing 1057 catalog candidate and native equipment batch support remain
in this build; the capture DLL and D3D proxy were not rebuilt or changed here.

Release build and a no-game stdio handshake passed: protocol 1 advertised the
new capability, and the new query returned `INVENTORY_ITEMS_NOT_READY` before
capture. The executable was checked for absolute developer paths and common
credential prefixes. Packet capture, material counts, native pipe behavior and
game acceptance for this exact candidate still need live validation. This is
a local `main.py` trial candidate, not a promoted release.
