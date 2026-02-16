"""
Test unit for sarstats
"""
from pathlib import Path

import pytest

from sar_grapher import SarGrapher
from sar_stats import SarStats

SAR_DIR = Path(__file__).parent / "sar-files"


def _discover_sar_files():
    """Discover all SAR files in the test data directory."""
    return sorted(
        str(f) for f in SAR_DIR.rglob("*")
        if f.is_file() and f.name.lower().strip().startswith("sar")
    )


@pytest.mark.parametrize("sar_file", _discover_sar_files(), ids=lambda f: Path(f).name)
def test_sar_parse_and_graph(sar_file, tmp_path):
    """Parse a SAR file and generate a PDF report."""
    grapher = SarGrapher([sar_file])
    stats = SarStats(grapher)

    out = str(tmp_path / "output.pdf")
    stats.graph([sar_file], [], out, threaded=True)

    out_path = Path(out)
    assert out_path.exists(), f"PDF was not created for {sar_file}"
    assert out_path.stat().st_size > 0, f"PDF is empty for {sar_file}"

    grapher.close()
