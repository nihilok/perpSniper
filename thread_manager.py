from threading import Thread

from coinData import CoinData
from signals_loop import MainLoop, scheduler
from trader import Trader


class ThreadManager:

    def __init__(self):
        try:
            self.trader = Trader()
            self.data = CoinData()
            self.signals = MainLoop(self.data)
            self.threads = []
            self.start_thread(self.data.websocket_loop)
            print('Live data web socket started')
            self.start_thread(self.jobs)
            print('Signals background tasks added')
        except KeyboardInterrupt:
            self.teardown()

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
        # t.setDaemon(True)
        t.start()
        self.threads.append(t)

    def stop_threads(self):
        for thread in self.threads:
            thread.join()

