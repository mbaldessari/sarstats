# SarParser.py - sar(1) graphs parsing class
# Copyright (C) 2012  Ray Dassen
#               2013  Ray Dassen, Michele Baldessari
#               2014  Michele Baldessari
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA  02110-1301, USA.

"""
sar(1) reports parsing and querying.

sar(1) provides system activity reports that are useful in the analysis of
system performance issues. This module provides a class that can parse sar
reports and that allows for easy querying of the data contained in them. This
code has been tested with a variety of sar reports, in particular ones from Red
Hat Enterprise Linux versions 3 through 6 and from Fedora 20
"""

from enum import Enum, auto
from functools import cached_property
from itertools import pairwise
from pathlib import Path
import datetime
import re

import dateutil
import numpy

import sar_metadata
from sos_report import SosReport
from sos_utils import natural_sort_key

# regex of the sar column containing the time of the measurement
TIMESTAMP_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})\s?(AM|PM)?")

# Regex to parse the first line of a SAR report (kernel, version, hostname, date)
FIRST_LINE_RE = re.compile(r"""(?x)
    ^(\S+)\s+                 # Kernel name (uname -s)
    (\S+)\s+                  # Kernel release (uname -r)
    \((\S+)\)\s+              # Hostname
    ((?:\d{4}-\d{2}-\d{2})|   # Date in YYYY-MM-DD format
     (?:\d{2}/\d{2}/\d{2,4})) #      in MM/DD/(YY)YY format
    .*$                       # Remainder, ignored
    """)

# Pre-compiled regexes for line parsing
_EMPTY_LINE_RE = re.compile(r"^\s*$")
_AVERAGE_LINE_RE = re.compile(r"^Average|^Summary")
_COLUMN_HEADERS_RE = re.compile(
    r"""(?x)
    ^("""
    + sar_metadata.TIMESTAMP_RE
    + r""")\s+
    (
        # Time to be strict - we don't want to
        # accidentally end up recognising lines of
        # data as lines defining column structure
        # Any field that has numbers inside of it needs
        # to be explicitly ORed
        (?:
            (?:[a-zA-Z1360%/_-]+    # No numbers (except for IPv6 and the %scpu-{10,60,300})
            |                       # and except...
            i\d{3}/s
            |
            i2big6/s
            |
            ipck2b6/s
            |
            opck2b6/s
            |
            ldavg-\d+
            )
            \s*
        )+
    )       # Column headers, all matched as one group
    \s*$
    """
)
_DATE_FORMAT_RE = re.compile(r"(\d{2})/(\d{2})/(\d{2,4})")


class ParseState(Enum):
    """States for the SAR file parser state machine."""

    START = auto()
    AFTER_FIRST_LINE = auto()
    AFTER_EMPTY_LINE = auto()
    SKIP_UNTIL_EOT = auto()
    TABLE_START = auto()
    TABLE_ROW = auto()
    TABLE_END = auto()


def _empty_line(line: str) -> re.Match | None:
    """Parse an empty line."""
    return _EMPTY_LINE_RE.search(line)


def _average_line(line: str) -> re.Match | None:
    """Parse a line starting with 'Average:' or 'Summary:'."""
    return _AVERAGE_LINE_RE.search(line)


def canonicalise_timestamp(date: tuple[int, int, int], ts: str) -> datetime.datetime:
    """Convert sar timestamp to datetime object.

    Sar files start with a date string (yyyy-mm-dd) and a series of lines
    starting with the time. Given the initial sar datetime date object as
    base and the time string column, return a full datetime object.

    Args:
        date: Tuple of (year, month, day).
        ts: Time string from sar file.

    Returns:
        A datetime object combining the date and parsed time.

    Raises:
        ValueError: If the timestamp cannot be parsed.
    """
    matches = TIMESTAMP_RE.search(ts)
    if matches:
        hours, minutes, seconds, meridiem = matches.groups()
        hours = int(hours)
        minutes = int(minutes)
        seconds = int(seconds)
        if meridiem:
            if meridiem == "AM" and hours == 12:
                hours = 0
            if meridiem == "PM" and hours < 12:
                hours += 12
        if hours == 24:
            hours = 0
        return datetime.datetime(date[0], date[1], date[2], hours, minutes, seconds)
    else:
        raise ValueError(f"canonicalise_timestamp error: {ts}")


