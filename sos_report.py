# Note: This is just a temporary class
# I am working on a more complete sosreport parsing class
# which will supersede this one

from pathlib import Path
from typing import Any, Optional
import re

from dateutil import parser as dateparser
from dateutil.relativedelta import relativedelta

from sos_utils import natural_sort_key


class SosReport:
    """Parser for sosreport data."""

    def __init__(self, path: str) -> None:
        """Initialize SosReport.

        Args:
            path: Path to the sosreport directory.

        Raises:
            FileNotFoundError: If the path doesn't exist or isn't a valid sosreport.
        """
        self.path = Path(path)
        if not self.path.is_dir():
            raise FileNotFoundError(f"{path} does not exist")

        sospath = self.path / "sos_reports"
        if not sospath.exists():
            raise FileNotFoundError(f"{sospath} does not exist")

        self.redhatrelease: Optional[str] = None
        self.packages: list[str] = []
        self.interrupts: dict[str, dict[str, Any]] = {}
        self.networking: dict[str, dict[str, str]] = {}
        self.reboots: dict[int, dict[str, Any]] = {}
        self.nr_cpus: int = 0

    def _parse_network_ethtool(self) -> None:
        """Parse ethtool output files for network interface info."""
        sos_networking = self.path / "sos_commands" / "networking"
        if not sos_networking.exists():
            return

        for filepath in sos_networking.iterdir():
            if not filepath.name.startswith("ethtool_-i_"):
                continue

            dev = filepath.name.split("_")[2]
            self.networking[dev] = {}
            with filepath.open() as f:
                for line in f:
                    line = line.strip()
                    if len(line) <= 1 or ": " not in line:
                        continue
                    label, value = line.split(": ", 1)
                    self.networking[dev][label] = value

    def _parse_network(self) -> None:
        """Parse network configuration."""
        self._parse_network_ethtool()

    def _parse_int_entry(self, fields: list[str], line: str) -> dict[str, Any]:
        """Parse a single interrupt entry."""
        result: dict[str, Any] = {"cpu": [int(fields[0])]}
        nr_fields = len(fields)

        if nr_fields >= self.nr_cpus:
            result["cpu"] += [int(i) for i in fields[1: self.nr_cpus]]
            if nr_fields > self.nr_cpus:
                result["type"] = fields[self.nr_cpus]
                if nr_fields > self.nr_cpus + 1:
                    field_idx = line.index(fields[self.nr_cpus + 1])
                    result["users"] = [a.strip() for a in line[field_idx:].split(",")]
                else:
                    result["users"] = []
        return result

    def _parse_interrupts(self) -> None:
        """Parse /proc/interrupts to associate interrupt numbers with devices."""
        intr_file = self.path / "proc" / "interrupts"
        if not intr_file.exists():
            return

        with intr_file.open() as f:
            for line in f:
                line = line.strip()
                fields = line.split()
                if not fields:
                    continue
                if fields[0][:3] == "CPU":
                    self.nr_cpus = len(fields)
                    continue
                irq = fields[0].strip(":")
                self.interrupts[irq] = self._parse_int_entry(fields[1:], line)

    def _parse_reboots(self) -> None:
        """Parse /var/log/messages to find machine reboot times.

        Parses messages* files to find lines like:
        'Dec  4 11:02:05 hostname kernel: Linux version 2.6.32...'
        """
        messages_dir = self.path / "var" / "log"
        if not messages_dir.exists():
            return

        reboot_re = re.compile(r".*kernel: Linux version.*$")
        files = [f for f in messages_dir.iterdir() if f.name.startswith("messages")]

        counter = 0
        for filepath in sorted(
            files, key=lambda x: natural_sort_key(x.name), reverse=True
        ):
            prev_month: Optional[int] = None
            with filepath.open(errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not reboot_re.match(line):
                        continue

                    tokens = line.split()[0:3]
                    d = dateparser.parse(" ".join(tokens))
                    if d.month == 1 and prev_month == 12:
                        # Year crossover - adjust previous dates
                        for j in self.reboots:
                            if "decremented" not in self.reboots[j]:
                                t = self.reboots[j]["date"]
                                self.reboots[j]["date"] = t - relativedelta(years=1)
                                self.reboots[j]["decremented"] = True
                    prev_month = d.month
                    self.reboots[counter] = {
                        "date": d,
                        "file": str(filepath),
                    }
                    counter += 1

    def parse(self) -> None:
        """Parse all sosreport data."""
        release_file = self.path / "etc" / "redhat-release"
        if release_file.exists():
            self.redhatrelease = release_file.read_text().strip()
        self._parse_interrupts()
        self._parse_network()
        self._parse_reboots()


if __name__ == "__main__":
    sosreport = SosReport("./demosos")
    sosreport.parse()
    for i in sosreport.reboots:
        print(f"{i} - {sosreport.reboots[i]}")
