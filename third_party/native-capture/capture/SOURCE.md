# Native component source

Source repository: https://github.com/kongbaiz/UETools-NTE

Base commit: 13320c0e44dfa203170309255e67553201abf901. Modified working-tree input SHA-256: 2db91c9bf9784854fa19aa401add9a7206541412e15136f5fd3a228d9a2d69f2. The base alone does not reproduce this build.

This dated test candidate removes the fallback whole-row HUD plate and border, retaining skill icons, cooldown masks and values while native buttons initialize or are unavailable. It also queues HUD Info messages in a bounded plugin-owned buffer. The existing plugin-management thread performs output, retaining the original timestamp, thread and source location. Overflow is counted; teardown quiesces producers before draining. Combat adds in-memory timing for clock identity checks, function validation and individual pause queries without changing sampling or pause semantics.

Five Release x64 DLLs use selected function protection. Four plugin signatures bind final bytes. The host, plugins and signatures are delivered as one checked set with the existing Core and Loader. No game deployment was performed.

Twenty-five focused HUD cases passed, including compiled values, geometry, owner construction, code-contract, queue and timing fixtures. The exact protected and signed set passed isolated loading, altered-signature rejection, dependency checks, independent HUD lifecycle, trace completion and SDK-not-ready refusal. The companion Core hash matches the existing Calc bundle.

Game performance and acquisition acceptance are not run for this candidate. No reduction in long stalls is claimed. Old runtime or antivirus observations are not validation of these newly built DLLs.
