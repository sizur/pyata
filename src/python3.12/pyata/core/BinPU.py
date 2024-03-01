#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from __future__ import annotations
from typing import Any

import numpy as np, rich, rich.repr, rich.pretty

from .Relations import FactsTable


class UInt4Diff(FactsTable[
    np.dtype[np.uint8], Any, Any, Any, Any]
):
    name = "UInt4Diff/4"