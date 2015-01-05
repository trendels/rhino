from __future__ import absolute_import

import httplib
import re
import time
from calendar import timegm
from collections import namedtuple
from datetime import datetime, timedelta
from email.utils import parsedate
from wsgiref.handlers import format_date_time

__all__ = [
    'cache_control',
]

# The "unrolled" version is faster by about a factor of 2.
#_quoted_string = r'"(?:[^"\\]|\\.)*"'
_quoted_string = r'"[^"\\]*(?:\\.[^\\"]*)*"'
_etag_weak_prefix = r'[Ww]/'
_etag_star = r'\*'
_etag = r'(%s)?(%s)' % (_etag_weak_prefix, _quoted_string)
_etag_header = r'^(?:(%s)|(?:%s(?:\s*,\s*|$))+)$' % (_etag_star, _etag)

etag_re = re.compile(_etag)
etag_header_re = re.compile(_etag_header)
quoted_string_re = re.compile(_quoted_string)

status_codes = httplib.responses.copy()


def parse_etag_header(header):
    """Parse a header containing one or more ETags or a wildcard ('*').

    Returns the string '*' or a list of ETags as (weak, etag) tuples.
    `weak` is the prefix designating a weak ETag, or the empty string.
    `etag` is the ETag (including quotes) with the weak prefix stripped
    off. Returns an empty list if the header could not be parsed.

    Example:

    >>> parse_etag_header('*')
    '*'
    >>> parse_etag_header('"foo"  ')
    [('', '"foo"')]
    >>> parse_etag_header('"foo", w/"bar", W/"baz"')
    [('', '"foo"'), ('w/', '"bar"'), ('W/', '"baz"')]
    >>> parse_etag_header('invalid')
    []

    """
    m = etag_header_re.match(header.strip())
    if not m:
        return []
    if m.group(1):  # star
        return m.group(1)
    else:  # list of entity tags
        return etag_re.findall(header)


def match_etag(etag, header, weak=False):
    """Try to match an ETag against a header value.

    If `weak` is True, uses the weak comparison function.
    """
    if etag is None:
        return False
    m = etag_re.match(etag)
    if not m:
        raise ValueError("Not a well-formed ETag: '%s'" % etag)
    (is_weak, etag) = m.groups()
    parsed_header = parse_etag_header(header)
    if parsed_header == '*':
        return True
    if is_weak and not weak:
        return False
    if weak:
        return etag in [t[1] for t in parsed_header]
    else:
        return etag in [t[1] for t in parsed_header if not t[0]]


def datetime_to_timestamp(dt):
    """Convert datetime.datetime to Unix timestamp."""
    return timegm(dt.utctimetuple())


def httpdate_to_timestamp(s):
    """Convert HTTP date to Unix timestamp."""
    return timegm(parsedate(s))


def total_seconds(td):
    if hasattr(td, 'total_seconds'):  # Since Python 2.7
        return td.total_seconds()
    else:  # pragma: no cover
        return td.seconds + 60*60*24 * td.days + td.microseconds/1000000.0


def datetime_to_httpdate(dt):
    """Convert datetime.datetime or Unix timestamp to HTTP date."""
    if isinstance(dt, (int, float)):
        return format_date_time(dt)
    elif isinstance(dt, datetime):
        return format_date_time(datetime_to_timestamp(dt))
    else:
        raise TypeError("expected datetime.datetime or timestamp (int/float),"
                        " got '%s'" % dt)


def timedelta_to_httpdate(td):
    """Convert datetime.timedelta or number of seconds to HTTP date.

    Returns an HTTP date in the future.
    """
    if isinstance(td, (int, float)):
        return format_date_time(time.time() + td)
    elif isinstance(td, timedelta):
        return format_date_time(time.time() + total_seconds(td))
    else:
        raise TypeError("expected datetime.timedelta or number of seconds"
                        "(int/float), got '%s'" % td)


def cache_control(max_age=None, private=False, public=False, s_maxage=None,
        must_revalidate=False, proxy_revalidate=False, no_cache=False,
        no_store=False):
    """Generate the value for a Cache-Control header.

    Example:

        >>> from rhino.http import cache_control as cc
        >>> from datetime import timedelta
        >>> cc(public=1, max_age=3600)
        'public, max-age=3600'
        >>> cc(public=1, max_age=timedelta(hours=1))
        'public, max-age=3600'
        >>> cc(private=True, no_cache=True, no_store=True)
        'private, no-cache, no-store'

    """
    if all([private, public]):
        raise ValueError("'private' and 'public' are mutually exclusive")
    if isinstance(max_age, timedelta):
        max_age = int(total_seconds(max_age))
    if isinstance(s_maxage, timedelta):
        s_maxage = int(total_seconds(s_maxage))
    directives = []
    if public: directives.append('public')
    if private: directives.append('private')
    if max_age is not None: directives.append('max-age=%d' % max_age)
    if s_maxage is not None: directives.append('s-maxage=%d' % s_maxage)
    if no_cache: directives.append('no-cache')
    if no_store: directives.append('no-store')
    if must_revalidate: directives.append('must-revalidate')
    if proxy_revalidate: directives.append('proxy-revalidate')
    return ', '.join(directives)
