#!/usr/bin/env python3
"""Backward-compatible WNBA entrypoint for the generic pbpstats runner."""

from __future__ import annotations

from pbpstats_job_runner import BundleConfig, DEFAULT_BUNDLE_PATH, DEFAULT_OUTPUT_ROOT, main, run_bundle

__all__ = [
    "BundleConfig",
    "DEFAULT_BUNDLE_PATH",
    "DEFAULT_OUTPUT_ROOT",
    "main",
    "run_bundle",
]


if __name__ == "__main__":
    main()
