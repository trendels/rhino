from __future__ import absolute_import

import mimetypes
import os
from hashlib import md5

from .errors import NotFound, MethodNotAllowed
from .response import ok


class StaticFile(object):
    """Resource for serving a static file."""

    block_size = 65536
    default_content_type = 'application/octet-stream'

    def __init__(self, path, content_type=None, expires=None):
        if not os.path.isfile(path):
            raise ValueError("No such file: %s" % path)
        if content_type is None:
            content_type = mimetypes.guess_type(path)[0] \
                    or self.default_content_type
        self.path = path
        self.content_type = content_type
        self.expires = expires

    def __call__(self, request):
        if request.method not in ('GET', 'HEAD'):
            raise MethodNotAllowed(allow='GET, HEAD')
        stat = os.stat(self.path)
        etag = md5('%d:%f:%d' % (
            stat.st_ino, stat.st_mtime, stat.st_size)).hexdigest()

        def body():
            with open(self.path) as f:
                while True:
                    chunk = f.read(self.block_size)
                    if chunk == '':
                        break
                    yield chunk

        return ok(
                body, content_length=str(stat.st_size),
                content_type=self.content_type,
                etag=etag, expires=self.expires)


class StaticDirectory(object):
    """Resource for serving static files from a directory.

    Must be mapped to a route including a template parameter named
    `path`. Example:

        from rhino import Mapper, StaticDirectory

        app = Mapper()
        app.add('/static/{path:any}', StaticDirectory('./static'))

    Setting the `path` parameter's range to `any`, which includes '/', enables
    serving files from subdirectories of './static'.
    """

    # TODO add support for index.html, directory listings?
    def __init__(self, root, expires=None):
        self.root = os.path.abspath(root)
        self.expires = expires

    def __call__(self, request):
        # Normalize path_info to always start with a slash.
        path_info = '/' + request.routing_args.get('path', '').lstrip('/')
        # Interpret path_info as an OS path, resolve any non-leading '..', and
        # require resulting path to be absolute.
        # This is to prevent enumeration of directory names: If 'foo.txt' is
        # a public file in self.root, and a request for '../bar/foo.txt'
        # succeeds, a client can learn that foo is in a directory named 'bar',
        # and continue like this until it knows the entire path of the file,
        # starting from '/'.
        request_path = os.path.normpath(path_info)
        if not os.path.isabs(request_path):
            raise NotFound
        # Concatenate with root path and do a prefix check to prevent path
        # traversal.
        prefix = os.path.abspath(self.root) + os.path.sep
        # Use concatenation here instead of os.path.join because request_path
        # is absolute.
        filepath = os.path.abspath(prefix + request_path)
        if os.path.commonprefix([prefix, filepath]) != prefix:
            raise NotFound
        try:
            return StaticFile(filepath, expires=self.expires)(request)
        except ValueError:
            raise NotFound
