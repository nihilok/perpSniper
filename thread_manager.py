import os
import time
from threading import Thread

from coin_data import CoinData
from signals_loop import MainLoop, scheduler
from trader import Trader


class ThreadManager:

    def __init__(self):

        """Construct all required instances and start threads"""

        self.trader = Trader()
        self.data = CoinData()
        self.signals = MainLoop(self.data)
        self.threads = []

        self.start_thread(self.jobs)
        print('Signals background tasks added')
        self.start_thread(self.save_data_thread)
        print('Data thread running')

    def save_data_thread(self):
        try:
            while True:
                time.sleep(2)
                self.data.save_latest_data()
        except KeyboardInterrupt as e:
            self.teardown()
            os.remove('symbols.db')
            raise e

    def teardown(self):
        scheduler.remove_all_jobs()
        self.stop_threads()
        scheduler.shutdown()
        self.signals.teardown()
        self.data.bsm_tear_down()

    def jobs(self):
        jobs = [(self.trader.check_positions_cancel_open_orders, 'interval', 60)]
        self.signals.start_jobs(jobs=jobs)

    def start_thread(self, func):
        t = Thread(target=func)
        t.setDaemon(True)
        t.start()
        self.threads.append(t)

    def stop_threads(self):
        self.data.bsm_tear_down()
        for thread in self.threads:
            thread.join()
        print('Threads stopped')