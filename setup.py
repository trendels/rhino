#!/usr/bin/env python
import re
from setuptools import setup, find_packages

with open('rhino/__init__.py') as f:
    version = re.findall(r"^__version__ = '(.*)'", f.read(), re.M)[0]

with open('README.rst') as f:
    README = f.read()

setup(
    name='Rhino',
    version=version,
    author='Stanis Trendelenburg',
    author_email='stanis.trendelenburg@gmail.com',
    packages=find_packages(exclude=['test*', 'example*']),
    url='https://github.com/trendels/rhino',
    license='MIT',
    description='A microframework for building RESTful web services',
    long_description=README,
    classifiers = [
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
    ],
)
