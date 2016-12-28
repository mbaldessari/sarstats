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

import datetime
import dateutil
import os
import numpy
import re

import sar_metadata
from sos_report import SosReport

# regex of the sar column containing the time of the measurement
TIMESTAMP_RE = re.compile(r'(\d{2}):(\d{2}):(\d{2})\s?(AM|PM)?')


def natural_sort_key(s):
    """Natural sorting function. Given a string, it returns a list of the strings
    and numbers. For example: natural_sort_key("michele0123") will return:
    ['michele', 123, '']"""

    _nsre = re.compile('([0-9]+)')
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(_nsre, s)]


def _empty_line(line):
    """Parse an empty line"""

    pattern = re.compile(r'^\s*$')
    return re.search(pattern, line)


def _average_line(line):
    """Parse a line starting with 'Average:'or 'Summary:'"""

    pattern = re.compile(r'^Average|^Summary')
    return re.search(pattern, line)


def canonicalise_timestamp(date, ts):
    """sar files start with a date string (yyyy-mm-dd) and a
    series of lines starting with the time. Given the initial
    sar datetime date object as base and the time string column
    return a full datetime object"""

    matches = re.search(TIMESTAMP_RE, ts)
    if matches:
        (hours, minutes, seconds, meridiem) = matches.groups()
        hours = int(hours)
        minutes = int(minutes)
        seconds = int(seconds)
        if meridiem:
            if meridiem == 'AM' and hours == 12:
                hours = 0
            if meridiem == 'PM' and hours < 12:
                hours += 12
        if hours == 24:
            hours = 0
        dt = datetime.datetime(date[0], date[1], date[2], hours,
                               minutes, seconds)
    else:
        raise Exception("canonicalise_timestamp error %s" % ts)
    return dt


