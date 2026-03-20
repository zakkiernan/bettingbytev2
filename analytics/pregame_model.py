"""Backward-compat shim - real code is in analytics.nba.pregame_model."""
from importlib import import_module as _import_module
import sys as _sys

_sys.modules[__name__] = _import_module("analytics.nba.pregame_model")
