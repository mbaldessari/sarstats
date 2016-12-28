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

from __future__ import print_function
from itertools import repeat
from hashlib import sha1
import csv
import dateutil
import multiprocessing
import os
import sys

from reportlab.lib.styles import ParagraphStyle as PS
from reportlab.platypus import PageBreak, Image, Spacer
from reportlab.platypus.paragraph import Paragraph
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.platypus.frames import Frame
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4, landscape

from sar_parser import natural_sort_key
import sar_metadata as metadata


# None means nr of available CPUs
NR_CPUS = None

# No more than the following nr of graphs in a single page
# per default
MAXGRAPHS_IN_PAGE = 64

DEFAULT_IMG_EXT = ".png"

# Inch graph size
GRAPH_WIDTH = 10.5
GRAPH_HEIGHT = 6.5


def split_chunks(list_to_split, chunksize):
    """Split the list l in chunks of at most n in size"""
    return [list_to_split[i:i + chunksize]
            for i in range(0, len(list_to_split), chunksize)]


def parse_labels(labels):
    """Parses list of labels in the form of foo:2014-01-01 13:45:03
    and returns a list of tuples [(datetime, 'label), ...]"""

    if labels is None:
        return []
    ret_labels = []
    for i in labels:
        # labels are in the form "foo:2014-01-01 13:45:03"
        label = i.split(':')[0]
        time = "".join(i.split(':')[1:])
        time = dateutil.parser.parse(time)
        ret_labels.append((time, label))

    return ret_labels


class MyDocTemplate(BaseDocTemplate):
    """Custom Doc Template in order to have bookmarks
    for certain type of text"""
    def __init__(self, filename, **kw):
        self.allowSplitting = 0
        BaseDocTemplate.__init__(self, filename, **kw)
        template = PageTemplate('normal', [Frame(0.1 * inch, 0.1 * inch,
                                11 * inch, 8 * inch, id='F1')])
        self.addPageTemplates(template)

        self.centered = PS(
            name='centered',
            fontSize=30,
            leading=16,
            alignment=1,
            spaceAfter=20)

        self.centered_index = PS(
            name='centered_index',
            fontSize=24,
            leading=16,
            alignment=1,
            spaceAfter=20)

        self.small_centered = PS(
            name='small_centered',
            fontSize=14,
            leading=16,
            alignment=1,
            spaceAfter=20)

        self.h1 = PS(
            name='Heading1',
            fontSize=16,
            leading=16)

        self.h2 = PS(
            name='Heading2',
            fontSize=14,
            leading=14)

        self.h2_center = PS(
            name='Heading2Center',
            alignment=1,
            fontSize=14,
            leading=14)

        self.h2_invisible = PS(
            name='Heading2Invisible',
            alignment=1,
            textColor='#FFFFFF',
            fontSize=14,
            leading=14)

        self.mono = PS(
            name='Mono',
            fontName='Courier',
            fontSize=16,
            leading=16)

        self.normal = PS(
            name='Normal',
            fontSize=16,
            leading=16)

        self.toc = TableOfContents()
        self.toc.levelStyles = [
            PS(fontName='Times-Bold', fontSize=14, name='TOCHeading1',
                leftIndent=20, firstLineIndent=-20, spaceBefore=2, leading=16),
            PS(fontSize=10, name='TOCHeading2', leftIndent=40,
                firstLineIndent=-20, spaceBefore=0, leading=8),
        ]

    def afterFlowable(self, flowable):
        """Registers TOC entries."""
        if flowable.__class__.__name__ == 'Paragraph':
            text = flowable.getPlainText()
            style = flowable.style.name
            if style in ['Heading1', 'centered_index']:
                level = 0
            elif style in ['Heading2', 'Heading2Center', 'Heading2Invisible']:
                level = 1
            else:
                return
            entry = [level, text, self.page]
            # if we have a bookmark name append that to our notify data
            bookmark_name = getattr(flowable, '_bookmarkName', None)
            if bookmark_name is not None:
                entry.append(bookmark_name)
            self.notify('TOCEntry', tuple(entry))
            self.canv.addOutlineEntry(text, bookmark_name, level, True)


def graph_wrapper(arg):
    """This is a wrapper due to pool.map() single argument limit"""
    sar_stats_obj, sar_obj, dataname = arg
    sar_grapher = sar_stats_obj.sar_grapher
    fname = sar_grapher._graph_filename(dataname[1][0])
    sar_obj.plot_datasets(dataname, fname, sar_stats_obj.extra_labels,
                          sar_stats_obj.showreboots)
    sys.stdout.write(".")
    sys.stdout.flush()


