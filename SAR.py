#
# SAR.py - sar(1) report graphing utility
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
Hat Enterprise Linux versions 3 through 6.
"""

import logging
import datetime
import re
import os
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.colors as colors
import matplotlib.cm as cm
import numpy

import sar_metadata
import sosreport

# If the there are more than 50 plots in a graph we move the legend to
# the bottom
LEGEND_THRESHOLD = 50

logging.basicConfig()
LOGGER = logging.getLogger("SAR reports parser")
LOGGER.setLevel(logging.WARN)

TIMESTAMP_RE = re.compile(r'(\d{2}):(\d{2}):(\d{2})\s?(AM|PM)?')


def natural_sort_key(s):
    """Natural sorting function"""
    _nsre = re.compile('([0-9]+)')
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(_nsre, s)]


class SARError(Exception):
    """
    Exception class for use when parsing of a supposed SAR file fails, or for
    problems querying a SAR object
    """

    def __init__(self, msg=None):
        self._msg = msg
        Exception.__init__(self)

    def __str__(self):
        if self._msg is None:
            return "SAR Parser error - no further details"
        else:
            return "SAR Parser error: " + self._msg


def _empty_line(line):
    """ Parse an empty line. """

    pattern = re.compile(r'^\s*$')
    return re.search(pattern, line)


def _average_line(line):
    """ Parse a line starting with "Average:" or "Summary:" """

    pattern = re.compile(r'^Average:|^Summary')
    return re.search(pattern, line)


def canonicalise_timestamp(date, ts):
    """ Canonicalise timestamps to full datetime object. The date is taken
        from self._date which must have been parsed already"""

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
        dt = datetime.datetime(date[0], date[1], date[2], hours, minutes, seconds)
    else:
        raise SARError("canonicalise_timestamp error %s" % ts)
    return dt


class SAR(object):
    """ Class for parsing a sar report and querying its data
    Data structure representing the sar report's contents.
    Dictionary of dictionaries. First index is timestamp (datetime)
    and the second index is the column:
    '%commit', '%memused', '%swpcad', '%swpused', '%vmeff'
    'CPU#0#%idle', 'CPU#0#%iowait', 'CPU#0#%irq', 'CPU#0#%nice'
    'CPU#0#%soft', 'CPU#0#%sys', 'CPU#0#%usr',..."""
    _data = {}

    # This dict holds the relationship graph->category
    _categories = {}

    def __init__(self, fnames):
        LOGGER.debug("SAR:__init__")
        self._files = fnames

        (self.kernel, self.version, self.hostname, self._date) = (None, None, None, None)
        self.sample_frequency = None

        # Current line number (for use in reporting parse errors)
        self._linecount = 0
        # Date of the report
        self._date = None
        # If this one was set it means that we crossed the day during one SAR file
        self._olddate = None
        self._prev_timestamp = None

        # Is this file part of an sosreport?
        # Check ../../../sos_commands exists and see if uptime is a
        # symlink
        a = os.path.abspath(fnames[0])
        for i in range(4):
            a = os.path.split(a)[0]

        self.sosreport = None
        try:
            self.sosreport = sosreport.SOSReport(a)
            self.sosreport.parse()
        except:
            pass

    def _prune_data(self):
        """This walks the _data structure and removes all keys that have value
        0 in *all* timestamps FIXME: As inefficient as it goes for now..."""
        # Store all possible keys looping over all time stamps
        all_keys = {}
        for t in self._data.keys():
            for i in self._data[t].keys():
                all_keys[i] = True
        #print("Timestamps: {0} - Columns all: {1} - Columns firs row: {2}".format(len(self._data.keys()),
        #    len(all_keys.keys()), len(self._data[self._data.keys()[0]].keys())))
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
                if not i in self._data[t]:
                    self._data[t][i] = None

        # We need to prune self._categories as well
        for i in self._categories.keys():
            if i not in all_keys:
                self._categories.pop(i)


    def _parse_first_line(self, line):
        """ Parse the line as a first line of a SAR report. """

        LOGGER.debug("SAR:_parse_first_line")
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
            LOGGER.debug('Successfully parsed first line: "{0}"'.format(line))
            (self.kernel, self.version, self.hostname, tmpdate) = matches.groups()
        else:
            raise SARError('Line {0}: "{1}" failed to parse as a first line'.format(self._linecount, line))
        LOGGER.debug('Kernel: {0}; version: {1}; hostname: {2}; date: {3}'.format(self.kernel,
                     self.version, self.hostname, tmpdate))

        pattern = re.compile(r"(\d{2})/(\d{2})/(\d{2,4})")
        matches = re.search(pattern, tmpdate)
        if matches:
            (mm, dd, yyyy) = matches.groups()
            if len(yyyy) == 2:
                yyyy = '20' + yyyy
            tmpdate = yyyy + '-' + mm + '-' + dd

        self._date = map(int, tmpdate.split('-'))

    def _column_headers(self, line):
        """ Parse the line as a set of column headings. """
        LOGGER.debug("SAR:_column_headers")
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
            LOGGER.debug('Recognised column headers line: "{0}"'.format(line))
            hdrs = [h for h in matches.group(2).split(' ') if h != '']
            LOGGER.debug("Column headers: {0}".format(hdrs))
            return matches.group(1), hdrs
        else:
            LOGGER.debug('Not recognised as a column headers line: "{0}" using pattern "{1}"'.format(line, restr))
            return None, None

    def _do_start(self, line):
        """ Actions for the "start" state of the parser. """

        self._parse_first_line(line)

    def _column_type_regexp(self, hdr):
        """ Get the regular expression to match entries under a particular header """

        return sar_metadata.get_regexp(hdr)

    def _valid_column_header_name(self, hdr):
        """ Is hdr a valid column name? """

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
                raise SARError('Line {0}: column header "{1}" unknown {2}'.format(self._linecount, hdr))
            regexp = regexp + r'\s+(' + str(hre) + r')'
        regexp += r'\s*$'
        LOGGER.debug('Regular expression to match data lines: "{0}"'.format(regexp))
        return regexp

    def _record_data(self, headers, matches):
        """ Record a parsed line of data """
        timestamp = canonicalise_timestamp(self._date, matches.group(1))
        if self._prev_timestamp and timestamp:
            # FIXME: This breaks if sar interval is bigger > 119 mins
            if self._prev_timestamp.hour == 23 and timestamp.hour == 0:
                nextday = timestamp + datetime.timedelta(days=1)
                self._olddate = self._date
                self._date = (nextday.year, nextday.month, nextday.day)
                timestamp = canonicalise_timestamp(self._date, matches.group(1))
            elif timestamp < self._prev_timestamp:
                raise SARError("Time going backwards: {0} - Prev timestamp: {1} -> {2}".
                               format(timestamp, self._prev_timestamp, self._linecount))
        self._prev_timestamp = timestamp

        # We never had this timestamp let's start with a new dictionary
        # associated to it
        if not timestamp in self._data:
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
                # HACK due to sysstat idiocy (retrans/s can appear in ETCP and NFS)
                # Rename ETCP retrans/s to retrant/s
                if i == 'retrans/s' and previous == 'estres/s':
                    i = 'retrant/s'
                if i in self._data[timestamp]:
                    raise SARError("Odd timestamp %s and column %s already exist?" % (timestamp, i))

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
                # LOVELY: Filesystem can have multiple entries with the same FILESYSTEM and timestamp
                # Let's just overwrite those
                if indexcol != 'FILESYSTEM':
                    raise SARError("Odd timestamp %s and column %s already exist?" % (timestamp, s))

            try:
                v = float(matches.group(counter + 2))
            except ValueError:
                v = matches.group(counter + 2)
            self._data[timestamp][s] = v
            self._categories[s] = sar_metadata.get_category(s)
            counter += 1

        return timestamp

    def parse(self, skip_tables=['BUS']):
        """ Parse a SAR report. """
        # Parsing is performed line by line using a state machine
        for file_name in self._files:
            self._prev_timestamp = None
            state = 'start'
            headers = None
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
                        raise SARError('Line {0}: expected empty line but got "{1}" instead'.format(self._linecount, line))
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
                    # If in previous tables we crossed the day, we start again from the previous date
                    if self._olddate:
                        self._date = self._olddate
                    if timestamp is None:
                        raise SARError('Line {0}: expected column header line but'
                                       'got "{1}" instead'.format(self._linecount, line))
                    if headers == ['LINUX', 'RESTART']:
                        # FIXME: restarts should really be recorded, in a smart way
                        state = 'table_end'
                        continue
                    # FIXME: we might want to skip even if it is present in other columns
                    elif headers[0] in skip_tables:
                        state = 'skip_until_eot'
                        print("Skipping: {0}".format(headers))
                        continue

                    try:
                        pattern = re.compile(self._build_data_line_regexp(headers))
                    except AssertionError:
                        raise SARError('Line {0}: exceeding python interpreter'
                                       'limit with regexp for this line "{1}"'.
                                       format(self._linecount, line))

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
                        raise SARError("Line {0}: headers: '{1}', line: '{2}'"
                                       "regexp '{3}': failed to parse".format(self._linecount,
                                       str(headers), line, pattern.pattern))

                    self._record_data(headers, matches)
                    continue

                if state == 'table_end':
                    if _empty_line(line):
                        state = 'after_empty_line'
                        continue

                    if _average_line(line):
                        # Remain in 'table_end' state
                        continue

                    raise SARError('Line {0}: "{1}" expecting end of table'.format(self._linecount, line))
            fd.close()

        # Remove unneeded columns
        self._prune_data()

        # Calculate sampling frequency
        k = sorted(self._data.keys())
        diff = [(x - k[i - 1]).total_seconds() for i, x in enumerate(k) if i > 0]
        self.sample_frequency = numpy.mean(diff)

    def del_date(self, d):
        self._data.pop(d, None)

    def available_dates(self):
        return self._data.keys()

    def close(self):
        for i in self._data.keys():
            self.del_date(i)

    def available_types(self, category):
        t = self._data.keys()[0]
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
                    raise Exception("Error datanames_per_arg per_key={0}: {1}".format(per_key, i))
                keys[k] = True

            for i in sorted(keys.keys(), key=natural_sort_key):
                tmp = []
                for j in l:
                    try:
                        (cat, k, p) = j.split("#")
                    except:
                        raise Exception("Error datanames_per_arg per_key={0}: {1}".format(per_key, j))
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
                    raise Exception("Error datanames_per_arg per_key={0}: {1}".format(per_key, i))
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
        return set([item for date in self._data.keys() for item in self._data[date].keys()])

    def find_max(self, timestamp, datanames):
        """Finds the max Y value given an approx timestamp and a list of datanames"""
        timestamps = self._data.keys()
        time_key = min(timestamps, key=lambda date: abs(timestamp - date))
        ymax = -1
        for i in datanames:
            if self._data[time_key][i] > ymax:
                ymax = self._data[time_key][i]

        return ymax

    def plottimeseries(self, data, fname, extra_labels, showreboots=False, grid=False):
        """ Plot timeseries data (of type dataname).
        The data can be either simple (one or no datapoint at any point in time,
        or indexed (by indextype). dataname is assumed to be in the form of
        [title, [label1, label2, ...], [data1, data2, ...]]
        extra_labels is a list of tuples [(datetime, 'label'), ...]
        """
        title = data[0][0]
        unit = data[0][1]
        axis_labels = data[0][2]
        datanames = data[1]

        if not isinstance(datanames, list):
            raise Exception("plottimeseries expects a list of datanames: %s" % data)

        fig = plt.figure(figsize=(10.5, 6.5))
        axes = fig.add_subplot(111)
        axes.set_title('{0} time series'.format(title), fontsize=12)
        axes.set_xlabel('Time')
        axes.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        # Twenty minutes. Could probably make it a parameter
        axes.xaxis.set_minor_locator(mdates.MinuteLocator(interval=20))
        fig.autofmt_xdate()

        ylabel = title
        if unit:
            ylabel += " - " + unit
        axes.set_ylabel(ylabel)
        y_formatter = matplotlib.ticker.ScalarFormatter(useOffset=False)
        axes.yaxis.set_major_formatter(y_formatter)
        axes.yaxis.get_major_formatter().set_scientific(False)

        color_norm = colors.Normalize(vmin=0, vmax=len(datanames) - 1)
        scalar_map = cm.ScalarMappable(norm=color_norm, cmap=plt.get_cmap('Set1'))

        timestamps = sorted(self._data.keys())
        counter = 0
        for i in datanames:
            dataset = [self._data[d][i] for d in timestamps]
            axes.plot(timestamps, dataset, 'o:', label=axis_labels[counter], color=scalar_map.to_rgba(counter))
            counter += 1

        # Draw extra_labels
        if extra_labels:
            for extra in extra_labels:
                axes.annotate(extra[1], xy=(mdates.date2num(extra[0]),
                              self.find_max(extra[0], datanames)), xycoords='data',
                              xytext=(30, 30), textcoords='offset points',
                              arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=.2"))

        # If we have a sosreport draw the reboots
        if showreboots and self.sosreport is not None and self.sosreport.reboots is not None:
            reboots = self.sosreport.reboots
            for reboot in reboots.keys():
                rboot_x = mdates.date2num(reboots[reboot]['date'])
                (xmin, xmax) = plt.xlim()
                (ymin, ymax) = plt.ylim()
                if rboot_x < xmin or rboot_x > xmax:
                    continue

                axes.annotate('r', xy=(mdates.date2num(reboots[reboot]['date']), ymin),
                              xycoords='data', xytext=(-30, -30), textcoords='offset points',
                              arrowprops=dict(arrowstyle="->", color='blue',
                              connectionstyle="arc3,rad=-0.1"))

        if grid:
            axes.grid(True)
        else:
            axes.grid(False)

        lgd = None
        # Draw the legend only when needed
        if len(datanames) > 1 or (len(datanames) == 1 and len(datanames[0].split('#')) > 1):
            # We want the legends box roughly square shaped
            # and not take up too much room
            fontproperties = matplotlib.font_manager.FontProperties(size='xx-small')
            if len(datanames) < LEGEND_THRESHOLD:
                cols = int((len(datanames)**0.5))
                lgd = axes.legend(loc=1, ncol=cols, shadow=True, prop=fontproperties)
            else:
                cols = int(len(datanames)**0.6)
                lgd = axes.legend(loc=9, ncol=cols, bbox_to_anchor=(0.5, -0.29), shadow=True, prop=fontproperties)

        if len(datanames) == 0:
            return None

        try:
            if lgd:
                plt.savefig(fname, bbox_extra_artists=(lgd,), bbox_inches='tight')
            else:
                plt.savefig(fname, bbox_inches='tight')
        except:
            import traceback
            print(traceback.format_exc())
            import sys
            sys.exit(-1)

        plt.cla()
        plt.clf()
        plt.close('all')

if __name__ == '__main__':
    raise SARError('No self-test code implemented')

# vim: autoindent tabstop=4 expandtab smarttab shiftwidth=4 softtabstop=4 tw=0
