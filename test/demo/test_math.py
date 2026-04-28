
import pytest

from test.demo.math_func import add, div


def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0


def test_div_error():
    with pytest.raises(ZeroDivisionError):
        div(10, 0)
