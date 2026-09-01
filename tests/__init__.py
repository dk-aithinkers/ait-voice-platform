"""Test package.

An ``__init__.py`` so mypy names these modules ``tests.test_x`` rather than
``test_x``. Its per-module overrides must be fully-qualified with wildcards on
whole components, so ``tests.*`` only matches if this file exists.
"""
