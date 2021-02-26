import logging
from datetime import datetime
from threading import Thread

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler

from trader import Trader, Trade
from coin_data import CoinData
from signals import Signals


class AlgoTrader:

    """Check each coin for signals and make trades in certain conditions.
    Conditions:
    - 15m RSI oversold and 4h ema_50 above ema_200"""

    data = CoinData()
    trader = Trader()

    def __init__(self):
        self.signals_dict = {}
        self.trend_markers = {}
        print(', '.join(self.data.symbols))
        self.get_signals()
        self.check_emas()
        self.data_thread = Thread(target=self.data.websocket_loop)

    def get_signals(self):
        inadequate_symbols = []
        for symbol in self.data.symbols:
            try:
                self.signals_dict[symbol] = (Signals(symbol, '1m'),
                                             Signals(symbol, '15m'),
                                             Signals(symbol, '1h'),
                                             Signals(symbol, '4h'))
            except IndexError:
                inadequate_symbols.append(symbol)
                continue
        for symbol in inadequate_symbols:
            self.data.symbols.remove(symbol)
        return self.signals_dict

    def check_emas(self):
        for symbol in self.data.symbols:
            signals_1m = self.signals_dict[symbol][0]
            signals_15m = self.signals_dict[symbol][1]
            signals_1h = self.signals_dict[symbol][2]
            signals_4h = self.signals_dict[symbol][3]
            h4 = True if signals_4h.df.ema_50.iloc[-1] > signals_4h.df.ema_200.iloc[-1] else False
            h1 = True if signals_1h.df.ema_50.iloc[-1] > signals_1h.df.ema_200.iloc[-1] else False
            m15 = True if signals_15m.df.ema_50.iloc[-1] > signals_15m.df.ema_200.iloc[-1] else False
            m1 = True if signals_1m.df.ema_50.iloc[-1] > signals_1m.df.ema_200.iloc[-1] else False
            self.trend_markers[symbol] = (m1, m15, h1, h4)
        return self.trend_markers

    def long_condition_rsi_ema(self):
        self.get_signals()
        self.check_emas()
        for symbol in self.signals_dict.keys():
            if self.trend_markers[symbol][3] and self.trend_markers[symbol][2]:
                if self.signals_dict[symbol][1].rsi_ob_os_dict['oversold']:
                    with open('buys.txt', 'a') as f:
                        f.write(f'BUY {symbol} at {datetime.now().strftime("%H:%M:%S")}')

    def schedule_tasks(self):
        self.data_thread.setDaemon(True)
        self.data_thread.start()
        scheduler = BackgroundScheduler()
        scheduler.add_job(self.data.save_new_data, trigger="cron", minute='0,13,15,28,30,43,45,58', second=57)
        scheduler.add_job(self.long_condition_rsi_ema, trigger='cron', minute='1,14,16,29,31,44,46,59')
        scheduler.start()


if __name__ == '__main__':
    at = AlgoTrader()
    at.long_condition_rsi_ema()
    at.schedule_tasks()