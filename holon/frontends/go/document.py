"""Readers of the Go frontend's document format (holon-facts/0.3, `go` section; holon.frontends.go.analyses writes it).

The Go document's codec entries carry their byte layout under a key the frontend owns. Generic consumers of the
document (the linked codec layer, holon.diagram.linked) read it through this module, so the format stays defined in
one place: the frontend that writes it.
"""
from __future__ import annotations

# the key under which go.codecs.encoders entries hold their output bytes, one term per byte (analyses.py)
ENCODER_LAYOUT_KEY = "cells"


def encoder_layout(entry: dict) -> list:
    """The byte terms of a go.codecs.encoders entry, in output order: ["const", v] or ["byte", <term>, k]."""
    return list(entry[ENCODER_LAYOUT_KEY])
