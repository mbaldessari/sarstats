from dateutil import parser
import os
import os.path
import re
import sys

# Interrupt parsine routines taken from python-linux-procfs (GPLv2)

class SOSReport:
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
                    d['users'] = [a.strip() for a in line[line.index(fields[self.nr_cpus + 1]):].split(',')]
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
            try:
                nirq = int(irq)
            except:
                continue
        return

    def _parse_disks(self):
        """Parse disk output files so that labels dev123-40 can be correctly
        mapped to an existing physical device"""
        return

    def _parse_reboots(self):
        """Parse /var/log/messages and find out when the machine rebooted.
        Returns an array of datetimes containing the times of reboot. First 
        uncompress /var/log/messages*, go through them and search for lines like 
        'Dec  4 11:02:05 illins04 kernel: Linux version 2.6.32-279.5.2.el6.x86_64'.
        We parse messages* files because 'LINUX RESTART' in sar files is not precise"""
        # FIXME: uncompress any compressed messages files
        # FIXME: need to solve the fact that no year is present in /var/log/messages
        messages_dir = os.path.join(self.path, 'var/log')
        reboots = {}
        reboot_re = r'.*kernel: Linux version.*$'
        for i in os.listdir(messages_dir):
            if not i.startswith('messages'):
                continue
            f = open(os.path.join(messages_dir, i))
            for line in f.readlines():
                line = line.strip()
                if not re.match(reboot_re, line):
                    continue

                tokens = line.split()[0:3]
                d = parser.parse(" ".join(tokens)) 
                self.reboots[d] = True

        return

    def parse(self):
        self.redhatrelease = open(os.path.join(self.path,
            'etc/redhat-release')).read().strip()
        self._parse_interrupts()
        self._parse_network()
        self._parse_reboots()

if __name__ == '__main__':
    sosreport = SOSReport('./demosos2')
    sosreport.parse()
    for i in sosreport.interrupts.keys():
        print("{0}: {1}".format(i, sosreport.interrupts[i]))
