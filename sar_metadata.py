# categories.py - sar(1) report graphing utility
# Copyright (C) 2012  Ray Dassen
#               2013  Ray Dassen, Michele Baldessari
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
import re


# Column titles that represent another layer of indexing
# i.e. timestamp -> index -> another column -> datum
_indexcolumn = set(['CPU', 'IFACE', 'DEV', 'INTR', 'FAN', 'TEMP', 'BUS',
    'FILESYSTEM', 'TTY'])

# Regular expressions to recognise various types of data found in sar
# files, to be used as building blocks.
# Notes:
# * These REs do not introduce any groups.
# * These REs are used to build up extended REs, so whitespace needs to
#   be matched through \s.
_timestamp_regexp = r'\d{2}:\d{2}:\d{2}(?:\sAM|\sPM)?'
_integer_regexp = r'[+-]?\d+'
_hex_regexp = r'[a-fA-F0-9]+'
_number_with_decimals_regexp = r'(?:[+-]?\d+\.\d+|nan)'
_interface_name_regexp = r'[^ \t]+'
_usb_name_regexp = r'[^\t]+'
_fs_name_regexp = r'[^\t]+'
_device_name_regexp = _interface_name_regexp
_interrupts_regexp = r'(?:' + _number_with_decimals_regexp + '|N/A)'
_cpu_regexp = r'(?:all|\d+)'
_intr_regexp = r'(?:sum|\d+)'

