sarstats
========

Creates a PDF report out of sar files

Written originally by Ray, I cleaned it up to make it more user-friendly, use
less memory and make it multi-processor capable.

demo
====
Here you can see how such a pdf looks like: http://acksyn.org/software/sarstats/sar19.pdf
And a more complex example (~60MB): http://acksyn.org/software/sarstats/sar01.pdf

The following creates a report off 'sar01' and adds a graph with three datasets (udpsck,
rawsck,tcp-tw):
```
./sarstats --out sar01.pdf --custom 'foo:udpsck,rawsck,tcp-tw' /var/log/sa/sar01
```

To list the names of all the possible graphs just run:
```
./sarstats --list /var/log/sa/sar01
```

To export a single custom graph in svg format run:
```
./sarstats --output base --svg 'ldavg-1,ldavg-5,ldavg-15' \
  --label 'peak:2014-02-17 14:30:00' demo/var/log/sa/
```

This will produce the following output:
![svg_output](http://mbaldessari.github.io/sarstats/base1.svg)

It is also possible to print a single graph in ascii format:
```
./sarstats --ascii 'tcp/s' tests/sar-files/1/sar19

                           tcp/s - tests/sar-files/1/sar19

   0.01 +++A-+--+--A--+--+--A--+-+--+--+--+--A--+--+-+--+--+--+--+--+--A--+++
        |  * +     *     +  *  +    +     +  *  +    +     +   tcp/s **A*** |
        |  *       *        *                *                         *    |
        |  *       *        *                *                         *    |
  0.008 ++ *       *        *                *                         *   ++
        |  *       *        *                *                         *    |
        |  *       *        *                *                         *    |
  0.006 ++ *       *        *                *                         *   ++
        |  *       *        *                *                         *    |
        |  *       **       **               **                        **   |
        | **       **       **               **                        **   |
  0.004 ++**       **       **               **                        **  ++
        | **       **       **               **                        **   |
        | **       **       **               **                        **   |
  0.002 ++**       **       **               **                        **  ++
        | **       **       **               **                        **   |
        | **       **       **               **                        **   |
        | ** +     **    +  ** +    +     +  ** +    +     +     +     **   |
      0 AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
           02:00 04:00 06:00 08:0010:00 12:00 14:0016:00 18:00 20:00 22:00
                                        Time
```

Q&A
===
* Q: Why don't you use 'sadf' instead of doing all that parsing?
* A: sadf does not parse 'older' SA files. So no RHEL 5 and even RHEL 6 files cannot
   be parsed on a current (F20) Fedora box.

* Q: I found a bug, where do I report it?
* A: Drop me an email or open an issue in github

* Q: Shouldn't you move to PCP or something more capable anyway?
* A: Yes, as soon as PCP is more widespread

* Q: In network graphs with bonding the bond interface is never shown?
* A: Because, depending on the bonding mode, the underlying ethX interface has the exact same traffic patterns and is drawn afterwards

* Q: When using --maxgraphs 15 on a big sar file (one with many scsi devices for example) I get a traceback with IOError: Cannot open resource "...."
* A: You are hitting the file number limit due to the many images that are being opened. Increase the limit per user (https://rtcamp.com/tutorials/linux/increase-open-files-limit/)

Thanks
======
Luca Miccini, Pablo Iranzo Gomez, Ali Sogukpinar, Freddy Wissinger
