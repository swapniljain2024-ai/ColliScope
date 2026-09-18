"""
Phase 0 Python Toolchain Scaffolding Verification Test.
Verifies that pytest runs and the Python environment operates as expected.
"""

def test_python_toolchain_scaffolding():
    project_name = "ColliScope"
    assert project_name == "ColliScope"
    assert 2 + 2 == 4

def test_environment_sanity():
    import sys
    assert sys.version_info >= (3, 10), "ColliScope requires Python 3.10+"
