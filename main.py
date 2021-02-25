#!/usr/bin/env python3
import atexit
import multiprocessing

import gunicorn.app.base
from app import app, start_signals, tear_down
from trader import Trader


atexit.register(tear_down)


def number_of_workers():
    return multiprocessing.cpu_count()


class StandaloneApplication(gunicorn.app.base.BaseApplication):

    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self):
        config = {key: value for key, value in self.options.items()
                  if key in self.cfg.settings and value is not None}
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application


if __name__ == '__main__':
    tr_setup = Trader()
    del tr_setup
    options = {
        'bind': '%s:%s' % ('0.0.0.0', '8080'),
        'workers': number_of_workers(),
        'worker_class': 'gthread',
        'on_starting': start_signals(),
    }
    StandaloneApplication(app, options).run()
