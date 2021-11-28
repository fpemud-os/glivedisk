#!/usr/bin/env python3

class export_iso(exporter):
    "exporting to ISO image"

    def __init__(self):
        super().__init__(self)

    def run(self):
        pass


def register():
    "Inform main catalyst program of the contents of this plugin."
    return ({
        "iso": export_iso,
    })
