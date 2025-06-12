"""Data ingestion sub-package.

This directory originally lacked an ``__init__.py`` file which meant that
imports such as ``import data_injestion.models`` failed at runtime because
Python did not recognise *data_injestion* as a package. Adding this marker
file turns the directory into a proper package so that absolute imports used
throughout the codebase (e.g. in ``prepdocs.py``) succeed once the project’s
root (or the ``src`` directory) is on ``sys.path``.

The file is intentionally empty – no execution is required at import time –
but we keep the docstring above to document the purpose of the file and the
misspelling in the package name, which we preserve to avoid creating further
breaking changes.
"""