base_graphs = {
    '%user':    {'cat': 'Utilization',
                 'label': 'User Utilization (%)',
                 'unit': 'percentage',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Percentage of CPU utilization that occurred while
                 executing at the user level (application). Note that this
                 field includes time spent running virtual processors""",
                 'detail': 'Column 1 of /proc/stat'},
    '%usr':     {'cat': 'Utilization',
                 'regexp': _number_with_decimals_regexp,
                 'label': 'User Utilization (novirt %)',
                 'unit': 'percentage',
                 'desc': """Percentage of CPU utilization that occurred while
                 executing at the user level (application). Note that this
                 field does NOT include time spent running virtual
                 processors""",
                 'detail': ''},
    '%system':  {'cat': 'Utilization',
                 'regexp': _number_with_decimals_regexp,
                 'unit': 'percentage',
                 'desc': """Percentage of CPU utilization that occurred while
                 executing at the system level (kernel). Note that this field
                 includes time spent servicing hardware and software
                 interrupts"""},
    '%sys':     {'cat': 'Utilization',
                 'regexp': _number_with_decimals_regexp,
                 'unit': 'percentage',
                 'desc': """Percentage of CPU utilization that occurred while
                 executing at the system level (kernel). Note that this field
                 does NOT include time spent servicing hardware or software
                 interrupts"""},
    '%iowait':  {'cat': 'Utilization',
                 'regexp': _number_with_decimals_regexp,
                 'unit': 'percentage',
                 'desc': """Percentage of time that the CPU or CPUs were idle
                 during which the system had an outstanding disk I/O
                 request"""},
    '%irq':     {'cat': 'Utilization',
                 'regexp': _number_with_decimals_regexp,
                 'unit': 'percentage',
                 'desc': """Percentage of time spent by the CPU or CPUs to
                 service hardware interrupts"""},
    '%soft':    {'cat': 'Utilization',
                 'regexp': _number_with_decimals_regexp,
                 'unit': 'percentage',
                 'desc': """Percentage of time spent by the CPU or CPUs to
                 service software interrupts"""},
    '%nice':    {'cat': 'Utilization',
                 'regexp': _number_with_decimals_regexp,
                 'unit': 'percentage',
                 'desc': """Percentage of CPU utilization that occurred while 
                 executing at the user level with nice priority"""},
    '%gnice':   {'cat': 'Utilization',
                 'regexp': _number_with_decimals_regexp,
                 'unit': 'percentage',
                 'desc': """Percentage of time spent by the CPU or CPUs to run
                 a niced guest"""},
    '%idle':    {'cat': 'Utilization',
                 'regexp': _number_with_decimals_regexp,
                 'unit': 'percentage',
                 'desc': """Percentage of time that the CPU or CPUs were idle
                 and the system did not have an outstanding disk I/O
                 request"""},
    '%steal':   {'cat': 'Utilization',
                 'regexp': _number_with_decimals_regexp,
                 'unit': 'percentage',
                 'desc': """Percentage of time that the CPU or CPUs were idle
                 and the system did not have an outstanding disk I/O
                 request"""},
    '%guest':   {'cat': 'Utilization',
                 'unit': 'percentage',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Percentage of time spent by the CPU or CPUs to run
                 a virtual processor"""},
    'runq-sz':  {'cat': 'Load',
                 'regexp': _integer_regexp,
                 'unit': 'number',
                 'desc': """Run queue length (number of tasks waiting for run
                 time)"""},
    'plist-sz': {'cat': 'Load',
                 'unit': 'number',
                 'regexp': _integer_regexp,
                 'desc': """Number of tasks in the task list"""},
    'ldavg-1':  {'cat': 'Load',
                 'unit': 'number',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """System load average for the last minute. The load
                 average is calculated as the average number of runnable or
                 running tasks (R state), and the number of tasks in
                 uninterruptible sleep (D state) over the specified
                 interval. The exact formula is:
                 <i>load(t) = n+((load(t-1)-n)/e^(interval/(min*60)))</i><br/>
                 &bull;<i>load(t)</i>: load average at a time of t<br/>
                 &bull;<i>n</i>: number of threads in running or uninterruptible state<br/>
                 &bull;<i>interval</i>: calculate interval (seconds). 5 seconds in RHEL<br/>
                 &bull;<i>min</i>: average time (minute)<br/>
                 It is a moving average function. See 
                 <link href="http://lxr.free-electrons.com/source/kernel/sched.c?v=2.6.32#L3138">
                 <i>kernel/sched.c:calc_load()</i></link> for more details on the implementation on RHEL 5 and 6. 
                 More recent kernels moved it to 
                 <link href="http://lxr.free-electrons.com/source/kernel/sched.c?v=2.6.32#L3138">
                 <i>kernel/sched/proc.c:calc_load()</i></link>"""},
    'ldavg-5':  {'cat': 'Load',
                 'unit': 'number',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """System load average for the past 5 minutes"""},
    'ldavg-15': {'cat': 'Load',
                 'unit': 'number',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """System load average for the past 15 minutes"""},
    'blocked':  {'cat': 'Load',
                 'unit': 'number',
                 'regexp': _integer_regexp,
                 'desc': """Number of tasks currently blocked, waiting for I/O
                 to complete"""},
    'proc/s':   {'cat': 'Load',
                 'unit': 'number_per_second',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Total number of tasks created per second"""},
    'cswch/s':  {'cat': 'Load',
                 'unit': 'number_per_second',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Total number of context switches per second"""},
    'kbmemfree':{'cat': 'Memory',
                 'unit': 'kilobytes',
                 'regexp': _integer_regexp,
                 'desc': """Amount of free memory available in kilobytes"""},
    'kbmemused':{'cat': 'Memory',
                 'regexp': _integer_regexp,
                 'unit': 'kilobytes',
                 'desc': """Amount of used memory in kilobytes. This does not
                 take into account memory used by the kernel itself"""},
    '%memused': {'cat': 'Memory',
                 'regexp': _number_with_decimals_regexp,
                 'unit': 'percentage',
                 'desc': """Percentage of used memory"""},
    'kbbuffers':{'cat': 'Memory',
                 'regexp': _integer_regexp,
                 'unit': 'kilobytes',
                 'desc': """Amount of memory used as buffers by the kernel in
                 kilobytes"""},
    'kbcached': {'cat': 'Memory',
                 'regexp': _integer_regexp,
                 'unit': 'kilobytes',
                 'desc': """Amount of memory used to cache data by the kernel
                 in kilobytes"""},
    'kbcommit': {'cat': 'Memory',
                 'regexp': _integer_regexp,
                 'unit': 'kilobytes',
                 'desc': """Amount of memory in kilobytes needed for current
                 workload.  This is an estimate of how much RAM/swap is needed
                 to guarantee that there never is out of memory"""},
    '%commit':  {'cat': 'Memory',
                 'unit': 'percentage',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Percentage of memory needed for current workload in
                 relation to the total amount of memory (RAM+swap). This number
                 may be greater than 100% because the kernel usually
                 overcommits memory"""},
    'kbactive': {'cat': 'Memory',
                 'regexp': _integer_regexp,
                 'unit': 'kilobytes',
                 'desc': """Amount of active memory in kilobytes (memory that
                 has been used more recently and usually not reclaimed unless
                 absolutely necessary)"""},
    'kbinact':  {'cat': 'Memory',
                 'unit': 'kilobytes',
                 'regexp': _integer_regexp,
                 'desc': """Amount of inactive memory in kilobytes (memory
                 which has been less recently used. It is more eligible to be
                 reclaimed for other purposes)"""},
    'kbdirty':  {'cat': 'Memory',
                 'unit': 'kilobytes',
                 'regexp': _integer_regexp,
                 'desc': """Amount of memory in kilobytes waiting to get
                 written back to the disk."""},
    'kbhugfree':{'cat': 'Memory',
                 'unit': 'kilobytes',
                 'regexp': _integer_regexp,
                 'desc': """Amount of hugepages memory in kilobytes that is not
                 yet allocated"""},
    'kbhugused':{'cat': 'Memory',
                 'regexp': _integer_regexp,
                 'unit': 'kilobytes',
                 'desc': """Amount of hugepages memory in kilobytes that has
                 been allocated"""},
    '%hugused':{'cat': 'Memory',
                 'regexp': _number_with_decimals_regexp,
                 'unit': 'percentage',
                 'desc': """Percentage of total hugepages memory that has been
                 allocated"""},
    'frmpg/s':  {'cat': 'Memory',
                 'regexp': _number_with_decimals_regexp,
                 'unit': 'number_per_second',
                 'desc': """Number of memory pages freed by the system per
                 second. A negative value represents a number of pages
                 allocated by the system.  Note that a page has a size of 4 kB
                 or 8 kB according to the machine architecture"""},
    'bufpg/s':  {'cat': 'Memory',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of additional memory pages used as buffers
                 by the system per second. A negative value means fewer pages
                 used as buffers by the system"""},
    'campg/s':  {'cat': 'Memory',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of additional memory pages cached by the
                 system per second. A negative value means fewer pages in the
                 cache"""},
    'pswpin/s': {'cat': 'Swap',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Total number of swap pages the system brought in
                 per second"""},
    'pswpout/s':{'cat': 'Swap',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Total number of swap pages the system brought out
                 per second"""},
    'kbswpfree':{'cat': 'Swap',
                 'regexp': _integer_regexp,
                 'desc': """Amount of free swap space in kilobytes"""},
    'kbswpused':{'cat': 'Swap',
                 'regexp': _integer_regexp,
                 'desc': """Amount of used swap space in kilobytes"""},
    '%swpused': {'cat': 'Swap',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Percentage of used swap space"""},
    'kbswpcad': {'cat': 'Swap',
                 'regexp': _integer_regexp,
                 'desc': """Amount of cached swap memory in kilobytes. This is
                 memory that once was swapped out, is swapped back in but still
                 also is in the swap area (if memory is needed it doesn\'t need
                 to be swapped out again because it is already in the swap
                 area. This saves I/O)"""},
    '%swpcad':  {'cat': 'Swap',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Percentage of cached swap memory in relation to the
                 amount of used swap space"""},
    'nswap/s':  {'cat': 'Swap',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of pages from the process address space the
                 system has swapped out per second. This value is always zero
                 with post 2.5 kernels"""},
    'tps':      {'cat': 'I/O',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Total number of transfers per second that were
                 issued to physical devices. A transfer is an I/O request to a
                 physical device. Multiple logical requests can be combined
                 into a single I/O request to the device. A transfer is of
                 indeterminate size"""},
    'rtps':     {'cat': 'I/O',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Total number of read requests per second issued to
                 physical devices"""},
    'wtps':     {'cat': 'I/O',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Total number of write requests per second issued to
                 physical devices"""},
    'bread/s':  {'cat': 'I/O',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Total amount of data read from the devices in
                 blocks per second. Blocks are equivalent to sectors with 2.4
                 kernels and newer and therefore have a size of 512 bytes. With
                 older kernels, a block is of indeterminate size"""},
    'bwrtn/s':  {'cat': 'I/O',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Total amount of data written to devices in blocks
                 per second"""},
    'rxkB/s':   {'cat': 'I/O',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Total number of kilobytes received per second"""},
    'txkB/s':   {'cat': 'I/O',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Total number of kilobytes transmitted per
                 second"""},
    'tps':      {'cat': 'I/O',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Indicates the number of transfers per second that
                 were issued to the device. Multiple logical requests can be
                 combined into a single I/O request to the device. A transfer
                 is of indeterminate size."""},
    'rd_sec/s': {'cat': 'I/O',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of sectors read from the device. The size of
                 a sector is 512 bytes."""},
    'wr_sec/s': {'cat': 'I/O',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of sectors written to the device. The size
                 of a sector is 512 bytes."""},
    'avgrq-sz': {'cat': 'I/O',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The average size (in sectors) of the requests that
                 were issued to the device."""},
    'avgqu-sz': {'cat': 'I/O',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The average queue length of the requests that were
                 issued to the device."""},
    'await':    {'cat': 'I/O',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The average time (in milliseconds) for I/O requests
                 issued to the device to be served. This includes the time
                 spent by the requests in queue and the time spent servicing
                 them."""},
    'svctm':    {'cat': 'I/O',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The average service time (in milliseconds) for I/O
                 requests that were issued to the device. Warning! Do not trust
                 this field any more.  This field will be removed in a future
                 sysstat version."""},
    '%util':    {'cat': 'I/O',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Percentage of CPU time during which I/O requests
                 were issued to the device (bandwidth utilization for the
                 device). Device saturation occurs when this value is close to
                 100%"""},
    'maxpower': {'cat': 'Power',
                 'regexp': _integer_regexp,
                 'desc': """Maxpower"""},
    'MHz':      {'cat': 'Power',
                 'regexp': _integer_regexp,
                 'desc': """MegaHertz"""},
    'FAN':      {'cat': 'Power',
                 'regexp': _integer_regexp,
                 'desc': """FAN"""},
    '%temp':    {'cat': 'Power',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """FAN"""},
    'degC':     {'cat': 'Power',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Degrees"""},
    'drpm':     {'cat': 'Power',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """DRPM"""},
    'rpm':      {'cat': 'Power',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """RPM"""},
    'pgpgin/s': {'cat': 'Paging',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Total number of kilobytes the system paged in from
                 disk per second. Note: With old kernels (2.2.x) this value is
                 a number of blocks per second (and not kilobytes)"""},
    'pgpgout/s':{'cat': 'Paging',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Total number of kilobytes the system paged out to
                 disk per second.  Note: With old kernels (2.2.x) this value is
                 a number of blocks per second (and not kilobytes)"""},
    'fault/s':  {'cat': 'Paging',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of page faults (major + minor) made by the
                 system per second.  This is not a count of page faults that
                 generate I/O, because some page faults can be resolved without
                 I/O"""},
    'majflt/s': {'cat': 'Paging',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of major faults the system has made per
                 second, those which have required loading a memory page from
                 disk"""},
    'minflt/s': {'cat': 'Paging',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Total number of minor faults the task has made per
                 second, those which have not required loading a memory page
                 from disk"""},
    'pgfree/s': {'cat': 'Paging',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of pages placed on the free list by the
                 system per second"""},
    'pgscank/s':{'cat': 'Paging',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of pages scanned by the kswapd daemon per
                 second"""},
    'pgscand/s':{'cat': 'Paging',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of pages scanned directly per second"""},
    'pgsteal/s':{'cat': 'Paging',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of pages the system has reclaimed from cache
                 (pagecache and swapcache) per second to satisfy its memory
                 demands"""},
    '%vmeff':   {'cat': 'Paging',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Calculated as pgsteal / pgscan, this is a metric of
                 the efficiency of page reclaim. If it is near 100% then almost
                 every page coming off the tail of the inactive list is being
                 reaped. If it gets too low (e.g. less than 30%) then the
                 virtual memory is having some difficulty. This field is
                 displayed as zero if no pages have been scanned during the
                 interval of time"""},
    'file-nr':  {'cat': 'Files',
                 'regexp': _integer_regexp,
                 'desc': """Number of file handles used by the system"""},
    'inode-nr': {'cat': 'Files',
                 'regexp': _integer_regexp,
                 'desc': """Number of inode handlers used by the system"""},
    'file-sz':  {'cat': 'Files',
                 'regexp': _integer_regexp,
                 'desc': """Number of used file handles"""},
    'inode-sz': {'cat': 'Files',
                 'regexp': _integer_regexp,
                 'desc': """Number of used inode handlers"""},
    'super-sz': {'cat': 'Files',
                 'regexp': _integer_regexp,
                 'desc': """Number of super block handlers allocated by the
                 kernel"""},
    '%super-sz':{'cat': 'Files',
                 'regexp': _number_with_decimals_regexp,
                'desc': """Percentage of allocated super block handlers with
                regard to the maximum number of super block handlers that Linux
                can allocate"""},
    'dquot-sz': {'cat': 'Files',
                 'regexp': _integer_regexp,
                 'desc': """Number of allocated disk quota entries"""},
    '%dquot-sz':{'cat': 'Files',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Percentage of allocated disk quota entries with
                 regard to the maximum number of cached disk quota entries that
                 can be allocated"""},
    'dentunusd':{'cat': 'Files',
                 'regexp': _integer_regexp,
                 'desc': """Number of unused cache entries in the directory
                 cache"""},
    'MBfsfree': {'cat': 'Files',
                 'regexp': _integer_regexp,
                 'desc': """MB Free"""},
    'MBfsused': {'cat': 'Files',
                 'regexp': _integer_regexp,
                 'desc': """MB Used"""},
    '%fsused':  {'cat': 'Files',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """FS Used %"""},
    '%ufsused': {'cat': 'Files',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """FS uUsed %"""},
    'Ifree':    {'cat': 'Files',
                 'regexp': _integer_regexp,
                 'desc': """Inodes Free"""},
    'Iused':    {'cat': 'Files',
                 'regexp': _integer_regexp,
                 'desc': """Inodes Used"""},
    '%Iused':   {'cat': 'Files',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Inodes Used %"""},
    'rtsig-sz': {'cat': 'Other',
                 'regexp': _integer_regexp,
                 'desc': """Number of queued RT signals"""},
    '%rtsig-sz':{'cat': 'Other',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Percentage of queued RT signals with regard to the
                 maximum number of RT signals that can be queued"""},
    'pty-nr':   {'cat': 'Other',
                 'regexp': _integer_regexp,
                 'desc': """Number of pseudo-terminals used by the system"""},
    'call/s':   {'cat': 'NFS',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of RPC requests made per second"""},
    'retrans/s':{'cat': 'NFS',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of RPC requests per second, those which
                 needed to be retransmitted (for example because of a server
                 timeout)"""},
    'read/s':   {'cat': 'NFS',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of "read" RPC calls made per second"""},
    'write/s':  {'cat': 'NFS',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of "write" RPC calls made per second"""},
    'access/s': {'cat': 'NFS',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of "access" RPC calls made per second"""},
    'getatt/s': {'cat': 'NFS',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of "getattr" RPC calls made per second"""},
    'scall/s':  {'cat': 'NFSD',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of RPC requests received per second"""},
    'badcall/s':{'cat': 'NFSD',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of bad RPC requests received per second,
                 those whose processing generated an error"""},
    'packet/s': {'cat': 'NFSD',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of network packets received per second"""},
    'udp/s':    {'cat': 'NFSD',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of UDP packets received per second"""},
    'tcp/s':    {'cat': 'NFSD',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of TCP packets received per second"""},
    'hit/s':    {'cat': 'NFSD',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of reply cache hits per second"""},
    'miss/s':   {'cat': 'NFSD',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of reply cache misses per second"""},
    'sread/s':  {'cat': 'NFSD',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of "read" RPC calls received per second"""},
    'swrite/s': {'cat': 'NFSD',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of "write" RPC calls received per
                 second"""},
    'saccess/s':{'cat': 'NFSD',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of "access" RPC calls received per
                 second"""},
    'sgetatt/s':{'cat': 'NFSD',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of "getattr" RPC calls received per
                 second"""},
    'rcvin/s':  {'cat': 'TTY',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of receive interrupts per second for current
                 serial line. Serial line number is given in the TTY
                 column"""},
    'xmtin/s':  {'cat': 'TTY',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of transmit interrupts per second for
                 current serial line""",
                 'detail': 'Taken from /proc/net/dev'},
    'framerr/s':{'cat': 'TTY',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of frame errors per second for current
                 serial line"""},
    'prtyerr/s':{'cat': 'TTY',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of parity errors per second for current
                 serial line"""},
    'brk/s':    {'cat': 'TTY',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of breaks per second for current serial
                 line"""},
    'ovrun/s':  {'cat': 'TTY',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of overrun errors per second for current
                 serial line"""},
    'totsck':   {'cat': 'Network',
                 'regexp': _integer_regexp,
                 'desc': """Total number of sockets used by the system"""},
    'tcpsck':   {'cat': 'Network',
                 'regexp': _integer_regexp,
                 'desc': """Number of TCP sockets currently in use"""},
    'udpsck':   {'cat': 'Network',
                 'regexp': _integer_regexp,
                 'desc': """Number of UDP sockets currently in use"""},
    'rawsck':   {'cat': 'Network',
                 'regexp': _integer_regexp,
                 'desc': """Number of RAW sockets currently in use"""},
    'ip-frag':  {'cat': 'Network',
                 'regexp': _integer_regexp,
                 'desc': """Number of IP fragments currently in use"""},
    'tcp-tw':   {'cat': 'Network',
                 'regexp': _integer_regexp,
                 'desc': """Number of TCP sockets in TIME_WAIT state"""},
    'rxpck/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Total number of packets received per second"""},
    'txpck/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Total number of packets transmitted per second"""},
    'rxbyt/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Total number of bytes received per second"""},
    'txbyt/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Total number of bytes transmitted per
                 'regexp': _number_with_decimals_regexp,
                 second"""},
    'rxcmp/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of compressed packets received per second
                 (for cslip etc.)"""},
    'txcmp/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of compressed packets transmitted per
                 second"""},
    'rxmcst/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of multicast packets received per
                 second"""},
    'rxerr/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Total number of bad packets received per
                 second"""},
    'txerr/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Total number of errors that happened per second
                 while transmitting packets"""},
    'coll/s':   {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of collisions that happened per second while
                 transmitting packets"""},
    'rxdrop/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of received packets dropped per second
                 because of a lack of space in linux buffers"""},
    'txdrop/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of transmitted packets dropped per second
                 because of a lack of space in linux buffers"""},
    'txcarr/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of carrier-errors that happened per second
                 while transmitting packets"""},
    'rxfram/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of frame alignment errors that happened per
                 second on received packets"""},
    'rxfifo/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of FIFO overrun errors that happened per
                 second on received packets"""},
    'txfifo/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """Number of FIFO overrun errors that happened per
                 second on transmitted packets"""},
    'irec/s':   {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The total number of input datagrams received from
                 interfaces per second, including those received in error
                 [ipInReceives]."""},
    'fwddgm/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of input datagrams per second, for which
                 this entity was not their final IP destination, as a result of
                 which an attempt was made to find a route to forward them to
                 that final destination [ipForwDatagrams]"""},
    'idel/s':   {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The total number of input datagrams successfully
                 delivered per second to IP user-protocols (including ICMP)
                 [ipInDelivers]"""},
    'orq/s':    {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The total number of IP datagrams which local IP
                 user-protocols (including ICMP) supplied per second to IP in
                 requests for transmission [ipOutRequests]. Note that this
                 counter does not include any datagrams counted in
                 fwddgm/s"""},
    'asmrq/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of IP fragments received per second
                 which needed to be reassembled at this entity
                 [ipReasmReqds]"""},
    'asmok/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of IP datagrams successfully
                 re-assembled per second [ipReasmOKs]"""},
    'fragok/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of IP datagrams that have been
                 successfully fragmented at this entity per second
                 [ipFragOKs]"""},
    'fragcrt/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of IP datagram fragments that have been
                 generated per second as a result of fragmentation at this
                 entity [ipFragCreates]"""},
    'ihdrerr/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of input datagrams discarded per second
                 due to errors in their IP headers, including bad checksums,
                 version number mismatch, other format errors, time-to-live
                 exceeded, errors discovered in processing their IP options,
                 etc. [ipInHdrErrors]"""},
    'iadrerr/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of input datagrams discarded per second
                 because the IP address in their IP header's destination field
                 was not a valid address to be received at this entity. This
                 count includes invalid addresses (e.g., 0.0.0.0) and addresses
                 of unsupported Classes (e.g., Class E). For entities which are
                 not IP routers and therefore do not forward datagrams, this
                 counter includes datagrams discarded because the destination
                 address was not a local address [ipInAddrErrors]."""},
    'iukwnpr/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of locally-addressed datagrams received
                 successfully but discarded per second because of an unknown or
                 unsupported protocol [ipInUnknownProtos]."""},
    'idisc/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of input IP datagrams per second for
                 which no problems were encountered to prevent their continued
                 processing, but which were discarded (e.g., for lack of buffer
                 space) [ipInDiscards]. Note that this counter does not include
                 any datagrams discarded while awaiting re-assembly"""},
    'odisc/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of output IP datagrams per second for
                 which no problem was encountered to prevent their transmission
                 to their destination, but which were discarded (e.g., for lack
                 of buffer space) [ipOutDiscards]. Note that this counter would
                 include datagrams counted in fwddgm/s if any such packets met
                 this (discretionary) discard criterion"""},
    'onort/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of IP datagrams discarded per second
                 because no route could be found to transmit them to their
                 destination [ipOutNoRoutes]. Note that this counter includes
                 any packets counted in fwddgm/s which meet this 'no-route'
                 criterion. Note that this includes any datagrams which a host
                 cannot route because all of its default routers are down"""},
    'asmf/s':   {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of failures detected per second by the
                 IP re-assembly algorithm (for whatever reason: timed out,
                 errors, etc) [ipReasmFails]. Note that this is not necessarily
                 a count of discarded IP fragments since some algorithms can
                 lose track of the number of fragments by combining them as
                 they are received"""},
    'fragf/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of IP datagrams that have been discarded
                 per second because they needed to be fragmented at this entity
                 but could not be, e.g., because their Don't Fragment flag was
                 set [ipFragFails]"""},
    'imsg/s':   {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The total number of ICMP messages which the entity
                 received per second [icmpInMsgs]. Note that this counter
                 includes all those counted by ierr/s"""},
    'omsg/s':   {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The total number of ICMP messages which this entity
                 attempted to send per second [icmpOutMsgs]. Note that this
                 counter includes all those counted by oerr/s"""},
    'iech/s':   {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Echo (request) messages received
                 per second [icmpInEchos]"""},
    'iechr/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Echo Reply messages received per
                 second [icmpInEchoReps]"""},
    'oech/s':   {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Echo (request) messages sent per
                 second [icmpOutEchos]"""},
    'oechr/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Echo Reply messages sent per
                 second [icmpOutEchoReps]"""},
    'itm/s':    {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Timestamp (request) messages
                 received per second [icmpInTimestamps]"""},
    'itmr/s':   {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Timestamp Reply messages
                 received per second [icmpInTimestampReps]"""},
    'otm/s':    {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Timestamp (request) messages
                 sent per second [icmpOutTimestamps]"""},
    'otmr/s':   {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Timestamp Reply messages sent
                 per second [icmpOutTimestampReps]"""},
    'iadrmk/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Address Mask Request messages
                 received per second [icmpInAddrMasks]"""},
    'iadrmkr/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Address Mask Reply messages
                 received per second [icmpInAddrMaskReps]"""},
    'oadrmk/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Address Mask Request messages
                 sent per second [icmpOutAddrMasks]"""},
    'oadrmkr/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Address Mask Reply messages sent
                 per second [icmpOutAddrMaskReps]"""},
    'ierr/s':   {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP messages per second which the
                 entity received but determined as having ICMP-specific errors
                 (bad ICMP checksums, bad length, etc.) [icmpInErrors]."""},
    'oerr/s':   {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP messages per second which this
                 entity did not send due to problems discovered within ICMP
                 such as a lack of buffers [icmpOutErrors]"""},
    'idstunr/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Destination Unreachable messages
                 received per second [icmpInDestUnreachs]"""},
    'odstunr/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Destination Unreachable messages
                 sent per second [icmpOutDestUnreachs]"""},
    'itmex/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Time Exceeded messages received
                 per second [icmpInTimeExcds]"""},
    'otmex/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Time Exceeded messages sent per
                 second [icmpOutTimeExcds]"""},
    'iparmpb/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Parameter Problem messages
                 received per second [icmpInParmProbs]"""},
    'oparmpb/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Parameter Problem messages sent
                 per second [icmpOutParmProbs]"""},
    'isrcq/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Source Quench messages received
                 per second [icmpInSrcQuenchs]"""},
    'osrcq/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Source Quench messages sent per
                 second [icmpOutSrcQuenchs]"""},
    'iredir/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Redirect messages received per
                 second [icmpInRedirects]"""},
    'oredir/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Redirect messages sent per
                 second [icmpOutRedirects]"""},
    'active/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of times TCP connections have made a
                 direct transition to the SYN-SENT state from the CLOSED state
                 per second [tcpActiveOpens]"""},
    'passive/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of times TCP connections have made a
                 direct transition to the SYN-RCVD state from the LISTEN state
                 per second [tcpPassiveOpens]"""},
    'iseg/s':   {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The total number of segments received per second,
                 including those received in error [tcpInSegs]. This count
                 includes segments received on currently established
                 connections."""},
    'oseg/s':   {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The total number of segments sent per second,
                 including those on current connections but excluding those
                 containing only retransmitted octets [tcpOutSegs]"""},
    'atmptf/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of times per second TCP connections have
                 made a direct transition to the CLOSED state from either the
                 SYN-SENT state or the SYN-RCVD state, plus the number of times
                 per second TCP connections have made a direct transition to
                 the LISTEN state from the SYN-RCVD state
                 [tcpAttemptFails]"""},
    'estres/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of times per second TCP connections have
                 made a direct transition to the CLOSED state from either the
                 ESTABLISHED state or the CLOSE-WAIT state
                 [tcpEstabResets]"""},
    # original sar name is retrans/s which is duplicate. we rename it on the fly
    'retrant/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The total number of segments retransmitted per
                 second - that is, the number of TCP segments transmitted
                 containing one or more previously transmitted octets
                 [tcpRetransSegs]"""},
    'isegerr/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The total number of segments received in error
                 (e.g., bad TCP checksums) per second [tcpInErrs]"""},
    'orsts/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of TCP segments sent per second
                 containing the RST flag [tcpOutRsts]"""},
    'idgm/s':   {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The total number of UDP datagrams delivered per
                 second to UDP users [udpInDatagrams]"""},
    'odgm/s':   {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The total number of UDP datagrams sent per second
                 from this entity [udpOutDatagrams]"""},
    'noport/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The total number of received UDP datagrams per
                 second for which there was no
                 application at the destination port [udpNoPorts]"""},
    'idgmerr/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of received UDP datagrams per second
                 that could not be delivered for reasons other than the lack of
                 an application at the destination port [udpInErrors]"""},
    'tcp6sck':  {'cat': 'Network',
                 'regexp': _integer_regexp,
                 'desc': """Number of TCPv6 sockets currently in use"""},
    'udp6sck':  {'cat': 'Network',
                 'regexp': _integer_regexp,
                 'desc': """Number of UDPv6 sockets currently in use"""},
    'raw6sck':  {'cat': 'Network',
                 'regexp': _integer_regexp,
                 'desc': """Number of RAWv6 sockets currently in use"""},
    'ip6-frag': {'cat': 'Network',
                 'regexp': _integer_regexp,
                 'desc': """Number of IPv6 fragments currently in use"""},
    'irec6/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The total number of input datagrams received from
                 interfaces per second, including those received in error
                 [ipv6IfStatsInReceives]"""},
    'fwddgm6/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of output datagrams per second which
                 this entity received and forwarded to their final destinations
                 [ipv6IfStatsOutForwDatagrams]"""},
    'idel6/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The total number of datagrams successfully
                 delivered per second to IPv6 user-protocols (including ICMP)
                 [ipv6IfStatsInDelivers"""},
    'orq6/s':   {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The total number of IPv6 datagrams which local IPv6
                 user-protocols (including ICMP) supplied per second to IPv6 in
                 requests for transmission [ipv6IfStatsOutRequests]. Note that
                 this counter does not include any datagrams counted in
                 fwddgm6/s"""},
    'asmrq6/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of IPv6 fragments received per second
                 which needed to be reassembled at this interface
                 [ipv6IfStatsReasmReqds"""},
    'asmok6/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of IPv6 datagrams successfully
                 reassembled per second [ipv6IfStatsReasmOKs]"""},
    'imcpck6/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of multicast packets received per second
                 by the interface [ipv6IfStatsInMcastPkts]"""},
    'omcpck6/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of multicast packets transmitted per
                 second by the interface [ipv6IfStatsOutMcastPkts]"""},
    'fragok6/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of IPv6 datagrams that have been
                 successfully fragmented at this output interface per second
                 [ipv6IfStatsOutFragOKs]"""},
    'fragcr6/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of output datagram fragments that have
                 been generated per second as a result of fragmentation at this
                 output interface [ipv6IfStatsOutFragCreates] """},
    'ihdrer6/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of input datagrams discarded per second
                 due to errors in their IPv6 headers, including version number
                 mismatch, other format errors, hop count exceeded, errors
                 discovered in processing their IPv6 options, etc.
                 [ipv6IfStatsInHdrErrors]"""},
    'iadrer6/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of input datagrams discarded per second
                 because the IPv6 address in their IPv6 header's destination
                 field was not a valid address to be received at this entity.
                 This count includes invalid addresses (e.g., ::0) and
                 unsupported addresses (e.g., addresses with unallocated
                 prefixes). For entities which are not IPv6 routers and
                 therefore do not forward datagrams, this counter includes
                 datagrams discarded because the destination address was not a
                 local address [ipv6IfStatsInAddrErrors]"""},
    'iukwnp6/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of locally-addressed datagrams received
                 successfully but discarded per second because of an unknown or
                 unsupported protocol [ipv6IfStatsInUnknownProtos]"""},
    'i2big6/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of input datagrams that could not be
                 forwarded per second because their size exceeded the link MTU
                 of outgoing interface [ipv6IfStatsInTooBigErrors]"""},
    'idisc6/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of input IPv6 datagrams per second for
                 which no problems were encountered to prevent their continued
                 processing, but which were discarded (e.g., for lack of buffer
                 space) [ipv6IfStatsInDiscards]. Note that this counter does
                 not include any datagrams discarded while awaiting
                 re-assembly"""},
    'odisc6/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of output IPv6 datagrams per second for
                 which no problem was encountered to prevent their transmission
                 to their destination, but which were discarded (e.g., for lack
                 of buffer space) [ipv6IfStatsOutDiscards]. Note that this
                 counter would include datagrams counted in fwddgm6/s if any
                 such packets met this (discretionary) discard criterion."""},
    'inort6/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of input datagrams discarded per second
                 because no route could be found to transmit them to their
                 destination [ipv6IfStatsInNoRoutes]"""},
    'onort6/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of locally generated IP datagrams
                 discarded per second because no route could be found to
                 transmit them to their destination [unknown formal SNMP
                     name]"""},
    'asmf6/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of failures detected per second by the
                  IPv6 re-assembly algorithm (for whatever reason: timed out,
                      errors, etc.) [ipv6IfStatsReasmFails]. Note that this is
                  not necessarily a count of discarded IPv6 fragments since
                  some algorithms can lose track of the number of fragments by
                  combining them as they are received"""},
    'fragf6/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of IPv6 datagrams that have been
                 discarded per second because they needed to be fragmented at
                 this output interface but could not be
                 [ipv6IfStatsOutFragFails]"""},
    'itrpck6/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of input datagrams discarded per second
                 because datagram frame didn't carry enough data
                 [ipv6IfStatsInTruncatedPkts]"""},
    'imsg6/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The total number of ICMP messages received by the
                 interface per second which includes all those counted by
                 ierr6/s [ipv6IfIcmpInMsgs]"""},
    'omsg6/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The total number of ICMP messages which this
                 interface attempted to send per second
                 [ipv6IfIcmpOutMsgs]"""},
    'iech6/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Echo (request) messages received
                 by the interface per second [ipv6IfIcmpInEchos]"""},
    'iechr6/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Echo Reply messages received by
                 the interface per second [ipv6IfIcmpInEchoReplies]"""},
    'oechr6/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Echo Reply messages sent by the
                 interface per second [ipv6IfIcmpOutEchoReplies]"""},
    'igmbq6/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMPv6 Group Membership Query
                 messages received by the interface per second
                 [ipv6IfIcmpInGroupMembQueries]"""},
    'igmbr6/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMPv6 Group Membership Response
                 messages received by the interface per second
                 [ipv6IfIcmpInGroupMembResponses] """},
    'ogmbr6/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMPv6 Group Membership Response
                 messages sent per second
                 [ipv6IfIcmpOutGroupMembResponses]"""},
    'igmbrd6/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMPv6 Group Membership Reduction
                 messages received by the interface per second
                 [ipv6IfIcmpInGroupMembReductions]."""},
    'ogmbrd6/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMPv6 Group Membership Reduction
                 messages sent per second
                 [ipv6IfIcmpOutGroupMembReductions]."""},
    'irtsol6/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Router Solicit messages received
                 by the interface per second [ipv6IfIcmpInRouterSolicits]."""},
    'ortsol6/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Router Solicitation messages
                 sent by the interface per second
                 [ipv6IfIcmpOutRouterSolicits]"""},
    'irtad6/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Router Advertisement messages
                 received by the interface per second
                 [ipv6IfIcmpInRouterAdvertisements]"""},
    'inbsol6/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Neighbor Solicit messages
                 received by the interface per second
                 [ipv6IfIcmpInNeighborSolicits]"""},
    'onbsol6/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Neighbor Solicitation messages
                 sent by the interface per second
                 [ipv6IfIcmpOutNeighborSolicits]"""},
    'inbad6/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Neighbor Advertisement messages
                 received by the interface per second
                 [ipv6IfIcmpInNeighborAdvertisements]"""},
    'onbad6/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Neighbor Advertisement messages
                 sent by the interface per second
                 [ipv6IfIcmpOutNeighborAdvertisements]."""},
    'ierr6/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP messages per second which the
                 interface received but determined as having ICMP-specific
                 errors (bad ICMP checksums, bad length, etc.)
                 [ipv6IfIcmpInErrors]"""},
    'idtunr6/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Destination Unreachable messages
                 received by the interface per second
                 [ipv6IfIcmpInDestUnreachs]"""},
    'odtunr6/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Destination Unreachable messages
                 sent by the interface per second
                 [ipv6IfIcmpOutDestUnreachs]"""},
    'itmex6/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Time Exceeded messages received
                 by the interface per second [ipv6IfIcmpInTimeExcds]"""},
    'otmex6/s': {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Time Exceeded messages sent by
                 the interface per second [ipv6IfIcmpOutTimeExcds]"""},
    'iprmpb6/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Parameter Problem messages
                 received by the interface per second
                 [ipv6IfIcmpInParmProblems]"""},
    'oprmpb6/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Parameter Problem messages sent
                 by the interface per second [ipv6IfIcmpOutParmProblems]"""},
    'iredir6/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of Redirect messages received by the
                 interface per second [ipv6IfIcmpInRedirects]"""},
    'oredir6/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of Redirect messages sent by the
                 interface by second [ipv6IfIcmpOutRedirects]"""},
    'ipck2b6/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Packet Too Big messages received
                 by the interface per second [ipv6IfIcmpInPktTooBigs]"""},
    'opck2b6/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of ICMP Packet Too Big messages sent by
                 the interface per second [ipv6IfIcmpOutPktTooBigs]"""},
    'idgm6/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The total number of UDP datagrams delivered per
                 second to UDP users [udpInDatagrams]"""},
    'odgm6/s':  {'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The total number of UDP datagrams sent per second
                 from this entity [udpOutDatagrams]."""},
    'noport6/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The total number of received UDP datagrams per
                 second for which there was no application at the destination
                 port [udpNoPorts]"""},
    'idgmer6/s':{'cat': 'Network',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """The number of received UDP datagrams per second
                 that could not be delivered for reasons other than the lack of
                 an application at the destination port [udpInErrors]"""},
    'intr/s':   {'cat': 'Interrupts',
                 'regexp': _number_with_decimals_regexp,
                 'desc': """ """},
}

