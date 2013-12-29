sarstats
========

Creates a PDF report out of sar files

Written originally by Ray, I cleaned it up to make it more user-friendly, use
less memory and make it multi-processor capable.

demo
====
Here you can see how such a pdf looks like: http://acksyn.org/software/sarstats/sar19.pdf

Q&A
===

Q: Why don't you use 'sadf' instead of doing all that parsing?
A: sadf does not parse 'older' SA files. So no RHEL 5 and even RHEL 6 files cannot
   be parsed on a current (F20) Fedora box.

Q: I found a bug, where do I report it?
A: Drop me an email: michele@acksyn.org

Q: Shouldn't you move to PCP or something more capable anyway?
A: Yes, as soon as PCP is more widespread