class SarParser(object):
    """Class for parsing a sar report and querying its data
    Data structure representing the sar report's contents.
    Main _data structure is a dictionary of dictionaries.
    First dictionary index is a timestamp (datetime class)
    and the second index is the graph's type:
    '%commit', '%memused', '%swpcad', '%swpused', '%vmeff'
    'CPU#0#%idle', 'CPU#0#%iowait', 'CPU#0#%irq', 'CPU#0#%nice'
    'CPU#0#%soft', 'CPU#0#%sys', 'CPU#0#%usr',..."""

    def __init__(self, fnames, starttime=None, endtime=None):
        """Constructor: takes a list of files to be parsed. The parsing
        itself is done in the .parse() method"""
        self._data = {}

        # This dict holds the relationship graph->category
        self._categories = {}
        self._files = fnames
        self.kernel = None
        self.version = None
        self.hostname = None
        self.sample_frequency = None
        # Date of the report
        self._date = None
        # If this one was set it means that we crossed the day during one SAR
        # file
        self._olddate = None
        self._prev_timestamp = None
        self.starttime = None
        self.endtime = None
        if starttime:
            self.starttime = dateutil.parser.parse(starttime[0])

        if endtime:
            self.endtime = dateutil.parser.parse(endtime[0])

        # Current line number (for use in reporting parse errors)
        self._linecount = 0
        # Hash containing all the line numbers with duplicate entries
        self._duplicate_timestamps = {}

        absdir = os.path.abspath(fnames[0])

        # if we were passed a file we need to calculate where the
        # sosreport base is
        if not os.path.isdir(absdir):
            for i in range(4):
                absdir = os.path.split(absdir)[0]

        self.sosreport = None
        try:
            self.sosreport = SosReport(absdir)
            self.sosreport.parse()
        except:
            pass

    def _prune_data(self):
        """This walks the _data structure and removes all graph keys that
        have a 0 value in *all* timestamps. FIXME: As inefficient as it
        goes for now..."""
        # Store all possible keys looping over all time stamps
        all_keys = {}
        for t in self._data.keys():
            for i in self._data[t].keys():
                all_keys[i] = True

        keys_to_remove = {}
        for k in all_keys.keys():
            remove = True
            for t in self._data.keys():
                if k in self._data[t] and self._data[t][k] != 0:
                    remove = False
                    break

            if remove:
                keys_to_remove[k] = True

        for t in self._data.keys():
            for i in keys_to_remove.keys():
                try:
                    self._data[t].pop(i)
                except:
                    pass

        # Store all possible keys
        all_keys = {}
        for t in self._data.keys():
            for i in self._data[t].keys():
                all_keys[i] = True

        # If we miss a key in a specific timestamp set it to none
        # This simplifies graph creation
        for t in self._data.keys():
            for i in all_keys.keys():
                if i not in self._data[t]:
                    self._data[t][i] = None

        # We need to prune self._categories as well
        keys_to_prune = {}
        for i in self._categories.keys():
            if i not in all_keys:
                keys_to_prune[i] = True

        for i in keys_to_prune.keys():
            self._categories.pop(i)

    def _parse_first_line(self, line):
        """Parse the line as a first line of a SAR report"""

        pattern = re.compile(r"""(?x)
            ^(\S+)\s+                 # Kernel name (uname -s)
            (\S+)\s+                  # Kernel release (uname -r)
            \((\S+)\)\s+              # Hostname
            ((?:\d{4}-\d{2}-\d{2})|   # Date in YYYY-MM-DD format
             (?:\d{2}/\d{2}/\d{2,4})) #      in MM/DD/(YY)YY format
            .*$                       # Remainder, ignored
            """)

        matches = re.search(pattern, line)
        if matches:
            (self.kernel, self.version, self.hostname,
             tmpdate) = matches.groups()
        else:
            raise Exception('Line {0}: "{1}" failed to parse as a'
                            ' first line'.format(self._linecount, line))

        pattern = re.compile(r"(\d{2})/(\d{2})/(\d{2,4})")
        matches = re.search(pattern, tmpdate)
        if matches:
            (mm, dd, yyyy) = matches.groups()
            if len(yyyy) == 2:
                yyyy = '20' + yyyy
            tmpdate = yyyy + '-' + mm + '-' + dd

        self._date = list(map(int, tmpdate.split('-')))

    def _column_headers(self, line):
        """Parse the line as a set of column headings"""
        restr = r"""(?x)
            ^(""" + sar_metadata.TIMESTAMP_RE + """)\s+
            (
                # Time to be strict - we don't want to
                # accidentally end up recognising lines of
                # data as lines defining column structure
                # Any field that has numbers inside of it needs
                # to be explicitely ORed
                (?:
                    (?:[a-zA-Z6%/_-]+       # No numbers (except for IPv6)
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
        pattern = re.compile(restr)
        matches = re.search(pattern, line)
        if matches:
            hdrs = [h for h in matches.group(2).split(' ') if h != '']
            return matches.group(1), hdrs
        else:
            return None, None

    def _do_start(self, line):
        """Actions for the "start" state of the parser"""

        self._parse_first_line(line)

    def _column_type_regexp(self, hdr):
        """Get the regular expression to match entries under a
        particular header"""

        return sar_metadata.get_regexp(hdr)

    def _valid_column_header_name(self, hdr):
        """Is hdr a valid column name? """

        return self._column_type_regexp(hdr) is not None

    def _build_data_line_regexp(self, headers):
        """
        Given a list of headers, build up a regular expression to match
        corresponding data lines.
        """
        regexp = r'^(' + sar_metadata.TIMESTAMP_RE + r')'
        for hdr in headers:
            hre = self._column_type_regexp(hdr)
            if hre is None:
                raise Exception('Line {0}: column header "{1}"'
                                'unknown {2}'.format(self._linecount, hdr))
            regexp = regexp + r'\s+(' + str(hre) + r')'
        regexp += r'\s*$'
        return regexp

    def _record_data(self, headers, matches):
        """Record a parsed line of data"""
        timestamp = canonicalise_timestamp(self._date, matches.group(1))
        # We skip recording values if the timestamp is not within the limits
        # defined by the user
        if self.starttime and timestamp < self.starttime:
            return
        if self.endtime and timestamp > self.endtime:
            return
        if self._prev_timestamp and timestamp:
            # FIXME: This breaks if sar interval is bigger > 119 mins
            if self._prev_timestamp.hour == 23 and timestamp.hour == 0:
                nextday = timestamp + datetime.timedelta(days=1)
                self._olddate = self._date
                self._date = (nextday.year, nextday.month, nextday.day)
                timestamp = canonicalise_timestamp(self._date,
                                                   matches.group(1))
            elif timestamp < self._prev_timestamp:
                raise Exception("Time going backwards: {0} "
                                "- Prev timestamp: {1} -> {2}".
                                format(timestamp, self._prev_timestamp,
                                       self._linecount))
        self._prev_timestamp = timestamp

        # We never had this timestamp let's start with a new dictionary
        # associated to it
        if timestamp not in self._data:
            self._data[timestamp] = {}

        column = 0
        # The column used as index/key can be different
        for i in headers:
            if i in sar_metadata.INDEX_COLUMN:
                break
            column += 1

        # Simple case: data is "2D": all columns are of a simple data type
        # that has just one datum per timestamp
        if column >= len(headers):
            counter = 0
            previous = ""
            for header in headers:
                i = header
                # HACK due to sysstat idiocy (retrans/s can appear in ETCP and
                # NFS) Rename ETCP retrans/s to retrant/s
                if i == 'retrans/s' and previous == 'estres/s':
                    i = 'retrant/s'
                if i in self._data[timestamp]:
                    # We do not bail out anymore on duplicate timestamps but
                    # simply report it to the user
                    self._duplicate_timestamps[self._linecount] = True

                try:
                    v = float(matches.group(counter + 2))
                except ValueError:
                    v = matches.group(counter + 2)
                self._data[timestamp][i] = v
                self._categories[i] = sar_metadata.get_category(i)
                previous = i
                counter += 1
            return timestamp

        # Complex case: data is "3D": data is indexed by an index column
        # (CPU number, device name etc.) and there is one datum per index
        # column value per timestamp
        indexcol = headers[column]
        indexval = matches.group(column + 2)
        if indexval == 'all' or indexval == 'Summary':
            # This is derived information that is only included for some types
            # of data. Let's save ourselves the complication.
            return timestamp

        counter = 0
        # column represents the number of the column which is used as index
        # Introduced due to 'FILESYSTEM' which is at the end. All the others
        # (CPU, IFACE...) are the first column
        for i in headers:
            if counter == column:
                counter += 1
                continue

            s = '{0}#{1}#{2}'.format(indexcol, indexval, i)
            if s in self._data[timestamp]:
                # LOVELY: Filesystem can have multiple entries with the same
                # FILESYSTEM and timestamp We used to raise an exception here
                # but apparently sometimes there are sar files with same
                # timestamp and different values. Let's just ignore that We do
                # not bail out anymore on duplicate timestamps but simply
                # report it to the user
                self._duplicate_timestamps[self._linecount] = True

            try:
                v = float(matches.group(counter + 2))
            except ValueError:
                v = matches.group(counter + 2)
            self._data[timestamp][s] = v
            self._categories[s] = sar_metadata.get_category(s)
            counter += 1

        return timestamp

    def parse(self, skip_tables=['BUS']):
        """Parse a the sar files. This method does the actual
        parsing and will populate the ._data structure. The
        parsing is performed line by line via a simple state
        machine"""
        for file_name in self._files:
            self._prev_timestamp = None
            state = 'start'
            headers = None
            self.cur_file = file_name
            fd = open(file_name, "r")
            for line in fd.readlines():
                self._linecount += 1
                line = line.rstrip('\n')
                if state == 'start':
                    self._do_start(line)
                    state = 'after_first_line'
                    continue

                if state == 'after_first_line':
                    if not _empty_line(line):
                        raise Exception('Line {0}: expected empty line but got'
                                        '"{1}" instead'.format(self._linecount,
                                                               line))
                    state = 'after_empty_line'
                    continue

                if state == 'after_empty_line':
                    if _empty_line(line):
                        continue

                    if _average_line(line):
                        state = 'table_end'
                        continue

                    state = 'table_start'
                    # Continue processing this line

                if state == 'skip_until_eot':
                    if not _empty_line(line):
                        continue
                    else:
                        state = 'after_empty_line'

                if state == 'table_start':
                    (timestamp, headers) = self._column_headers(line)
                    # If in previous tables we crossed the day, we start again
                    # from the previous date
                    if self._olddate:
                        self._date = self._olddate
                    if timestamp is None:
                        raise Exception('Line {0}: expected column header'
                                        ' line but got "{1}" instead'.format(
                                            self._linecount, line))
                    if headers == ['LINUX', 'RESTART']:
                        # FIXME: restarts should really be recorded, in a smart
                        # way
                        state = 'table_end'
                        continue
                    # FIXME: we might want to skip even if it is present in
                    # other columns
                    elif headers[0] in skip_tables:
                        state = 'skip_until_eot'
                        print("Skipping: {0}".format(headers))
                        continue

                    try:
                        pattern = re.compile(
                            self._build_data_line_regexp(headers))
                    except AssertionError:
                        raise Exception('Line {0}: exceeding python '
                                        'interpreter limit with regexp for '
                                        'this line "{1}"'.format(
                                            self._linecount, line))

                    self._prev_timestamp = False
                    state = 'table_row'
                    continue

                if state == 'table_row':
                    if _empty_line(line):
                        state = 'after_empty_line'
                        continue

                    if _average_line(line):
                        state = 'table_end'
                        continue

                    matches = re.search(pattern, line)
                    if matches is None:
                        raise Exception("File: {0} - Line {1}: headers: '{2}'"
                                        ", line: '{3}' regexp '{4}': failed"
                                        " to parse".format(
                                            self.cur_file, self._linecount,
                                            str(headers), line,
                                            pattern.pattern))

                    self._record_data(headers, matches)
                    continue

                if state == 'table_end':
                    if _empty_line(line):
                        state = 'after_empty_line'
                        continue

                    if _average_line(line):
                        # Remain in 'table_end' state
                        continue

                    raise Exception('Line {0}: "{1}" expecting end of '
                                    'table'.format(self._linecount, line))
            fd.close()

        # Remove unneeded columns
        self._prune_data()

        # Calculate sampling frequency
        k = sorted(self._data.keys())
        diff = [(x - k[i - 1]).total_seconds()
                for i, x in enumerate(k) if i > 0]
        self.sample_frequency = numpy.mean(diff)

    def available_datasets(self):
        """Returns all available datasets"""
        first_timestamp = self._data.keys()[0]
        datasets = [i for i in sorted(self._data[first_timestamp].keys())]
        return datasets

    def match_datasets(self, regex):
        """Returns all datasets that match a certain regex"""
        first_timestamp = list(self._data.keys())[0]
        expression = re.compile(regex)
        ret = []
        for i in sorted(self._data[first_timestamp].keys()):
            if expression.match(i):
                ret.append(i)
        return ret

    def available_timestamps(self):
        """Returns all available timestamps"""
        return list(self._data.keys())

    def close(self):
        """Explicitly removes the main ._data structure from memory"""
        del self._data

    def available_types(self, category):
        """Given a category string returns all the graphs starting
        with it"""
        t = list(self._data.keys())[0]
        l = [i for i in sorted(self._data[t].keys()) if i.startswith(category)]
        return l

    def datanames_per_arg(self, category, per_key=True):
        """Returns a list of all combined graphs per category. If per_key is
        True the list is per DEVICE/CPU/etc. Otherwise it is per "perf"
        attribute datanames_per_arg('DEV', True) will give:
        ['DEV#dev253-1#%util', 'DEV#dev253-1#avgqu-sz',
        'DEV#dev253-1#avgrq-sz',..], ['DEV#dev8-0#%util',
        'DEV#dev8-0#avgqu-sz', ...]] datanames_per_arg('DEV', False) will give:
        [['DEV#dev253-1#%util', 'DEV#dev8-0#%util', 'DEV#dev8-3#%util'],
        ['DEV#dev253-1#avgqu-sz'...]]"""
        l = self.available_types(category)
        ret = []

        if per_key:
            keys = {}
            for i in l:
                try:
                    (cat, k, p) = i.split("#")
                except:
                    raise Exception("Error datanames_per_arg "
                                    "per_key={0}: {1}".format(
                                        per_key, i))
                keys[k] = True

            for i in sorted(keys.keys(), key=natural_sort_key):
                tmp = []
                for j in l:
                    try:
                        (cat, k, p) = j.split("#")
                    except:
                        raise Exception("Error datanames_per_arg "
                                        "per_key={0}: {1}".format(
                                            per_key, j))
                    if k == i and not p.endswith('DEVICE'):
                        tmp.append(j)
                if len(tmp) == 0:
                    continue
                ret.append(tmp)

            return ret

        if not per_key:
            keys2 = {}
            for i in l:
                try:
                    (cat, k, p) = i.split("#")
                except:
                    raise Exception("Error datanames_per_arg "
                                    "per_key={0}: {1}".format(
                                        per_key, i))
                keys2[p] = True

            for i in sorted(keys2.keys(), key=natural_sort_key):
                tmp = []
                for j in l:
                    (cat, k, p) = j.split("#")
                    if p == i and not p.endswith('DEVICE'):
                        tmp.append(j)
                if len(tmp) == 0:
                    continue
                ret.append(tmp)

            return ret

    def available_data_types(self):
        """ What types of data are available. """
        return set([item for date in self._data.keys()
                   for item in self._data[date].keys()])

    def find_max(self, timestamp, datanames):
        """Finds the max Y value given an approx timestamp and a list of
        datanames"""
        timestamps = list(self._data.keys())
        time_key = min(timestamps, key=lambda date: abs(timestamp - date))
        ymax = -1
        for i in datanames:
            if self._data[time_key][i] > ymax:
                ymax = self._data[time_key][i]

        return ymax

    def find_data_gaps(self):
        """Returns a list of tuples containing the data gaps. A data gap is an
        interval of time longer than the collecting frequency that does not
        contain any data.  NOTE: The algorithm is not super-smart, but covers
        the most blatant cases.  This is because the sampling frequency
        calculation is skewed a bit when the sysstat is not running.  Returns:
        [(gap1start, gap1end), (.., ..), ...] or []"""

        # in seconds
        freq = self.sample_frequency
        last = None
        ret = []
        for time in sorted(self.available_timestamps()):
            if not last:
                last = time
                continue
            delta = time - last
            # If the delta > (freq + 10%) we consider it a gap
            # NB: we must add a bit of percentage to make
            # sure we do not display gaps unnecessarily
            if delta.total_seconds() > int(freq * 1.1):
                ret.append((last, time))
            last = time

        return ret


if __name__ == '__main__':
    raise Exception('No self-test code implemented')

# vim: autoindent tabstop=4 expandtab smarttab shiftwidth=4 softtabstop=4 tw=0
