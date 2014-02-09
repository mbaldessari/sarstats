import os
import os.path
import sys

# Interrupt parsine routines taken from python-linux-procfs (GPLv2)

class SOSReport:
    def __init__(self, path):
        if not os.path.isdir(path):
            raise Exception("{0} does not exist".format(path))

        sosxml = os.path.join(path, 'sos_reports/sosreport.xml')
        if not os.path.exists(sosxml):
            raise Exception("{0} does not exist".format(sosxml))

        self.path = path
        self.redhatrelease = None
        self.packages = []
        self.interrupts = {}
        self.networking = {}

    def _parse_network(self):
        """Parse network configuration and create a hash like the following:
        self.network['eth0'] = {'module': 'igb', ipv4: ['10.0.0.1/24'],
        ipv6: ['fe80::2e41:38ff:feab:99e2/64'], 'firmware': '1.20', 
        'bus-info': '0000:01:00.0', 'version': '3.133'"""
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
        intr_file = os.path.join(self.path, '/proc/interrupts')
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

    def parse(self):
        self.redhatrelease = open(os.path.join(self.path,
            'etc/redhat-release')).read().strip()
        self._parse_network()
        self._parse_interrupts()

if __name__ == '__main__':
    sosreport = SOSReport('./demosos')
    sosreport.parse()
    print(sosreport.redhatrelease)
    print(sosreport.interrupts)
