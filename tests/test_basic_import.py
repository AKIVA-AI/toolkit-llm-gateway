"""
Basic test to verify LiteLLM import works
"""

import importlib.metadata

import pytest


def test_litellm_import():
    """Test that litellm can be imported"""
    try:
        import litellm

        assert hasattr(litellm, "completion")
        if not hasattr(litellm, "__version__"):
            litellm.__version__ = importlib.metadata.version("litellm")
    except ImportError as e:
        pytest.fail(f"Failed to import litellm: {e}")


def test_litellm_version():
    """Test that litellm version is accessible"""
    import litellm

    version = getattr(litellm, "__version__", None)
    if version is None:
        version = importlib.metadata.version("litellm")
    assert version is not None
    assert isinstance(version, str)


def test_completion_function_exists():
    """Test that completion function exists"""
    from litellm import completion

    assert callable(completion)
