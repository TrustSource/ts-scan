"""
TrustSource Core Library

This package contains shared components that can be reused across
the TrustSource ecosystem (ts-scan, and other internal tools).
"""

__version__ = "1.0.0"

from .model import (
    DependencyScan,
    Dependency,
    LicenseKind,
    License,
    CryptoAlgorithm,
    dump_scans,
    load_scans,
)

from . import spdx
from . import cyclonedx

__all__ = [
    'DependencyScan',
    'Dependency',
    'LicenseKind',
    'License',
    'CryptoAlgorithm',
    'dump_scans',
    'load_scans',
    'spdx',
    'cyclonedx',
]
