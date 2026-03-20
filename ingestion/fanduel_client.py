"""Backward-compat shim - real code is in ingestion.common.fanduel_client."""
from importlib import import_module as _import_module
import sys as _sys

_sys.modules[__name__] = _import_module("ingestion.common.fanduel_client")
