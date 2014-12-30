Rhino
=====

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

