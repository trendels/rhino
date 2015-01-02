Rhino
=====

|build-status| |docs|

Rhino is a python microframework for building RESTful web services.

Installation
------------

From pypi::

   $ pip install rhino

From a github checkout::

   $ git clone https://github.com/trendels/rhino.git
   $ cd rhino
   $ python setup.py install

To run the test suite, clone the repository as shown above, and run::

   $ pip install -r requirements.txt
   $ make test


Minimal "Hello World" example
-----------------------------

.. code-block:: python

    from rhino import Mapper, get

    @get
    def hello(request):
        return "Hello, world!"

    app = Mapper()
    app.add('/', hello)
    app.start_server()

Documentation
-------------

Read the `documentation at readthedocs. <http://rhino.readthedocs.org/>`_.

.. |build-status| image:: https://travis-ci.org/trendels/rhino.svg?branch=github
   :target: https://travis-ci.org/trendels/rhino
   :alt: Build Status
   :scale: 100%

.. |docs| image:: https://readthedocs.org/projects/rhino/badge/?version=latest
   :target: https://readthedocs.org/projects/rhino/?badge=latest
   :alt: Documentation Status
   :scale: 100%
