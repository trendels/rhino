Rhino
=====

|docs|

Rhino is a python microframework for building RESTful web services.

Minimal "Hello World" example:

.. code-block:: python

    from rhino import Mapper, get

    @get
    def hello(request):
        return "Hello, world!"

    app = Mapper()
    app.add('/', hello)
    app.start_server()

Features
--------

- Build reusable, nested applications
- Resource-centric design
- Support for content negotiation

Documentation
-------------

Read the `documentation at readthedocs. <http://rhino.readthedocs.org/>`_.

.. |docs| image:: https://readthedocs.org/projects/rhino/badge/?version=latest
   :target: https://readthedocs.org/projects/rhino/?badge=latest
   :alt: Documentation Status
   :scale: 100%
