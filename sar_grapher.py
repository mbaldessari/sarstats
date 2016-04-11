import hashlib
import matplotlib
# Force matplotlib to not use any Xwindows backend.
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.colors as colors
import matplotlib.cm as cm
from matplotlib.patches import Rectangle
import os
import shutil
import tempfile

from sar_parser import SarParser

# If the there are more than 50 plots in a graph we move the legend to the
# bottom
LEGEND_THRESHOLD = 50


def ascii_date(d):
    return "%s" % (d.strftime("%Y-%m-%d %H:%M"))


class SarGrapher(object):
    def __init__(self, filenames, starttime=None, endtime=None):
        """Initializes the class, creates a SarParser class
        given a list of files and also parsers the files"""
        # Temporary dir where images are stored (one per graph)
        # NB: This is done to keep the memory usage constant
        # in spite of being a bit slower (before this change
        # we could use > 12GB RAM for a simple sar file -
        # matplotlib is simply inefficient in this area)
        self._tempdir = tempfile.mkdtemp(prefix='sargrapher')

        self.sar_parser = SarParser(filenames, starttime, endtime)
        self.sar_parser.parse()
        duplicate_timestamps = self.sar_parser._duplicate_timestamps
        if duplicate_timestamps:
            print("There are {0} lines with duplicate timestamps. First 10"
                  "line numbers at {1}".format(
                      len(duplicate_timestamps.keys()),
                      sorted(list(duplicate_timestamps.keys()))[:10]))

    def _graph_filename(self, graph, extension='.png'):
        """Creates a unique constant file name given a graph or graph list"""
        if isinstance(graph, list):
            temp = "_".join(graph)
        else:
            temp = graph
        temp = temp.replace('%', '_')
        temp = temp.replace('/', '_')
        digest = hashlib.sha1()
        digest.update(temp.encode('utf-8'))
        fname = os.path.join(self._tempdir, digest.hexdigest() + extension)
        return fname

    def datasets(self):
        """Returns a list of all the available datasets"""
        return self.sar_parser.available_data_types()

    def timestamps(self):
        """Returns a list of all the available datasets"""
        return sorted(self.sar_parser.available_timestamps())

    def plot_datasets(self, data, fname, extra_labels, showreboots=False,
                      output='pdf'):
        """ Plot timeseries data (of type dataname).  The data can be either
        simple (one or no datapoint at any point in time, or indexed (by
        indextype). dataname is assumed to be in the form of [title, [label1,
        label2, ...], [data1, data2, ...]] extra_labels is a list of tuples
        [(datetime, 'label'), ...] """
        sar_parser = self.sar_parser
        title = data[0][0]
        unit = data[0][1]
        axis_labels = data[0][2]
        datanames = data[1]

        if not isinstance(datanames, list):
            raise Exception("plottimeseries expects a list of datanames: %s" %
                            data)

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
        scalar_map = cm.ScalarMappable(norm=color_norm,
                                       cmap=plt.get_cmap('Set1'))

        timestamps = self.timestamps()
        counter = 0
        for i in datanames:
            try:
                dataset = [sar_parser._data[d][i] for d in timestamps]
            except:
                print("Key {0} does not exist in this graph".format(i))
                raise
            axes.plot(timestamps, dataset, 'o:', label=axis_labels[counter],
                      color=scalar_map.to_rgba(counter))
            counter += 1

        # Draw extra_labels
        if extra_labels:
            for extra in extra_labels:
                axes.annotate(extra[1], xy=(mdates.date2num(extra[0]),
                              sar_parser.find_max(extra[0], datanames)),
                              xycoords='data', xytext=(30, 30),
                              textcoords='offset points',
                              arrowprops=dict(arrowstyle="->",
                              connectionstyle="arc3,rad=.2"))

        # If we have a sosreport draw the reboots
        if showreboots and sar_parser.sosreport is not None and \
           sar_parser.sosreport.reboots is not None:
            reboots = sar_parser.sosreport.reboots
            for reboot in reboots.keys():
                reboot_date = reboots[reboot]['date']
                rboot_x = mdates.date2num(reboot_date)
                (xmin, xmax) = plt.xlim()
                (ymin, ymax) = plt.ylim()
                if rboot_x < xmin or rboot_x > xmax:
                    continue

                axes.annotate('', xy=(mdates.date2num(reboot_date), ymin),
                              xycoords='data', xytext=(-30, -30),
                              textcoords='offset points',
                              arrowprops=dict(arrowstyle="->", color='blue',
                              connectionstyle="arc3,rad=-0.1"))

        # Show any data collection gaps in the graph
        gaps = sar_parser.find_data_gaps()
        if len(gaps) > 0:
            for i in gaps:
                (g1, g2) = i
                x1 = mdates.date2num(g1)
                x2 = mdates.date2num(g2)
                (ymin, ymax) = plt.ylim()
                axes.add_patch(Rectangle((x1, ymin), x2 - x1,
                                         ymax - ymin, facecolor="lightgrey"))

        # Add a grid to the graph to ease visualization
        axes.grid(True)

        lgd = None
        # Draw the legend only when needed
        if len(datanames) > 1 or \
           (len(datanames) == 1 and len(datanames[0].split('#')) > 1):
            # We want the legends box roughly square shaped
            # and not take up too much room
            props = matplotlib.font_manager.FontProperties(size='xx-small')
            if len(datanames) < LEGEND_THRESHOLD:
                cols = int((len(datanames) ** 0.5))
                lgd = axes.legend(loc=1, ncol=cols, shadow=True, prop=props)
            else:
                cols = int(len(datanames) ** 0.6)
                lgd = axes.legend(loc=9, ncol=cols,
                                  bbox_to_anchor=(0.5, -0.29),
                                  shadow=True, prop=props)

        if len(datanames) == 0:
            return None

        try:
            if lgd:
                plt.savefig(fname, bbox_extra_artists=(lgd,),
                            bbox_inches='tight')
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

    def plot_svg(self, graphs, output, labels):
        """Given a list of graphs, output an svg file per graph.
        Input is a list of strings. A graph with multiple datasets
        is a string with datasets separated by comma"""
        if output == 'out.pdf':
            output = 'graph'
        counter = 1
        fnames = []
        for i in graphs:
            subgraphs = i.split(',')
            fname = self._graph_filename(subgraphs, '.svg')
            fnames.append(fname)
            self.plot_datasets((['', None, subgraphs], subgraphs), fname,
                               labels)
            dest = os.path.join(os.getcwd(), "{0}{1}.svg".format(
                                output, counter))
            shutil.move(fname, dest)
            print("Created: {0}".format(dest))
            counter += 1

        # removes all temporary files and directories
        self.close()

    def plot_ascii(self, graphs, def_columns=80, def_rows=25):
        """Displays a single graph in ASCII form on the terminal"""
        import subprocess
        sar_parser = self.sar_parser
        timestamps = self.timestamps()
        try:
            rows, columns = os.popen('stty size', 'r').read().split()
        except:
            columns = def_columns
        rows = def_rows
        if columns > def_columns:
            columns = def_columns

        for graph in graphs:
            try:
                gnuplot = subprocess.Popen(["/usr/bin/gnuplot"],
                                           stdin=subprocess.PIPE)
            except Exception as e:
                raise("Error launching gnuplot: {0}".format(e))

            gnuplot.stdin.write("set term dumb {0} {1}\n".format(
                                columns, rows))
            gnuplot.stdin.write("set xdata time\n")
            gnuplot.stdin.write('set xlabel "Time"\n')
            gnuplot.stdin.write('set timefmt \"%Y-%m-%d %H:%M\"\n')
            gnuplot.stdin.write('set xrange [\"%s\":\"%s\"]\n' %
                                (ascii_date(timestamps[0]),
                                 ascii_date(timestamps[-1])))
            gnuplot.stdin.write('set ylabel "%s"\n' % (graph))
            gnuplot.stdin.write('set datafile separator ","\n')
            gnuplot.stdin.write('set autoscale y\n')
            gnuplot.stdin.write('set title "%s - %s"\n' %
                                (graph, " ".join(sar_parser._files)))
            # FIXME: do it through a method
            try:
                dataset = [sar_parser._data[d][graph] for d in timestamps]
            except KeyError:
                print("Key '{0}' could not be found")
                return

            txt = "plot '-' using 1:2 title '{0}' with linespoints \n".format(
                graph)
            gnuplot.stdin.write(txt)
            for i, j in zip(timestamps, dataset):
                s = '\"%s\",%f\n' % (ascii_date(i), j)
                gnuplot.stdin.write(s)

            gnuplot.stdin.write("e\n")
            gnuplot.stdin.write("exit\n")
            gnuplot.stdin.flush()

    def export_csv(self):
        return

    def close(self):
        """Removes temporary directory and files"""
        if os.path.isdir(self._tempdir):
            shutil.rmtree(self._tempdir)
