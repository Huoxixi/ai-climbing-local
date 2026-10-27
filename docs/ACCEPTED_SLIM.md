# Accepted source slimming release

Release 0.1.20-local.20261027 synchronizes the six-round accepted behavior-preserving cleanup. Backend responsibilities are split into contracts, rendering, media, records, test video catalog and queue modules; the local replay page shares metadata, labels and reactive state. The public application retains its existing 视频复盘 title and local-only entry.

The original development acceptance passed 210 frontend tests and six browser cases. Its expanded backend baseline and final source both passed 268/270 with the same two pre-existing failures (final-frame hold color expectation and unsupported-container response code). This release does not claim those failures were fixed or the entire backend is green. Release-specific checks cover the reviewed public source, build, installer manifest and packaging scope.

The accepted 19.2 algorithms, raw observations, model weights and user data remain unchanged. Rejected occlusion hold, identity heads, PoseWarper and other failed candidates remain excluded. No further optimization round, accuracy improvement, faster startup or smaller installer is claimed. Existing records are not recomputed.
