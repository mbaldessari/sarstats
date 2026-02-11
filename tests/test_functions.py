"""
Test unit for sarstats
"""
import os
import os.path
import sys

import pytest

from sar_grapher import SarGrapher
from sar_stats import SarStats

SAR_FILES_DIR = "sar-files"


def _discover_sar_files():
    """Discover all SAR files in the test data directory."""
    sar_base = os.path.join(sys.modules["tests"].__file__)
    sar_dir = os.path.join(os.path.abspath(os.path.dirname(sar_base)), SAR_FILES_DIR)
    files = []
    for root, dirs, filenames in os.walk(sar_dir):
        for fname in filenames:
            if fname.lower().strip().startswith("sar"):
                files.append(os.path.join(root, fname))
    return sorted(files)


@pytest.mark.parametrize("sar_file", _discover_sar_files(), ids=lambda f: os.path.basename(f))
def test_sar_parse_and_graph(sar_file, tmp_path):
    """Parse a SAR file and generate a PDF report."""
    grapher = SarGrapher([sar_file])
    stats = SarStats(grapher)

    out = str(tmp_path / "output.pdf")
    stats.graph([sar_file], [], out, threaded=True)

    assert os.path.exists(out), f"PDF was not created for {sar_file}"
    assert os.path.getsize(out) > 0, f"PDF is empty for {sar_file}"

    grapher.close()