def get_regexp(name):
    k = {}
    k['IFACE'] = _interface_name_regexp
    k['DEV'] = _device_name_regexp
    k['CPU'] = _cpu_regexp
    k['INTR'] = _intr_regexp
    k['iNNN/s'] = _interrupts_regexp
    k['BUS'] = _integer_regexp
    k['FAN'] = _integer_regexp
    k['DEVICE'] = _interface_name_regexp
    k['TEMP'] = _integer_regexp
    k['TTY'] = _integer_regexp
    k['idvendor'] = _hex_regexp
    k['idprod'] = _hex_regexp
    k['manufact'] = _usb_name_regexp
    k['product'] = _usb_name_regexp
    k['MHz'] = _number_with_decimals_regexp
    k['FILESYSTEM'] = _fs_name_regexp
    if k.has_key(name):
        return k[name]

    if base_graphs.has_key(name) and base_graphs[name].has_key('regexp'):
        return base_graphs[name]['regexp']

    if re.match('i[0-9]*/s', name):
        return _interrupts_regexp

    raise Exception("regexp for %s could not be found" % name)

def get_labels_title(names):
    if not isinstance(names, list):
        raise Exception("get_labels_title expects a list: %s" % names)

    cat  = {}
    key  = {}
    perf = {}
    for i in names:
        try:
            (c, k, p) = i.split('#')
        except: # It is not in the "CPU#0#%idle" form
            # Contemplate a combined simple graph like ldavg-{1,5,15}
            if len(names) != 1:
                return (" ".join(names), names)

            if not base_graphs.has_key(names[0]):
                return (names[0], names[0])
            if base_graphs[names[0]].has_key('label'):
                s = base_graphs[names[0]]['label']
                return (s, s)
            else:
                return (names[0], names[0])
        cat[c] = True
        key[k] = True
        perf[p] = True

    if len(cat.keys()) > 1:
        raise Exception("Error. We do not contemplate graphing data from different categories: %s" % names)

    #   ['CPU#0#%idle', 'CPU#1#%idle', 'CPU#3#%idle', ...]
    #    title = '%idle'
    #    labels = ['CPU0', 'CPU1', 'CPU2', ...]
    if len(perf.keys()) == 1:
        c = cat.keys()[0]
        title = "%s" % (perf.keys()[0])
        labels = ["".join(i.split('#')[1:2]) for i in names]
        return (title, labels)

    raise Exception("get_labels_title() error on %s" % names)

