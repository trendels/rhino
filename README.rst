Rhino
=====

|build-status-img|

Rhino is a python microframework for building RESTful web services.

Installation
------------

From pypi:

::

    $ pip install rhino

From a git checkout:

::

    $ git clone https://github.com/trendels/rhino.git
    $ cd rhino
    $ python setup.py install

To run the test suite, clone the repository as shown above, and run:

::

    $ pip install -r requirements.txt
    $ make test

Minimal "Hello World" example
-----------------------------

.. code:: python

    from rhino import Mapper, get

    @get
    def hello(request):
        return "Hello, world!"

    app = Mapper()
    app.add('/', hello)
    app.start_server()

Documentation
-------------

The online documentation can be found at
https://trendels.github.io/rhino/

Bugs
----

Please report bugs using the `github issue
tracker <https://github.com/trendels/rhino/issues>`__.

License
-------

Rhino is licensed unter the MIT License. See the included file
``LICENSE`` for details.

.. |build-status-img| image:: https://travis-ci.org/trendels/rhino.svg
   :target: https://travis-ci.org/trendels/rhino
