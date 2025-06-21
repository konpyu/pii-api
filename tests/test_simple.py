"""Simple test to verify pytest setup."""


def test_simple_addition():
    """Test that basic arithmetic works."""
    assert 1 + 1 == 2


def test_simple_string():
    """Test that string operations work."""
    assert "hello" + " " + "world" == "hello world"


class TestSimpleClass:
    """Test class to verify class-based tests work."""

    def test_class_method(self):
        """Test method in a test class."""
        assert True

    def test_list_operations(self):
        """Test list operations."""
        test_list = [1, 2, 3]
        test_list.append(4)
        assert len(test_list) == 4
        assert test_list[-1] == 4
