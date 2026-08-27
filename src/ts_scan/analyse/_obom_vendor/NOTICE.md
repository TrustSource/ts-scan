# Vendored code notice

`checkov/` in this directory is a trimmed subset of
[bridgecrewio/checkov](https://github.com/bridgecrewio/checkov), licensed
under the [Apache License 2.0](checkov/LICENSE) (included alongside this
notice, unmodified). Checkov's copyright is retained by Bridgecrew/Prisma
Cloud (Palo Alto Networks) and its contributors.

## Provenance

- Upstream source: `bridgecrewio/checkov`, version `3.3.15`
  (`checkov/version.py`), commit `2137e91a69bbcf73d9c672073a049ec4b48f85ff`
  (`upstream/main` on the fork used, 2026-08-27).
- Trimmed and adapted via
  [`jthDEV/checkov`](https://github.com/jthDEV/checkov), branch
  `feature/scan2graph-extraction` (`scan2graph/vendor_src/`), for use by
  `ts_scan.analyse.obom`.

## What was changed from upstream (Apache-2.0 §4(b))

- **Reduced file set.** Only the ~25 files that
  `checkov.cloudformation.graph_manager` / `checkov.terraform.graph_manager`
  / `checkov.common.graph.db_connectors.networkx` genuinely need at runtime
  are included, out of the full checkov source tree.
- **23 stub modules added**, replacing subsystems that are imported
  somewhere on that path but never called by it (check-registry,
  Bridgecrew-platform-integration, reporting, external-check-verification,
  module-download-over-network, and SCA/SAST output code). Each stub is a
  short, self-documenting file: a module-level `__getattr__` returning a
  `unittest.mock.MagicMock` for any attribute, with `__all__ = []` so
  checkov's own `from x import *` package-init pattern is a no-op. Their
  exact paths are listed in `jthDEV/checkov`'s
  `scan2graph/vendor_src/checkov/**/__init__.py` (docstring-tagged) and in
  that repo's commit history.
- **One real code change:** `common/util/json_utils.py`. Its
  `CustomJSONEncoder` is genuinely used (Terraform variable-rendering
  serialization) and could not be stubbed, but its `default()` method
  special-cased four types from stubbed subsystems
  (`Severity`, `ImageDetails`, SAST `MatchMetadata`/`DataFlow`/
  `MatchLocation`/`Point`, `PotentialSecret`) purely via `isinstance()`
  checks. Replaced those four imports with local, unreachable sentinel
  classes of the same names — the branches become dead code (no object our
  code path produces is ever an instance of them) rather than a crash.
- No other line-level edits to files that were kept.

## Why vendored instead of `pip install checkov`

See the module docstring in `ts_scan/analyse/obom.py` for the full
reasoning: the full `checkov` PyPI distribution's declared dependencies
conflict with ts-scan's own (`cyclonedx-python-lib`, `packageurl-python`,
`importlib-metadata`), and none of that weight turned out to be needed for
graph-building specifically.

## Re-syncing with upstream checkov

If checkov's graph-builder internals change upstream in a way this vendored
copy needs, re-run the trimming process from `jthDEV/checkov`'s
`feature/scan2graph-extraction` branch against the new upstream commit
(iteratively import `checkov.cloudformation.graph_manager` /
`checkov.terraform.graph_manager` from a fresh copy, copy in whatever's
reported missing, re-verify against `scan2graph/testdata/`) rather than
hand-patching this copy in place.
