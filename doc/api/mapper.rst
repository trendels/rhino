The Mapper
==========

.. module:: rhino

The mapper dispatches incoming requests based on URL templates and also
provides a WSGI interface.

The HTTP request's path is matched against a series of patterns in the order
they were added. Patterns may be given as strings that must match the request
path exactly, or they may be templates.

Groups of matching characters for templates are extracted from the URI and
accessible via the `request.routing_args` accessor.

A template is a string that can contain thee special kinds of markup:

``{name}`` or ``{name:range}``

   Whatever matches this part of the path will be available in the
   `request.routing_args` dict of named parameters.

``[]``

   Any part enclosed in brackets is optional. Brackets can be nested and
   contain named parameters. If an optional part contains named parameters and
   is missing from the request URL, the parameter names contained therein will
   also be missing from `request.routing_args`.

``|``

   A vertical bar may only be present at the end of the template, and causes
   the path to be matched only against the part before the ``'|'``. The path
   can contain more characters after the match, which will be preserved in
   `request.path_info`.

A named parameter can contain an optional named range specifier after a ``:``.
which restricts what characters the parameter can match. If no range is
specified a parameter matches ``segment``. The default ranges are as follows:

+---------------+------------------------+
|Range Name     |Regular Expression      |
+===============+========================+
|``word``       |``\w+``                 |
+---------------+------------------------+
|``alpha``      |``[a-zA-Z]+``           |
+---------------+------------------------+
|``digits``     |``\d+``                 |
+---------------+------------------------+
|``alnum``      |``[a-zA-Z0-9]+``        |
+---------------+------------------------+
|``segment``    |``[^/]+``               |
+---------------+------------------------+
|``unreserved`` |``[a-zA-Z\d\-\.\_\~]+`` |
+---------------+------------------------+
|``any``        |``.+``                  |
+---------------+------------------------+

The default ranges can be extended or overwritten by passing a dict mapping
range names to regular expressions to the Mapper constructor. The regular
expressions should be strings::

   # match numbers in engineering format
   mapper = Mapper(ranges={'real': r'(\+|-)?[1-9]\.[0-9]*E(\+|-)?[0-9]+'})
   mapper.add('/a/b/{n:real}', my_math_app)

The ``|`` is needed when nesting mappers::

   foo_mapper = Mapper()
   foo_mapper.add('/bar', bar_resource)

   mapper = Mapper()
   mapper.add('/', index)
   mapper.add('/foo|', foo_mapper)

A request to ``/foo/bar`` is now dispatched by ``mapper`` to ``foo_mapper`` and
on to ``bar_resource``.

.. autoclass:: Mapper
   :members:
