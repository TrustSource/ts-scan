# ts-scan-core

TrustSource Core Library - shared components for the ts-scan ecosystem.

## Installation

### From Git (for internal projects)

```bash
pip install "git+https://github.com/TrustSource/ts-scan.git#subdirectory=packages/ts_scan_core"
```

### For Development

```bash
cd packages/ts_scan_core
pip install -e .
```

## Usage

```python
from ts_scan_core import DependencyScan, Dependency, License
from ts_scan_core import dump_scans, load_scans
from ts_scan_core import spdx, cyclonedx
```
