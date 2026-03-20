"""Backward-compat shim - real code is in api.schemas.nba.advanced_trends."""
from importlib import import_module as _import_module
import sys as _sys

_sys.modules[__name__] = _import_module("api.schemas.nba.advanced_trends")
