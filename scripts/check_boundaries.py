from __future__ import annotations

import argparse
import subprocess
import sys


BOUNDARY_GATES = {
    "v0.6.3": [
        "tests/test_signal_contract.py",
        "tests/test_architectural_boundaries.py::TestAdapterBoundary::test_rsi_engine_has_no_source_conditionals",
        "tests/test_architectural_boundaries.py::TestAdapterBoundary::test_polymarket_adapter_emits_signal_contracts",
        "tests/test_architectural_boundaries.py::TestAdapterBoundary::test_no_raw_dict_reaches_rsi_engine",
    ],
    "v0.6.4": [
        "tests/test_architectural_boundaries.py::TestAdapterBoundary::test_kalshi_adapter_emits_signal_contracts",
        "tests/test_architectural_boundaries.py::TestAdapterBoundary::test_manifold_adapter_provenance_is_archive_only",
    ],
    "v0.6.6": [
        "tests/test_architectural_boundaries.py::TestAdapterBoundary::test_signal_registry_deduplicates_cross_source",
    ],
    "v0.7.0": [
        "tests/test_architectural_boundaries.py::TestAdapterBoundary::test_becker_calibration_only_modifies_calibrated_field",
        "tests/test_api_contract.py::TestAPIContract::test_promotion_changes_rsi_from_unity",
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run milestone boundary gates.")
    parser.add_argument("tag", choices=sorted(BOUNDARY_GATES))
    args = parser.parse_args()

    command = [sys.executable, "-m", "pytest", "-v", *BOUNDARY_GATES[args.tag]]
    completed = subprocess.run(command)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
