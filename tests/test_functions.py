import cProfile
import os
import os.path
import pstats
import random
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

sarstats = imp.load_source('sarstats', 'sarstats')

SAR_FILES = 'sar-files'

def end_of_path(s):
    base = os.path.basename(s)
    dirname = os.path.dirname(s)
    return os.path.join(os.path.split(dirname)[1], base)

class TestSarParsing(unittest.TestCase):
    def setUp(self):
        sar_base = os.path.join(sys.modules['tests'].__file__)
        self.sar_dir = os.path.join(os.path.abspath(os.path.dirname(sar_base)),
            SAR_FILES)
        tmp = []
        for root, dirs, files in os.walk(self.sar_dir):
            for f in files:
                s = f.lower().strip()
                if s.startswith("sar"):
                    tmp.append(os.path.join(root, f))

        self.sar_files = sorted(tmp)
        if USE_PROFILER:
            self.pr = cProfile.Profile()
            self.pr.enable()
        self.startTime = time.time()

    def tearDown(self):
        t = time.time() - self.startTime
        print("{0}: {1:.3f}".format(self.id(), t))

    def test_sar(self):
        count = 0
        for example in self.sar_files:
            print("Parsing: {0}".format(example))
            sar = SAR.SAR([example])
            sar.parse()
            usage = resource.getrusage(resource.RUSAGE_SELF)
            if USE_MELIAE:
                objgraph.show_growth()
                tmp = tempfile.mkstemp(prefix='sar-test')[1]
                scanner.dump_all_objects(tmp)
                l = loader.load(tmp)
                s = l.summarize()
            print("SAR parsing: {0} usertime={1} systime={2} mem={3} MB"
                .format(end_of_path(example), usage[0], usage[1],
                (usage[2] / 1024.0)))
            count += 1
            if USE_PROFILER:
                self.pr.disable()
                s = StringIO.StringIO()
                sortby = 'cumulative'
                ps = pstats.Stats(self.pr, stream=s).sort_stats(sortby)
                ps.print_stats(TOP_PROFILED_FUNCTIONS)
                print("\nProfiling of sar.parse()")
                print(s.getvalue())

                # Set up profiling for pdf generation
                self.pr.enable()

            stats = sarstats.SarStats(sar)
            out = "{0}.pdf".format(example)
            stats.graph(example, [], out)
            if USE_PROFILER:
                self.pr.disable()
                s = StringIO.StringIO()
                sortby = 'cumulative'
                ps = pstats.Stats(self.pr, stream=s).sort_stats(sortby)
                ps.print_stats(TOP_PROFILED_FUNCTIONS)
                print("\nProfiling of sarstats.graph()")
                print(s.getvalue())

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
