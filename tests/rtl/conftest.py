"""Skip the cocotb RTL cosimulations when Icarus Verilog is not installed."""
import os
import shutil

import pytest


@pytest.fixture(autouse=True)
def _require_icarus():
    if os.getenv("SIM", "icarus") == "icarus" and shutil.which("iverilog") is None:
        pytest.skip("Icarus Verilog (iverilog) is not on PATH")