class SarParser:
    """Class for parsing a sar report and querying its data
    Data structure representing the sar report's contents.
    Main _data structure is a dictionary of dictionaries.
    First dictionary index is a timestamp (datetime class)
    and the second index is the graph's type:
    '%commit', '%memused', '%swpcad', '%swpused', '%vmeff'
    'CPU#0#%idle', 'CPU#0#%iowait', 'CPU#0#%irq', 'CPU#0#%nice'
    'CPU#0#%soft', 'CPU#0#%sys', 'CPU#0#%usr',..."""

    def __init__(
        self,
        fnames: list[str],
        starttime: list[str] | None = None,
        endtime: list[str] | None = None,
    ):
        """Initialize SarParser.

        Args:
            fnames: List of SAR files to be parsed.
            starttime: Optional start time filter.
            endtime: Optional end time filter.
        """
        self._data: dict[datetime.datetime, dict[str, float | str | None]] = {}
        self._categories: dict[str, str] = {}
        self._files = fnames
        self.kernel: str | None = None
        self.version: str | None = None
        self.hostname: str | None = None
        self.sample_frequency: float | None = None
        self._date: tuple[int, int, int] | None = None
        self._olddate: tuple[int, int, int] | None = None
        self._prev_timestamp: datetime.datetime | None = None
        self.starttime: datetime.datetime | None = None
        self.endtime: datetime.datetime | None = None

        if starttime:
            self.starttime = dateutil.parser.parse(starttime[0])
        if endtime:
            self.endtime = dateutil.parser.parse(endtime[0])

        self._linecount = 0
        self._duplicate_timestamps: set[int] = set()

        # Calculate sosreport base directory
        abspath = Path(fnames[0]).resolve()
        sosreport_base = abspath if abspath.is_dir() else abspath.parents[3]

        self.sosreport: SosReport | None = None
        try:
            self.sosreport = SosReport(str(sosreport_base))
            self.sosreport.parse()
        except (FileNotFoundError, OSError):
            # SosReport not available or not parseable, continue without it
            pass

    @cached_property
    def _first_timestamp(self) -> datetime.datetime:
        """Return the first timestamp in the data (cached for efficiency)."""
        return next(iter(self._data))

    def _prune_data(self) -> None:
        """Remove graph keys that have 0 values in all timestamps.

        Also ensures all timestamps have the same keys (missing keys set to None)
        and prunes orphaned categories.
        """
        # Collect all keys across all timestamps
        all_keys = {
            key for timestamp_data in self._data.values() for key in timestamp_data
        }

        # Find keys that are 0 in all timestamps
        keys_to_remove = {
            key
            for key in all_keys
            if all(self._data[t].get(key) == 0 for t in self._data)
        }

        # Remove zero-only keys from all timestamps
        for timestamp_data in self._data.values():
            for key in keys_to_remove:
                timestamp_data.pop(key, None)

        # Recalculate all_keys after removal
        all_keys = {
            key for timestamp_data in self._data.values() for key in timestamp_data
        }

        # Ensure all timestamps have the same keys (set missing to None)
        for timestamp_data in self._data.values():
            for key in all_keys:
                if key not in timestamp_data:
                    timestamp_data[key] = None

        # Prune orphaned categories
        self._categories = {
            key: cat for key, cat in self._categories.items() if key in all_keys
        }

    def _parse_first_line(self, line: str) -> None:
        """Parse the first line of a SAR report to extract metadata."""
        matches = FIRST_LINE_RE.search(line)
        if matches:
            self.kernel, self.version, self.hostname, tmpdate = matches.groups()
        else:
            raise ValueError(
                f'Line {self._linecount}: "{line}" failed to parse as a first line'
            )

        # Convert MM/DD/YY(YY) format to YYYY-MM-DD
        date_matches = _DATE_FORMAT_RE.search(tmpdate)
        if date_matches:
            mm, dd, yyyy = date_matches.groups()
            if len(yyyy) == 2:
                yyyy = "20" + yyyy
            tmpdate = f"{yyyy}-{mm}-{dd}"

        date_parts = list(map(int, tmpdate.split("-")))
        self._date = (date_parts[0], date_parts[1], date_parts[2])

    def _column_headers(self, line: str) -> tuple[str | None, list[str] | None]:
        """Parse the line as a set of column headings."""
        matches = _COLUMN_HEADERS_RE.search(line)
        if matches:
            hdrs = [h for h in matches.group(2).split(" ") if h]
            return matches.group(1), hdrs
        return None, None

    def _do_start(self, line: str) -> None:
        """Actions for the 'start' state of the parser."""
        self._parse_first_line(line)

    def _column_type_regexp(self, hdr: str) -> str | None:
        """Get the regular expression to match entries under a particular header."""
        return sar_metadata.get_regexp(hdr)

    def _valid_column_header_name(self, hdr: str) -> bool:
        """Check if hdr is a valid column name."""
        return self._column_type_regexp(hdr) is not None

    def _build_data_line_regexp(self, headers: list[str]) -> str:
        """Build a regular expression to match data lines for given headers."""
        regexp = rf"^({sar_metadata.TIMESTAMP_RE})"
        for hdr in headers:
            hre = self._column_type_regexp(hdr)
            if hre is None:
                raise ValueError(
                    f'Line {self._linecount}: column header "{hdr}" unknown'
                )
            regexp += rf"\s+({hre})"
        regexp += r"\s*$"
        return regexp

    def _record_data(
        self, headers: list[str], matches: re.Match
    ) -> datetime.datetime | None:
        """Record a parsed line of data."""
        timestamp = canonicalise_timestamp(self._date, matches.group(1))

        # Skip if timestamp is outside user-defined limits
        if self.starttime and timestamp < self.starttime:
            return None
        if self.endtime and timestamp > self.endtime:
            return None

        # Handle day crossover
        if self._prev_timestamp is not None:
            if self._prev_timestamp.hour == 23 and timestamp.hour == 0:
                nextday = timestamp + datetime.timedelta(days=1)
                self._olddate = self._date
                self._date = (nextday.year, nextday.month, nextday.day)
                timestamp = canonicalise_timestamp(self._date, matches.group(1))
            elif timestamp < self._prev_timestamp:
                raise ValueError(
                    f"Time going backwards: {timestamp} "
                    f"- Prev timestamp: {self._prev_timestamp} -> {self._linecount}"
                )
        self._prev_timestamp = timestamp

        if timestamp not in self._data:
            self._data[timestamp] = {}

        # Find the index column position
        column = next(
            (i for i, h in enumerate(headers) if h in sar_metadata.INDEX_COLUMN),
            len(headers),
        )

        # Simple case: 2D data - all columns are simple data types
        if column >= len(headers):
            previous = ""
            for counter, header in enumerate(headers):
                key = header
                # HACK: retrans/s can appear in ETCP and NFS, rename ETCP's
                if key == "retrans/s" and previous == "estres/s":
                    key = "retrant/s"
                if key in self._data[timestamp]:
                    self._duplicate_timestamps.add(self._linecount)

                try:
                    value: float | str = float(matches.group(counter + 2))
                except ValueError:
                    value = matches.group(counter + 2)
                self._data[timestamp][key] = value
                self._categories[key] = sar_metadata.get_category(key)
                previous = key
            return timestamp

        # Complex case: 3D data - indexed by CPU number, device name, etc.
        indexcol = headers[column]
        indexval = matches.group(column + 2)
        if indexval in ("all", "Summary"):
            return timestamp

        for counter, header in enumerate(headers):
            if counter == column:
                continue

            key = f"{indexcol}#{indexval}#{header}"
            if key in self._data[timestamp]:
                self._duplicate_timestamps.add(self._linecount)

            try:
                value = float(matches.group(counter + 2))
            except ValueError:
                value = matches.group(counter + 2)
            self._data[timestamp][key] = value
            self._categories[key] = sar_metadata.get_category(key)

        return timestamp

    def parse(self, skip_tables: list[str] | None = None) -> None:
        """Parse the sar files.

        This method populates the _data structure using a line-by-line
        state machine parser.

        Args:
            skip_tables: List of table names to skip (default: ["BUS"]).
        """
        if skip_tables is None:
            skip_tables = ["BUS"]

        for file_name in self._files:
            self._prev_timestamp = None
            state = ParseState.START
            headers: list[str] | None = None
            pattern: re.Pattern | None = None
            self.cur_file = file_name

            with open(file_name, "r") as fd:
                for line in fd:
                    self._linecount += 1
                    line = line.rstrip("\n")

                    if state == ParseState.START:
                        self._do_start(line)
                        state = ParseState.AFTER_FIRST_LINE
                        continue

                    if state == ParseState.AFTER_FIRST_LINE:
                        if not _empty_line(line):
                            raise ValueError(
                                f"Line {self._linecount}: expected empty line but got "
                                f'"{line}" instead'
                            )
                        state = ParseState.AFTER_EMPTY_LINE
                        continue

                    if state == ParseState.AFTER_EMPTY_LINE:
                        if _empty_line(line):
                            continue
                        if _average_line(line):
                            state = ParseState.TABLE_END
                            continue
                        state = ParseState.TABLE_START
                        # Continue processing this line

                    if state == ParseState.SKIP_UNTIL_EOT:
                        if _empty_line(line):
                            state = ParseState.AFTER_EMPTY_LINE
                        continue

                    if state == ParseState.TABLE_START:
                        if "LINUX RESTART" in line or line == "":
                            continue
                        timestamp_str, headers = self._column_headers(line)
                        # Reset date if we crossed a day in previous tables
                        if self._olddate:
                            self._date = self._olddate
                        if timestamp_str is None:
                            raise ValueError(
                                f"Line {self._linecount}: expected column header "
                                f'line but got "{line}" instead'
                            )
                        if headers == ["LINUX", "RESTART"]:
                            state = ParseState.TABLE_END
                            continue
                        if headers[0] in skip_tables:
                            state = ParseState.SKIP_UNTIL_EOT
                            print(f"Skipping: {headers}")
                            continue

                        try:
                            pattern = re.compile(self._build_data_line_regexp(headers))
                        except AssertionError as e:
                            raise ValueError(
                                f"Line {self._linecount}: exceeding python "
                                f"interpreter limit with regexp for "
                                f'this line "{line}"'
                            ) from e

                        self._prev_timestamp = None
                        state = ParseState.TABLE_ROW
                        continue

                    if state == ParseState.TABLE_ROW:
                        if _empty_line(line):
                            state = ParseState.AFTER_EMPTY_LINE
                            continue
                        if _average_line(line):
                            state = ParseState.TABLE_END
                            continue

                        matches = pattern.search(line)
                        if matches is None:
                            raise ValueError(
                                f"File: {self.cur_file} - Line {self._linecount}: "
                                f"headers: '{headers}', line: '{line}' "
                                f"regexp '{pattern.pattern}': failed to parse"
                            )
                        self._record_data(headers, matches)
                        continue

                    if state == ParseState.TABLE_END:
                        if _empty_line(line):
                            state = ParseState.AFTER_EMPTY_LINE
                            continue
                        if _average_line(line):
                            continue
                        raise ValueError(
                            f'Line {self._linecount}: "{line}" expecting end of table'
                        )

        # Remove unneeded columns
        self._prune_data()

        # Calculate sampling frequency
        time_diffs = [
            (t2 - t1).total_seconds()
            for t1, t2 in pairwise(self._data)
        ]
        self.sample_frequency = numpy.mean(time_diffs)

    def available_datasets(self) -> list[str]:
        """Return all available datasets."""
        return sorted(self._data[self._first_timestamp].keys())

    def match_datasets(self, regex: str) -> list[str]:
        """Return all datasets that match the given regex."""
        expression = re.compile(regex)
        return [
            key
            for key in sorted(self._data[self._first_timestamp].keys())
            if expression.match(key)
        ]

    def available_timestamps(self) -> list[datetime.datetime]:
        """Return all available timestamps."""
        return list(self._data.keys())

    def close(self) -> None:
        """Explicitly remove the main _data structure from memory."""
        del self._data

    def available_types(self, category: str) -> list[str]:
        """Return all graphs starting with the given category."""
        return [
            key
            for key in sorted(self._data[self._first_timestamp].keys())
            if key.startswith(category)
        ]

    def datanames_per_arg(self, category: str, per_key: bool = True) -> list[list[str]]:
        """Return a list of all combined graphs per category.

        Args:
            category: The category to filter by.
            per_key: If True, group by DEVICE/CPU/etc. Otherwise group by perf attribute.

        Returns:
            List of graph name lists grouped as specified.
        """
        graph_list = self.available_types(category)
        result: list[list[str]] = []

        if per_key:
            # Group by device/cpu key
            keys: set[str] = set()
            for graph in graph_list:
                parts = graph.split("#")
                if len(parts) != 3:
                    raise ValueError(
                        f"Error datanames_per_arg per_key={per_key}: {graph}"
                    )
                keys.add(parts[1])

            for key in sorted(keys, key=natural_sort_key):
                group = [
                    g
                    for g in graph_list
                    for parts in [g.split("#")]
                    if parts[1] == key and not parts[2].endswith("DEVICE")
                ]
                if group:
                    result.append(group)
        else:
            # Group by performance attribute
            perfs: set[str] = set()
            for graph in graph_list:
                parts = graph.split("#")
                if len(parts) != 3:
                    raise ValueError(
                        f"Error datanames_per_arg per_key={per_key}: {graph}"
                    )
                perfs.add(parts[2])

            for perf in sorted(perfs, key=natural_sort_key):
                group = [
                    g
                    for g in graph_list
                    for parts in [g.split("#")]
                    if parts[2] == perf and not perf.endswith("DEVICE")
                ]
                if group:
                    result.append(group)

        return result

    @cached_property
    def _all_data_types(self) -> set[str]:
        """Cached set of all available data types."""
        return {item for data in self._data.values() for item in data}

    def available_data_types(self) -> set[str]:
        """Return the set of all available data types."""
        return self._all_data_types

    def find_max(self, timestamp: datetime.datetime, datanames: list[str]) -> float:
        """Find the max Y value for the given datanames at the closest timestamp."""
        timestamps = list(self._data.keys())
        time_key = min(timestamps, key=lambda date: abs(timestamp - date))
        return max(
            (
                self._data[time_key][name]
                for name in datanames
                if self._data[time_key][name] is not None
            ),
            default=-1,
        )

    def find_data_gaps(self) -> list[tuple[datetime.datetime, datetime.datetime]]:
        """Find intervals where data collection was interrupted.

        A data gap is an interval longer than the collecting frequency
        that contains no data.

        Returns:
            List of (gap_start, gap_end) tuples.
        """
        freq = self.sample_frequency
        return [
            (t1, t2)
            for t1, t2 in pairwise(self._data)
            if (t2 - t1).total_seconds() > freq * 1.1
        ]


if __name__ == "__main__":
    raise SystemExit("No self-test code implemented")
