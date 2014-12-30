#!/usr/bin/env python
from setuptools import setup

version = '0.0.1'

with open('README.rst') as f:
    README = f.read()

setup(
    name='Rhino',
    version=version,
    author='Stanis Trendelenburg',
    author_email='stanis.trendelenburg@gmail.com',
    packages=['rhino'],
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
