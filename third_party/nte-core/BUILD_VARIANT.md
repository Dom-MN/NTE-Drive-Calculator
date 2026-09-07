# NTE Core - Windows x64

This build provides the capture component's JSON-RPC stdio interface. The exact source revision,
build command, license, toolchain and binary hashes are recorded in [SOURCE.md](SOURCE.md).
Read [CLI_PROTOCOL.md](CLI_PROTOCOL.md) before integrating.

The included fixes constrain weave attribution by its declared source role, preserve distinct
same-frame hits, prevent duplicate settlement, and isolate the inventory fragment clock from
unsupported Bunch modes. Supported empty packets still expire fragments, independent raw records
keep their existing handling, and the 96-packet window is unchanged.

Focused regressions, production capture replay, Release build, UPX integrity, deployed version/hash
checks and installer content verification passed. Truncated capture tails remain input errors.
Live login synchronization, the capture component's full suite and actual installation acceptance
remain unverified. See [COMPONENT.md](COMPONENT.md) for the integration boundary.
