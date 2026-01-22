# sos_utils.py - Shared utility functions for sarstats
# Copyright (C) 2012  Ray Dassen
#               2013  Ray Dassen, Michele Baldessari
#               2014  Michele Baldessari
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

"""Shared utility functions for sarstats."""

import re
from typing import Any


_NATURAL_SORT_RE = re.compile(r"([0-9]+)")


def natural_sort_key(s: str) -> list[Any]:
    """Natural sorting function.

    Given a string, it returns a list of strings and numbers for natural sorting.

    Example:
        natural_sort_key("michele0123") returns ['michele', 123, '']

    Args:
        s: The string to generate a sort key for.

    Returns:
        A list of strings and integers for natural sorting comparison.
    """
    return [
        int(text) if text.isdigit() else text.lower()
        for text in re.split(_NATURAL_SORT_RE, s)
    ]


# vim: autoindent tabstop=4 expandtab smarttab shiftwidth=4 softtabstop=4 tw=0
