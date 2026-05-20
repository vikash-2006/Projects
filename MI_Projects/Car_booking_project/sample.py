# 🧪 1. Writing a Basic Test

# This is the foundation. A test checks if your function works correctly.

def add(a, b):
    return a + b

def test_add():
    assert add(2, 3) == 5

# 👉 assert is the heart of pytest. If it's wrong, pytest shouts 😄




# ⚠️ 5. Exception Testing
# 🧪 Check if error is raised correctly

import pytest

def divide(a, b):
    return a / b

def test_divide_zero():
    with pytest.raises(ZeroDivisionError):
        divide(10, 0)

# 👉 Test passes only if error occurs




# 🔁 4. Parametrization (Multiple Inputs in One Test)
# 🧪 Run same test with different values

import pytest

@pytest.mark.parametrize("a,b,result", [
    (2, 3, 5),
    (4, 5, 9),
    (1, 1, 2)
])
def test_add_multiple(a, b, result):
    assert a + b == result

# 👉 One test, many cases 🚀



# ⏭️ 6. Skipping Test
# 🧪 Skip a test (not ready or not needed)

import pytest

@pytest.mark.skip(reason="Not implemented yet")
def test_skip_example():
    assert False

# 👉 This test will be skipped