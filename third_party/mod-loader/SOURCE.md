# User-mode Loader source

Based on the existing nte-dps-toolkit Loader; base commit b58a86589563fa06e91be3b8807e5b13704a206c, working-tree input SHA-256 eea80ee79d39894dc8223e35f68f7492040ded025471eda2b674530a5089a0cc. The base alone does not reproduce this build.

Adds nte_calc_host_v1 identity validation for the integrated Calc host while preserving the legacy developer host Platform check and independent capture-runtime identity. Uses the existing standard LoadLibrary path, UAC, stop event and owner PID; no kernel driver or security-policy changes.

Release EXE and embedded shim are built together. Exact embedded-shim capability and host loading passed in an isolated ordinary process; actual launcher/game integration remains unverified. AGPL-3.0 and bundled dependency notices remain applicable.
