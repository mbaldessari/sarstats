from pathlib import Path
from typing import Optional
import hashlib
import os
import shutil
import subprocess
import tempfile

import matplotlib

# Force matplotlib to not use any Xwindows backend.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.colors as colors
import matplotlib.cm as cm
from matplotlib.patches import Rectangle

from sar_parser import SarParser

# If there are more than 50 plots in a graph we move the legend to the bottom
LEGEND_THRESHOLD = 50


def ascii_date(d) -> str:
    """Format datetime for ASCII output."""
    return d.strftime("%Y-%m-%d %H:%M")


class SarGrapher:
    """Graph generator for SAR data."""

    def __init__(
        self,
        filenames: list[str],
        starttime: Optional[list[str]] = None,
        endtime: Optional[list[str]] = None,
    ) -> None:
        """Initialize SarGrapher.

        Creates a SarParser class given a list of files and parses them.
        Images are stored in a temporary directory to keep memory usage constant.

        Args:
            filenames: List of SAR files to parse.
            starttime: Optional start time filter.
            endtime: Optional end time filter.
        """
        self._tempdir = Path(tempfile.mkdtemp(prefix="sargrapher"))

        self.sar_parser = SarParser(filenames, starttime, endtime)
        self.sar_parser.parse()

        duplicate_timestamps = self.sar_parser._duplicate_timestamps
        if duplicate_timestamps:
            print(
                f"There are {len(duplicate_timestamps)} lines with duplicate timestamps. "
                f"First 10 line numbers at {sorted(duplicate_timestamps.keys())[:10]}"
            )

    def _graph_filename(self, graph: str | list[str], extension: str = ".png") -> str:
        """Create a unique constant file name given a graph or graph list."""
        if isinstance(graph, list):
            temp = "_".join(graph)
        else:
            temp = graph
        temp = temp.replace("%", "_").replace("/", "_")
        digest = hashlib.sha1(temp.encode("utf-8")).hexdigest()
        return str(self._tempdir / (digest + extension))

    def datasets(self) -> set[str]:
        """Return a set of all available datasets."""
        return self.sar_parser.available_data_types()

    def timestamps(self) -> list:
        """Return a sorted list of all available timestamps."""
        return sorted(self.sar_parser.available_timestamps())

    def plot_datasets(
        self,
        data: tuple[tuple[str, Optional[str], list[str]], list[str]],
        fname: str,
        extra_labels: Optional[list[tuple]],
        showreboots: bool = False,
        output: str = "pdf",
    ) -> None:
        """Plot timeseries data.

        Args:
            data: Tuple of ((title, unit, axis_labels), datanames).
            fname: Output filename.
            extra_labels: List of (datetime, 'label') tuples for annotations.
            showreboots: Whether to show reboot markers.
            output: Output format.
        """
        sar_parser = self.sar_parser
        title = data[0][0]
        unit = data[0][1]
        axis_labels = data[0][2]
        datanames = data[1]

        if not isinstance(datanames, list):
            raise TypeError(f"plottimeseries expects a list of datanames: {data}")

        fig = plt.figure(figsize=(10.5, 6.5))
        axes = fig.add_subplot(111)
        axes.set_title(f"{title} time series", fontsize=12)
        axes.set_xlabel("Time")
        axes.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
        axes.xaxis.set_minor_locator(mdates.MinuteLocator(interval=20))
        fig.autofmt_xdate()

        ylabel = f"{title} - {unit}" if unit else title
        axes.set_ylabel(ylabel)
        y_formatter = matplotlib.ticker.ScalarFormatter(useOffset=False)
        axes.yaxis.set_major_formatter(y_formatter)
        axes.yaxis.get_major_formatter().set_scientific(False)

        color_norm = colors.Normalize(vmin=0, vmax=len(datanames) - 1)
        scalar_map = cm.ScalarMappable(norm=color_norm, cmap=plt.get_cmap("Set1"))

        timestamps = self.timestamps()
        for counter, dataname in enumerate(datanames):
            try:
                dataset = [sar_parser._data[d][dataname] for d in timestamps]
            except KeyError:
                print(f"Key {dataname} does not exist in this graph")
                raise
            axes.plot(
                timestamps,
                dataset,
                "o:",
                label=axis_labels[counter],
                color=scalar_map.to_rgba(counter),
            )

        # Draw extra_labels
        if extra_labels:
            for extra in extra_labels:
                axes.annotate(
                    extra[1],
                    xy=(
                        mdates.date2num(extra[0]),
                        sar_parser.find_max(extra[0], datanames),
                    ),
                    xycoords="data",
                    xytext=(30, 30),
                    textcoords="offset points",
                    arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=.2"),
                )

        # If we have a sosreport draw the reboots
        if (
            showreboots
            and sar_parser.sosreport is not None
            and sar_parser.sosreport.reboots is not None
        ):
            reboots = sar_parser.sosreport.reboots
            for reboot in reboots.keys():
                reboot_date = reboots[reboot]["date"]
                rboot_x = mdates.date2num(reboot_date)
                (xmin, xmax) = plt.xlim()
                (ymin, ymax) = plt.ylim()
                if rboot_x < xmin or rboot_x > xmax:
                    continue

                axes.annotate(
                    "",
                    xy=(mdates.date2num(reboot_date), ymin),
                    xycoords="data",
                    xytext=(-30, -30),
                    textcoords="offset points",
                    arrowprops=dict(
                        arrowstyle="->", color="blue", connectionstyle="arc3,rad=-0.1"
                    ),
                )

        # Show any data collection gaps in the graph
        gaps = sar_parser.find_data_gaps()
        if len(gaps) > 0:
            for i in gaps:
                (g1, g2) = i
                x1 = mdates.date2num(g1)
                x2 = mdates.date2num(g2)
                (ymin, ymax) = plt.ylim()
                axes.add_patch(
                    Rectangle((x1, ymin), x2 - x1, ymax - ymin, facecolor="lightgrey")
                )

        # Add a grid to the graph to ease visualization
        axes.grid(True)

        lgd = None
        # Draw the legend only when needed
        if len(datanames) > 1 or (
            len(datanames) == 1 and len(datanames[0].split("#")) > 1
        ):
            # We want the legends box roughly square shaped
            # and not take up too much room
            props = matplotlib.font_manager.FontProperties(size="xx-small")
            if len(datanames) < LEGEND_THRESHOLD:
                cols = int((len(datanames) ** 0.5))
                lgd = axes.legend(loc=1, ncol=cols, shadow=True, prop=props)
            else:
                cols = int(len(datanames) ** 0.6)
                lgd = axes.legend(
                    loc=9,
                    ncol=cols,
                    bbox_to_anchor=(0.5, -0.29),
                    shadow=True,
                    prop=props,
                )

        if len(datanames) == 0:
            return None

        try:
            if lgd:
                plt.savefig(fname, bbox_extra_artists=(lgd,), bbox_inches="tight")
            else:
                plt.savefig(fname, bbox_inches="tight")
        except Exception:
            import traceback

            print(traceback.format_exc())
            import sys

            sys.exit(-1)

        plt.cla()
        plt.clf()
        plt.close("all")

    def plot_svg(
        self,
        graphs: list[str],
        output: str,
        labels: Optional[list[tuple]],
    ) -> None:
        """Output an SVG file per graph.

        Args:
            graphs: List of graph names (comma-separated for multiple datasets).
            output: Output filename prefix.
            labels: Optional labels for annotations.
        """
        if output == "out.pdf":
            output = "graph"

        for counter, graph in enumerate(graphs, 1):
            subgraphs = graph.split(",")
            fname = self._graph_filename(subgraphs, ".svg")
            self.plot_datasets((["", None, subgraphs], subgraphs), fname, labels)
            dest = Path.cwd() / f"{output}{counter}.svg"
            shutil.move(fname, dest)
            print(f"Created: {dest}")

        self.close()

    def plot_ascii(
        self,
        graphs: list[str],
        def_columns: int = 80,
        def_rows: int = 25,
    ) -> None:
        """Display graphs in ASCII form on the terminal using gnuplot."""
        sar_parser = self.sar_parser
        timestamps = self.timestamps()

        try:
            size_output = os.popen("stty size", "r").read().split()
            columns = int(size_output[1]) if len(size_output) > 1 else def_columns
        except (ValueError, IndexError):
            columns = def_columns
        columns = min(columns, def_columns)

        for graph in graphs:
            try:
                gnuplot = subprocess.Popen(
                    ["/usr/bin/gnuplot"],
                    stdin=subprocess.PIPE,
                    text=True,
                )
            except OSError as e:
                raise RuntimeError(f"Error launching gnuplot: {e}") from e

            commands = [
                f"set term dumb {columns} {def_rows}",
                "set xdata time",
                'set xlabel "Time"',
                'set timefmt "%Y-%m-%d %H:%M"',
                f'set xrange ["{ascii_date(timestamps[0])}":"{ascii_date(timestamps[-1])}"]',
                f'set ylabel "{graph}"',
                'set datafile separator ","',
                "set autoscale y",
                f'set title "{graph} - {" ".join(sar_parser._files)}"',
            ]

            try:
                dataset = [sar_parser._data[d][graph] for d in timestamps]
            except KeyError:
                print(f"Key '{graph}' could not be found")
                continue

            commands.append(f"plot '-' using 1:2 title '{graph}' with linespoints")
            for cmd in commands:
                gnuplot.stdin.write(cmd + "\n")

            for ts, val in zip(timestamps, dataset):
                gnuplot.stdin.write(f'"{ascii_date(ts)}",{val}\n')

            gnuplot.stdin.write("e\n")
            gnuplot.stdin.write("exit\n")
            gnuplot.stdin.flush()
            gnuplot.wait()

    def close(self) -> None:
        """Remove temporary directory and files."""
        if self._tempdir.is_dir():
            shutil.rmtree(self._tempdir)
