#!/usr/bin/env python3

class export_iso(exporter):
    "exporting to ISO image"

    def __init__(self):
        super().__init__(self)

    def run(self):
        # Create the ISO
        if "iso" in self.settings:
            cmd([self.settings['controller_file'], 'iso', self.settings['iso']], env=self.env)
            self.gen_contents_file(self.settings["iso"])
            self.gen_digest_file(self.settings["iso"])
            self.resume.enable("create_iso")
        else:
            log.warning('livecd/iso was not defined.  An ISO Image will not be created.')


def register():
    "Inform main catalyst program of the contents of this plugin."
    return ({
        "iso": export_iso,
    })
