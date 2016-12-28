# Note: This is just a temporary class
# I am working on a more complete sosreport parsing class
# which will supersede this one
from dateutil import parser
from dateutil.relativedelta import relativedelta
import os
import os.path
import re

# Interrupt parsing routines taken from python-linux-procfs (GPLv2)
#


def natural_sort_key(s):
    _nsre = re.compile('([0-9]+)')
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(_nsre, s)]


class SosReport:
    def __init__(self, path):
        if not os.path.isdir(path):
            raise Exception("{0} does not exist".format(path))

        sospath = os.path.join(path, 'sos_reports')
        if not os.path.exists(sospath):
            raise Exception("{0} does not exist".format(sospath))

        self.path = path
        self.redhatrelease = None
        self.packages = []
        self.interrupts = {}
        self.networking = {}
        self.reboots = {}

    def _parse_network_ethtool(self):
        sos_networking = os.path.join(self.path, 'sos_commands/networking')
        for i in os.listdir(sos_networking):
            if not i.startswith('ethtool_-i_'):
                continue

            dev = i.split('_')[2]
            self.networking[dev] = {}
            f = open(os.path.join(sos_networking, i))
            for line in f.readlines():
                line = line.strip()
                if len(line) <= 1:
                    continue
                (label, value) = line.split(': ')
                self.networking[dev][label] = value

    def _parse_network(self):
        """Parse network configuration and create a hash like the following:
        self.network['eth0'] = {'module': 'igb', ipv4: ['10.0.0.1/24'],
        ipv6: ['fe80::2e41:38ff:feab:99e2/64'], 'firmware': '1.20',
        'bus-info': '0000:01:00.0', 'version': '3.133'"""
        self._parse_network_ethtool()
        return

    def _parse_int_entry(self, fields, line):
        d = {}
        d['cpu'] = []
        d['cpu'].append(int(fields[0]))
        nr_fields = len(fields)
        if nr_fields >= self.nr_cpus:
            d['cpu'] += [int(i) for i in fields[1:self.nr_cpus]]
            if nr_fields > self.nr_cpus:
                d['type'] = fields[self.nr_cpus]
                if nr_fields > self.nr_cpus + 1:
                    field = line.index(fields[self.nr_cpus + 1])
                    d['users'] = [a.strip() for a in line[field:].split(',')]
                else:
                    d['users'] = []
        return d

    def _parse_interrupts(self):
        """Parse /proc/interrupts in order to associate the interrupt number
        to the proper device"""
        intr_file = os.path.join(self.path, 'proc/interrupts')
        f = open(intr_file)
        for line in f.readlines():
            line = line.strip()
            fields = line.split()
            if fields[0][:3] == 'CPU':
                self.nr_cpus = len(fields)
                continue
            irq = fields[0].strip(":")
            self.interrupts[irq] = {}
            self.interrupts[irq] = self._parse_int_entry(fields[1:], line)
        return

    def _parse_disks(self):
        """Parse disk output files so that labels dev123-40 can be correctly
        mapped to an existing physical device"""
        return

    def _parse_reboots(self):
        """Parse /var/log/messages and find out when the machine rebooted.
        Returns an array of datetimes containing the times of reboot. First
        uncompress /var/log/messages*, go through them and search for lines
        like 'Dec  4 11:02:05 illins04 kernel: Linux version
        2.6.32-279.5.2.el6.x86_64'.  We parse messages* files because 'LINUX
        RESTART' in sar files is not precise"""
        # FIXME: uncompress any compressed messages files
        # FIXME: This is still potentially *very* fragile
        messages_dir = os.path.join(self.path, 'var/log')
        reboot_re = r'.*kernel: Linux version.*$'
        files = [f for f in os.listdir(messages_dir)
                 if f.startswith('messages')]
        for i in sorted(files, key=natural_sort_key, reverse=True):
            prev_month = None
            counter = 0
            f = open(os.path.join(messages_dir, i))
            for line in f.readlines():
                line = line.strip()
                if not re.match(reboot_re, line):
                    continue

                tokens = line.split()[0:3]
                d = parser.parse(" ".join(tokens))
                if d.month == 1 and prev_month == 12:
                    # We crossed a year. This means that all the dates read
                    # until now should belong to the previous year and not the
                    # current one FIXME: this breaks if we investigate
                    # sosreports older than one year :/
                    for i in self.reboots:
                        t = self.reboots[i]['date']
                        # Remember which dates were decremented and only do it
                        # once
                        if i <= counter and \
                                'decremented' not in self.reboots[i]:
                            d = t - relativedelta(years=1)
                            self.reboots[i]['date'] = d
                            self.reboots[i]['decremented'] = True
                prev_month = d.month
                self.reboots[counter] = {}
                self.reboots[counter]['date'] = d
                self.reboots[counter]['file'] = f
                counter += 1

    def parse(self):
        self.redhatrelease = open(os.path.join(self.path,
                                  'etc/redhat-release')).read().strip()
        self._parse_interrupts()
        self._parse_network()
        self._parse_reboots()


if __name__ == '__main__':
    sosreport = SosReport('./demosos')
    sosreport.parse()
    for i in sosreport.reboots:
        print("{0} - {1}".format(i, sosreport.reboots[i]))
