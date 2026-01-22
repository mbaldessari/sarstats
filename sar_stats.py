"""
Graph sar(1) reports.

sar(1) provides system activity reports that are useful in the analysis of
system performance issues. This script produces a PDF file with graphs of the
data contained in one or more sar reports.
"""

# SarStats.py - sar(1) report graphing utility
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
# MA 02110-1301, USA.

from hashlib import sha1
from itertools import repeat
from typing import Optional
import csv
import multiprocessing
import os
import sys
import textwrap

import dateutil

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle as PS
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Image, Spacer
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate
from reportlab.platypus.frames import Frame
from reportlab.platypus.paragraph import Paragraph
from reportlab.platypus.tableofcontents import TableOfContents

import sar_metadata as metadata
from sos_utils import natural_sort_key


# None means use all available CPUs
NR_CPUS: Optional[int] = None

# Maximum graphs per page by default
MAXGRAPHS_IN_PAGE = 64

DEFAULT_IMG_EXT = ".png"

# Graph dimensions in inches
GRAPH_WIDTH = 10.5
GRAPH_HEIGHT = 6.5


def split_chunks(lst: list, chunksize: int) -> list[list]:
    """Split a list into chunks of at most chunksize elements."""
    return [lst[i : i + chunksize] for i in range(0, len(lst), chunksize)]


def parse_labels(labels: Optional[list[str]]) -> list[tuple]:
    """Parse label strings into (datetime, label) tuples.

    Args:
        labels: List of strings in format "label:YYYY-MM-DD HH:MM:SS".

    Returns:
        List of (datetime, label) tuples.
    """
    if not labels:
        return []

    result = []
    for label_str in labels:
        parts = label_str.split(":", 1)
        if len(parts) != 2:
            continue
        label = parts[0]
        time_str = parts[1]
        parsed_time = dateutil.parser.parse(time_str)
        result.append((parsed_time, label))

    return result


class MyDocTemplate(BaseDocTemplate):
    """Custom Doc Template in order to have bookmarks
    for certain type of text"""

    def __init__(self, filename, **kw):
        self.allowSplitting = 0
        BaseDocTemplate.__init__(self, filename, **kw)
        template = PageTemplate(
            "normal", [Frame(0.1 * inch, 0.1 * inch, 11 * inch, 8 * inch, id="F1")]
        )
        self.addPageTemplates(template)

        self.centered = PS(
            name="centered", fontSize=30, leading=16, alignment=1, spaceAfter=20
        )

        self.centered_index = PS(
            name="centered_index", fontSize=24, leading=16, alignment=1, spaceAfter=20
        )

        self.small_centered = PS(
            name="small_centered", fontSize=14, leading=16, alignment=1, spaceAfter=20
        )

        self.h1 = PS(name="Heading1", fontSize=16, leading=16)

        self.h2 = PS(name="Heading2", fontSize=14, leading=14)

        self.h2_center = PS(name="Heading2Center", alignment=1, fontSize=14, leading=14)

        self.h2_invisible = PS(
            name="Heading2Invisible",
            alignment=1,
            textColor="#FFFFFF",
            fontSize=14,
            leading=14,
        )

        self.mono = PS(name="Mono", fontName="Courier", fontSize=16, leading=16)

        self.normal = PS(name="Normal", fontSize=16, leading=16)

        self.toc = TableOfContents()
        self.toc.levelStyles = [
            PS(
                fontName="Times-Bold",
                fontSize=14,
                name="TOCHeading1",
                leftIndent=20,
                firstLineIndent=-20,
                spaceBefore=2,
                leading=16,
            ),
            PS(
                fontSize=10,
                name="TOCHeading2",
                leftIndent=40,
                firstLineIndent=-20,
                spaceBefore=0,
                leading=8,
            ),
        ]

    def afterFlowable(self, flowable):
        """Registers TOC entries."""
        if flowable.__class__.__name__ == "Paragraph":
            text = flowable.getPlainText()
            style = flowable.style.name
            if style in ["Heading1", "centered_index"]:
                level = 0
            elif style in ["Heading2", "Heading2Center", "Heading2Invisible"]:
                level = 1
            else:
                return
            entry = [level, text, self.page]
            # if we have a bookmark name append that to our notify data
            bookmark_name = getattr(flowable, "_bookmarkName", None)
            if bookmark_name is not None:
                entry.append(bookmark_name)
            self.notify("TOCEntry", tuple(entry))
            self.canv.addOutlineEntry(text, bookmark_name, level, True)