class SarStats(object):
    """Creates a pdf file given a parsed SAR object"""
    def __init__(self, sar_grapher, maxgraphs=MAXGRAPHS_IN_PAGE):
        """Initialize class"""
        self.story = []
        self.maxgraphs = maxgraphs
        self.sar_grapher = sar_grapher

    def graphs_order(self, cat, skip_list=None):
        """ Order in which to present all graphs.
        Data is grouped loosely by type. """
        skiplist = skip_list or []
        l = []
        sar_grapher = self.sar_grapher
        sar_parser = sar_grapher.sar_parser
        # First we add all the simple graphs sorted by chosen category list
        for i in cat:
            for j in sorted(sar_parser.available_data_types(),
                            key=natural_sort_key):
                # We cannot graph a column with device names
                if j.endswith('DEVICE'):
                    continue
                if metadata.get_category(j) == i:
                    l.append([j])

        # Here we add the combined graphs always per category
        c = {}
        for i in metadata.INDEX_COLUMN:
            s = sar_parser.datanames_per_arg(i, False)
            try:
                key = metadata.get_category(s[0][0])
            except:
                continue
            if key not in c:
                c[key] = s
            else:
                c[key] += s

        # We merge the two in a single list: for each category simple graphs
        # and then combined graphs
        l = []
        for i in cat:
            for j in sorted(sar_parser.available_data_types(),
                            key=natural_sort_key):
                if j in metadata.BASE_GRAPHS and \
                        metadata.BASE_GRAPHS[j]['cat'] == i and \
                        j not in skiplist:
                    entry = metadata.graph_info([j], sar_obj=sar_parser)
                    l.append([entry, [j]])
            if i in c:
                for j in range(len(c[i])):
                    # Only add the graph if none of it's components is in the
                    # skip_list
                    b = sorted([x for x in c[i][j]
                               if len(set(skiplist).intersection(
                                   x.split('#'))) == 0], key=natural_sort_key)
                    # If the graph has more than X columns we split it
                    if len(b) > self.maxgraphs:
                        chunks = split_chunks(b, self.maxgraphs)
                        counter = 1
                        for chunk in chunks:
                            entry = metadata.graph_info(chunk,
                                                        sar_obj=sar_parser)
                            s = "{0} {1}/{2}".format(entry[0],
                                                     counter, len(chunks))
                            newentry = (s, entry[1], entry[2])
                            l.append([newentry, chunk])
                            counter += 1
                    else:
                        entry = metadata.graph_info(b, sar_obj=sar_parser)
                        l.append([entry, b])

        return l

    def do_heading(self, text, sty):
        # create bookmarkname
        bn = sha1(text.encode('utf-8') + sty.name.encode('utf-8')).hexdigest()
        # modify paragraph text to include an anchor point with name bn
        h = Paragraph(text + '<a name="%s"/>' % bn, sty)
        # store the bookmark name on the flowable so afterFlowable can see this
        h._bookmarkName = bn
        self.story.append(h)

    def graph(self, sar_files, skip_list, output_file='out.pdf', labels=None,
              show_reboots=False, custom_graphs='', threaded=True):
        """ Parse sar data and produce graphs of the parsed data. """
        sar_grapher = self.sar_grapher
        sar_parser = sar_grapher.sar_parser
        self.extra_labels = None
        self.showreboots = show_reboots
        doc = MyDocTemplate(output_file, pagesize=landscape(A4))

        if labels is not None:
            try:
                self.extra_labels = parse_labels(labels)
            except:
                raise
                print("Unable to parse extra labels: {0}".format(labels))
                sys.exit(-1)

        self.story.append(Paragraph('%s' % sar_parser.hostname, doc.centered))
        self.story.append(Paragraph('%s %s' % (sar_parser.kernel,
                                               sar_parser.version),
                          doc.small_centered))
        self.story.append(Spacer(1, 0.05 * inch))
        self.story.append(Paragraph('%s' % (" ".join(sar_files)),
                          doc.small_centered))
        mins = int(sar_parser.sample_frequency / 60)
        secs = int(sar_parser.sample_frequency % 60)
        s = "Sampling Frequency: %s minutes" % mins
        if secs > 0:
            s += " %s seconds" % secs
        self.story.append(Paragraph(s, doc.small_centered))

        self.do_heading('Table of contents', doc.centered_index)
        self.story.append(doc.toc)
        self.story.append(PageBreak())

        category_order = metadata.list_all_categories()

        used_cat = {}
        count = 0
        # Let's create all the images either via multiple threads or in
        # sequence
        if threaded:
            pool = multiprocessing.Pool(NR_CPUS)
            l = self.graphs_order(category_order, skip_list)
            f = zip(repeat(self), repeat(sar_grapher), l)
            pool.map(graph_wrapper, f)
        else:
            for dataname in self.graphs_order(category_order, skip_list):
                fname = sar_grapher._graph_filename(dataname[1][0])
                sar_grapher.plot_datasets(dataname, fname, self.extra_labels,
                                          show_reboots)
                sys.stdout.write(".")
                sys.stdout.flush()

        # Custom graphs are always created in non threaded mode as their number
        # is typically quite low. Graph descriptions are in the form:
        # 'foo:ldavg-1,i001/s;bar:i001/s,i002/s'
        custom_graph_list = {}
        if custom_graphs is not None:
            try:
                for i in custom_graphs:
                    label = i.split(':')[0]
                    values = i.split(':')[1].split(',')
                    custom_graph_list[label] = values
            except:
                raise Exception("Error in parsing custom graphs: {0}".format(
                                custom_graphs))

            for graph in custom_graph_list.keys():
                matched_graphs = set()
                # For each customer graph o through every dataset
                for i in custom_graph_list[graph]:
                    # For each match add it to the set
                    try:
                        ret = sar_parser.match_datasets(i)
                    except:
                        raise Exception("Error in regex for: {0}".format(i))
                    for j in ret:
                        matched_graphs.add(j)

                graphs = list(matched_graphs)
                if len(graphs) == 0:
                    continue
                fname = sar_grapher._graph_filename(graphs)
                sar_grapher.plot_datasets(([graph, None, graphs], graphs),
                                          fname, self.extra_labels,
                                          show_reboots)
                sys.stdout.write(".")
                sys.stdout.flush()
                cat = 'Custom'
                if cat not in used_cat:  # We've not seen the category before
                    self.do_heading(cat, doc.h1)
                    used_cat[cat] = True
                else:
                    self.story.append(Paragraph(cat, doc.normal))

                self.do_heading(graph, doc.h2_invisible)
                self.story.append(Image(fname, width=GRAPH_WIDTH * inch,
                                        height=GRAPH_HEIGHT * inch))
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
            self.story.append(Image(fname, width=GRAPH_WIDTH * inch,
                                    height=GRAPH_HEIGHT * inch))
            self.story.append(Spacer(1, 0.2 * inch))
            desc = metadata.get_desc(dataname[1])
            for (name, desc, detail) in desc:
                self.story.append(Paragraph("<strong>%s</strong> - %s" %
                                  (name, desc), doc.normal))
                if detail:
                    self.story.append(Paragraph("Counter: <i>%s</i>" %
                                      (detail), doc.mono))

            self.story.append(PageBreak())
            count += 1

        doc.multiBuild(self.story)

    def export_csv(self, output_file):
        sar_grapher = self.sar_grapher
        sar_parser = sar_grapher.sar_parser
        f = open(output_file, 'wb')
        writer = csv.writer(f, delimiter=',')
        all_keys = list(sar_parser.available_data_types())
        writer.writerow(all_keys)
        for timestamps in sar_parser._data:
            s = []
            for i in all_keys:
                s.append(sar_parser._data[timestamps][i])
            writer.writerow(s)
        f.close()

    def plot_ascii(self, graphs):
        self.sar_grapher.plot_ascii(graphs)

    def plot_svg(self, graphs, output, labels=''):
        extra_labels = parse_labels(labels)
        self.sar_grapher.plot_svg(graphs, output, extra_labels)

    def list_graphs(self):
        sar_grapher = self.sar_grapher
        sar_parser = sar_grapher.sar_parser
        timestamps = sar_grapher.timestamps()
        print("\nTimespan: {0} - {1}".format(timestamps[0], timestamps[-1]))
        if sar_parser.sosreport and sar_parser.sosreport.reboots:
            reboots = sar_parser.sosreport.reboots
            print("Reboots: ", end='')
            for i in reboots:
                print("{0} ".format(reboots[i]['date']), end='')
            print('')

        gaps = sar_parser.find_data_gaps()
        if len(gaps) > 0:
            print("Data gaps:")
            for i in gaps:
                print("{0} - {1}".format(i[0], i[1]))

        print("List of graphs available:")
        inv_map = {}
        # FIXME: expose _categories through a method
        for k, v in sar_parser._categories.items():
            inv_map[v] = inv_map.get(v, [])
            inv_map[v].append(k)

        try:
            rows, columns = os.popen('stty size', 'r').read().split()
        except:
            columns = 80
        columns = int(columns) - 10

        import textwrap
        for i in sorted(inv_map):
            line = ", ".join(sorted(inv_map[i], key=natural_sort_key))
            indent = ' ' * (len(i) + 2)
            text = textwrap.fill(line, width=columns, initial_indent='',
                                 subsequent_indent=indent)
            print("{0}: {1}".format(i, text))

# vim: autoindent tabstop=4 expandtab smarttab shiftwidth=4 softtabstop=4 tw=0
