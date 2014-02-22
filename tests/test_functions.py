"""
Test unit for sarstats
"""
import cProfile
import os
import os.path
import pstats
import resource
import StringIO
import sys
import tempfile
import time
import unittest

# To debug memory leaks
USE_MELIAE = False
if USE_MELIAE:
    from meliae import scanner, loader
    import objgraph
    import gc

# To profile speed
USE_PROFILER = True
TOP_PROFILED_FUNCTIONS = 15

import SAR
import imp

# Hack needed because sarstats does not end in .py
SARSTATS_MOD = imp.load_source('sarstats', 'sarstats')

SAR_FILES = 'sar-files'

def end_of_path(path):
    """Prints the last part of an absolute path"""
    base = os.path.basename(path)
    dirname = os.path.dirname(path)
    return os.path.join(os.path.split(dirname)[1], base)

class TestSarParsing(unittest.TestCase):
    """Main UnitTest class"""
    def setUp(self):
        """Sets the test cases up"""
        sar_base = os.path.join(sys.modules['tests'].__file__)
        self.sar_dir = os.path.join(os.path.abspath(os.path.dirname(sar_base)),
            SAR_FILES)
        tmp = []
        for root, dirs, files in os.walk(self.sar_dir):
            for fname in files:
                if fname.lower().strip().startswith("sar"):
                    tmp.append(os.path.join(root, fname))

        self.sar_files = sorted(tmp)
        if USE_PROFILER:
            self.profile = cProfile.Profile()
            self.profile.enable()
        self.start_time = time.time()

    def tearDown(self):
        """Called when the testrun is complete. Displays full time"""
        tdelta = time.time() - self.start_time
        print("{0}: {1:.5f}".format(self.id(), tdelta))

    def test_sar(self):
        """Parses all the sar files and creates the pdf outputs"""
        for example in self.sar_files:
            print("Parsing: {0}".format(example))
            sar = SAR.SAR([example])
            sar.parse()
            usage = resource.getrusage(resource.RUSAGE_SELF)
            if USE_MELIAE:
                objgraph.show_growth()
                tmp = tempfile.mkstemp(prefix='sar-test')[1]
                scanner.dump_all_objects(tmp)
                leakreporter = loader.load(tmp)
                summary = leakreporter.summarize()
            print("SAR parsing: {0} usertime={1} systime={2} mem={3} MB"
                .format(end_of_path(example), usage[0], usage[1],
                (usage[2] / 1024.0)))
            if USE_PROFILER:
                self.profile.disable()
                str_io = StringIO.StringIO()
                sortby = 'cumulative'
                pstat = pstats.Stats(self.profile, stream=str_io).sort_stats(sortby)
                pstat.print_stats(TOP_PROFILED_FUNCTIONS)
                print("\nProfiling of sar.parse()")
                print(str_io.getvalue())

                # Set up profiling for pdf generation
                self.profile.enable()

            stats = SARSTATS_MOD.SarStats(sar)
            out = "{0}.pdf".format(example)
            stats.graph(example, [], out)
            if USE_PROFILER:
                self.profile.disable()
                str_io = StringIO.StringIO()
                sortby = 'cumulative'
                pstat = pstats.Stats(self.profile, stream=str_io).sort_stats(sortby)
                pstat.print_stats(TOP_PROFILED_FUNCTIONS)
                print("\nProfiling of sarstats.graph()")
                print(str_io.getvalue())

            print("Wrote: {0}".format(out))
            os.remove(out)
            sar.close()
            del sar
            stats.close()
            del stats
            usage = resource.getrusage(resource.RUSAGE_SELF)
            print("SAR graphing: {0} usertime={1} systime={2} mem={3} MB"
                .format(end_of_path(example), usage[0], usage[1],
                (usage[2] / 1024.0)))

if __name__ == '__main__':
    unittest.main()