def graph_wrapper(arg: tuple) -> None:
    """Wrapper for pool.map() to plot a single graph."""
    sar_stats_obj, sar_obj, dataname = arg
    sar_grapher = sar_stats_obj.sar_grapher
    fname = sar_grapher._graph_filename(dataname[1][0])
    sar_obj.plot_datasets(
        dataname, fname, sar_stats_obj.extra_labels, sar_stats_obj.showreboots
    )
    sys.stdout.write(".")
    sys.stdout.flush()


class SarStats:
    """PDF report generator for SAR data."""

    def __init__(self, sar_grapher, maxgraphs: int = MAXGRAPHS_IN_PAGE) -> None:
        """Initialize SarStats.

        Args:
            sar_grapher: SarGrapher instance with parsed data.
            maxgraphs: Maximum graphs per page.
        """
        self.story: list = []
        self.maxgraphs = maxgraphs
        self.sar_grapher = sar_grapher
        self.extra_labels: Optional[list[tuple]] = None
        self.showreboots: bool = False

    def graphs_order(
        self,
        cat: set[str],
        skip_list: Optional[list[str]] = None,
    ) -> list[list]:
        """Determine the order in which to present graphs.

        Args:
            cat: Set of categories to include.
            skip_list: List of graph names to skip.

        Returns:
            Ordered list of graph specifications.
        """
        skiplist = skip_list or []
        my_list = []
        sar_grapher = self.sar_grapher
        sar_parser = sar_grapher.sar_parser
        # First we add all the simple graphs sorted by chosen category list
        for i in cat:
            for j in sorted(sar_parser.available_data_types(), key=natural_sort_key):
                # We cannot graph a column with device names
                if j.endswith("DEVICE"):
                    continue
                if metadata.get_category(j) == i:
                    my_list.append([j])

        # Here we add the combined graphs always per category
        c = {}
        for i in metadata.INDEX_COLUMN:
            s = sar_parser.datanames_per_arg(i, False)
            try:
                key = metadata.get_category(s[0][0])
            except Exception:
                continue
            if key not in c:
                c[key] = s
            else:
                c[key] += s

        # We merge the two in a single list: for each category simple graphs
        # and then combined graphs
        my_list = []
        for i in cat:
            for j in sorted(sar_parser.available_data_types(), key=natural_sort_key):
                if (
                    j in metadata.BASE_GRAPHS
                    and metadata.BASE_GRAPHS[j]["cat"] == i
                    and j not in skiplist
                ):
                    entry = metadata.graph_info([j], sar_obj=sar_parser)
                    my_list.append([entry, [j]])
            if i in c:
                for j in range(len(c[i])):
                    # Only add the graph if none of it's components is in the
                    # skip_list
                    b = sorted(
                        [
                            x
                            for x in c[i][j]
                            if len(set(skiplist).intersection(x.split("#"))) == 0
                        ],
                        key=natural_sort_key,
                    )
                    # If the graph has more than X columns we split it
                    if len(b) > self.maxgraphs:
                        chunks = split_chunks(b, self.maxgraphs)
                        counter = 1
                        for chunk in chunks:
                            entry = metadata.graph_info(chunk, sar_obj=sar_parser)
                            s = "{0} {1}/{2}".format(entry[0], counter, len(chunks))
                            newentry = (s, entry[1], entry[2])
                            my_list.append([newentry, chunk])
                            counter += 1
                    else:
                        entry = metadata.graph_info(b, sar_obj=sar_parser)
                        my_list.append([entry, b])

        return my_list

    def do_heading(self, text: str, sty: PS) -> None:
        """Add a heading with bookmark to the document.

        Args:
            text: Heading text.
            sty: Paragraph style to apply.
        """
        bookmark_name = sha1(
            text.encode("utf-8") + sty.name.encode("utf-8")
        ).hexdigest()
        heading = Paragraph(f'{text}<a name="{bookmark_name}"/>', sty)
        heading._bookmarkName = bookmark_name
        self.story.append(heading)

    def graph(
        self,
        sar_files: list[str],
        skip_list: list[str],
        output_file: str = "out.pdf",
        labels: Optional[list[str]] = None,
        show_reboots: bool = False,
        custom_graphs: Optional[list[str]] = None,
        threaded: bool = True,
    ) -> None:
        """Parse SAR data and produce graphs in a PDF.

        Args:
            sar_files: List of SAR files being processed.
            skip_list: List of graph names to skip.
            output_file: Output PDF filename.
            labels: Extra labels for annotations.
            show_reboots: Whether to show reboot markers.
            custom_graphs: Custom graph specifications.
            threaded: Whether to use multiprocessing.
        """
        sar_grapher = self.sar_grapher
        sar_parser = sar_grapher.sar_parser
        self.extra_labels = None
        self.showreboots = show_reboots
        doc = MyDocTemplate(output_file, pagesize=landscape(A4))

        if labels is not None:
            try:
                self.extra_labels = parse_labels(labels)
            except Exception:
                print(f"Unable to parse extra labels: {labels}")
                raise

        self.story.append(Paragraph(f"{sar_parser.hostname}", doc.centered))
        self.story.append(
            Paragraph(f"{sar_parser.kernel} {sar_parser.version}", doc.small_centered)
        )
        self.story.append(Spacer(1, 0.05 * inch))
        self.story.append(Paragraph(" ".join(sar_files), doc.small_centered))

        mins = int(sar_parser.sample_frequency / 60)
        secs = int(sar_parser.sample_frequency % 60)
        freq_str = f"Sampling Frequency: {mins} minutes"
        if secs > 0:
            freq_str += f" {secs} seconds"
        self.story.append(Paragraph(freq_str, doc.small_centered))

        self.do_heading("Table of contents", doc.centered_index)
        self.story.append(doc.toc)
        self.story.append(PageBreak())

        category_order = metadata.list_all_categories()

        used_cat = {}
        count = 0
        # Let's create all the images either via multiple threads or in
        # sequence
        if threaded:
            pool = multiprocessing.Pool(NR_CPUS)
            graph_list = self.graphs_order(category_order, skip_list)
            f = zip(repeat(self), repeat(sar_grapher), graph_list)
            pool.map(graph_wrapper, f)
        else:
            for dataname in self.graphs_order(category_order, skip_list):
                fname = sar_grapher._graph_filename(dataname[1][0])
                sar_grapher.plot_datasets(
                    dataname, fname, self.extra_labels, show_reboots
                )
                sys.stdout.write(".")
                sys.stdout.flush()

        # Custom graphs are created sequentially (typically few in number)
        # Format: 'foo:ldavg-1,i001/s;bar:i001/s,i002/s'
        custom_graph_list: dict[str, list[str]] = {}
        if custom_graphs:
            try:
                for spec in custom_graphs:
                    parts = spec.split(":", 1)
                    if len(parts) == 2:
                        label = parts[0]
                        values = parts[1].split(",")
                        custom_graph_list[label] = values
            except Exception as e:
                raise ValueError(f"Error parsing custom graphs: {custom_graphs}") from e

            for graph_name, patterns in custom_graph_list.items():
                matched_graphs: set[str] = set()
                for pattern in patterns:
                    try:
                        matches = sar_parser.match_datasets(pattern)
                    except Exception as e:
                        raise ValueError(f"Error in regex for: {pattern}") from e
                    matched_graphs.update(matches)

                graphs = list(matched_graphs)
                if not graphs:
                    continue

                fname = sar_grapher._graph_filename(graphs)
                sar_grapher.plot_datasets(
                    ([graph_name, None, graphs], graphs),
                    fname,
                    self.extra_labels,
                    show_reboots,
                )
                sys.stdout.write(".")
                sys.stdout.flush()

                cat = "Custom"
                if cat not in used_cat:
                    self.do_heading(cat, doc.h1)
                    used_cat[cat] = True
                else:
                    self.story.append(Paragraph(cat, doc.normal))

                self.do_heading(graph_name, doc.h2_invisible)
                self.story.append(
                    Image(fname, width=GRAPH_WIDTH * inch, height=GRAPH_HEIGHT * inch)
                )
                self.story.append(Spacer(1, 0.2 * inch))

        # All the image files are created let's go through the files and create
        # the pdf
        for dataname in self.graphs_order(category_order, skip_list):
            fname = sar_grapher._graph_filename(dataname[1][0])
            cat = sar_parser._categories[dataname[1][0]]
            title = dataname[0][0]
            # We've not seen the category before
            if cat not in used_cat:
                self.do_heading(cat, doc.h1)
                used_cat[cat] = True
            else:
                self.story.append(Paragraph(cat, doc.normal))
            self.do_heading(title, doc.h2_invisible)
            self.story.append(
                Image(fname, width=GRAPH_WIDTH * inch, height=GRAPH_HEIGHT * inch)
            )
            self.story.append(Spacer(1, 0.2 * inch))
            desc = metadata.get_desc(dataname[1])
            for name, desc, detail in desc:
                self.story.append(
                    Paragraph("<strong>%s</strong> - %s" % (name, desc), doc.normal)
                )
                if detail:
                    self.story.append(
                        Paragraph("Counter: <i>%s</i>" % (detail), doc.mono)
                    )

            self.story.append(PageBreak())
            count += 1

        doc.multiBuild(self.story)

    def export_csv(self, output_file: str) -> None:
        """Export SAR data to CSV format.

        Args:
            output_file: Path to the output CSV file.
        """
        sar_parser = self.sar_grapher.sar_parser
        all_keys = sorted(sar_parser.available_data_types())

        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp"] + all_keys)
            for timestamp in sorted(sar_parser._data.keys()):
                row = [timestamp.isoformat()]
                row.extend(sar_parser._data[timestamp].get(key) for key in all_keys)
                writer.writerow(row)

    def plot_ascii(self, graphs: list[str]) -> None:
        """Display graphs in ASCII format."""
        self.sar_grapher.plot_ascii(graphs)

    def plot_svg(
        self,
        graphs: list[str],
        output: str,
        labels: Optional[list[str]] = None,
    ) -> None:
        """Output graphs as SVG files."""
        extra_labels = parse_labels(labels)
        self.sar_grapher.plot_svg(graphs, output, extra_labels)

    def list_graphs(self) -> None:
        """Print available graphs and metadata to stdout."""
        sar_parser = self.sar_grapher.sar_parser
        timestamps = self.sar_grapher.timestamps()

        print(f"\nTimespan: {timestamps[0]} - {timestamps[-1]}")

        if sar_parser.sosreport and sar_parser.sosreport.reboots:
            reboots = sar_parser.sosreport.reboots
            reboot_dates = " ".join(str(reboots[i]["date"]) for i in reboots)
            print(f"Reboots: {reboot_dates}")

        gaps = sar_parser.find_data_gaps()
        if gaps:
            print("Data gaps:")
            for start, end in gaps:
                print(f"{start} - {end}")

        print("List of graphs available:")

        # Build inverse map: category -> list of graph names
        inv_map: dict[str, list[str]] = {}
        for key, category in sar_parser._categories.items():
            inv_map.setdefault(category, []).append(key)

        try:
            size_output = os.popen("stty size", "r").read().split()
            columns = int(size_output[1]) - 10 if len(size_output) > 1 else 70
        except (ValueError, IndexError):
            columns = 70

        for category in sorted(inv_map):
            graphs_list = ", ".join(sorted(inv_map[category], key=natural_sort_key))
            indent = " " * (len(category) + 2)
            text = textwrap.fill(
                graphs_list,
                width=columns,
                initial_indent="",
                subsequent_indent=indent,
            )
            print(f"{category}: {text}")


# vim: autoindent tabstop=4 expandtab smarttab shiftwidth=4 softtabstop=4 tw=0