def list_all_categories():
    l = set(['Load', 'Files', 'I/O', 'TTY', 'Network', 'Power', 'Intr'])
    for i in base_graphs.keys():
        cat = base_graphs[i]['cat']
        l.update([cat])
    return l

def get_category(name):
    if name.startswith('CPU#'):
        return 'Load'
    elif name.startswith('FILESYSTEM#'):
        return 'Files'
    elif name.startswith('DEV#'):
        return 'I/O'
    elif name.startswith('TTY'):
        return 'TTY'
    elif name.startswith('IFACE'):
        return 'Network'
    elif name.startswith('TEMP#'):
        return 'Power'
    elif name.startswith('FAN#'):
        return 'Power'
    elif name.startswith('INTR#'):
        return 'Intr'

    if base_graphs.has_key(name):
        return base_graphs[name]['cat']

    # Everything else aka 'i[0-9]*/s' we match to 'Interrups'
    # Not using a re here due to performance reason
    # Worse that can happen is that we get wrong categories on new
    # not-yet accounted for graph. Drop me a line in such cases
    return 'Interrupts'

def get_desc(names):
    if not isinstance(names, list):
        raise Exception("get_desc mandates a list: %s" % names)

    regex = re.compile('[\n ]+')
    if len(names) == 1:
        name = names[0]
        if base_graphs.has_key(name):
            s = base_graphs[name]['desc']
            return [[name, regex.sub(' ', s)]]

        try:
            (cat, key, perf) = name.split('#')
            s = base_graphs[perf]['desc']
            return [[perf, regex.sub(' ', s)]]
        except:
            pass
        if re.match('.*i[0-9]*/s', name):
            return [['int/s', 'Interrupts per second']]
    else:
        ret = []
        previous = None
        for i in names:
            try:
                (cat, key, perf) = i.split('#')
                if re.match('.*i[0-9]*/s', perf):
                    if previous != 'int/s':
                        ret.append(['int/s', 'Interrupts per second'])
                        previous = 'int/s'
                    continue

                s = base_graphs[perf]['desc']
                if previous != perf:
                    ret.append([perf, regex.sub(' ', s)])
                    previous = perf
            except:
                # It is a combination of simple graphs (like ldavg-{1,5,15})
                s = base_graphs[i]['desc']
                ret.append([i, regex.sub(' ', s)])

        return ret

    raise Exception("Unknown graph: %s" % names)

# vim: autoindent tabstop=4 expandtab smarttab shiftwidth=4 softtabstop=4 tw=0
