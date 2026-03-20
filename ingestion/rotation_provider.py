"""Backward-compat shim - real code is in ingestion.nba.rotation_provider."""
from importlib import import_module as _import_module
import sys as _sys

_sys.modules[__name__] = _import_module("ingestion.nba.rotation_provider")
