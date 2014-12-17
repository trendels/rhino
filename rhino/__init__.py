from __future__ import absolute_import

from .mapper import Mapper
from .resource import Resource, get, post, put, delete, patch, options
from .request import Request
from .response import Response, Entity, ok, redirect
from .static import StaticFile, StaticDirectory

__version__ = '0.0.1'
