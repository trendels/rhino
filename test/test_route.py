from rhino.mapper import Route, InvalidArgumentError
from pytest import raises as assert_raises

def test_default():
    assert Route('/', None)

def test_invalid_route_name():
    assert_raises(InvalidArgumentError, Route, '/', None, name='.')
    assert_raises(InvalidArgumentError, Route, '/', None, name='/')

def test_invalid_param_name():
    assert_raises(InvalidArgumentError, Route, '/{ctx}', None)
    assert_raises(InvalidArgumentError, Route, '/{_query}', None)
    assert_raises(InvalidArgumentError, Route, '/{_relative}', None)
