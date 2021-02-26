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
    - 15m RSI oversold, macd crossing up and 4h&1h ema_50 above ema_200"""

    data = CoinData()
    trader = Trader()
    scheduler = BackgroundScheduler()

    def __init__(self):
        self.signals_dict = {}
        self.trend_markers = {}
        print(', '.join(self.data.symbols))
        self.get_signals()
        self.check_emas()

    def get_signals(self):
        inadequate_symbols = []
        for symbol in self.data.symbols:
            try:
                self.signals_dict[symbol] = (   # Signals(symbol, '1m'),
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
            # signals_1m = self.signals_dict[symbol][0]
            signals_15m = self.signals_dict[symbol][0]
            signals_1h = self.signals_dict[symbol][1]
            signals_4h = self.signals_dict[symbol][2]
            h4 = True if signals_4h.df.ema_50.iloc[-1] > signals_4h.df.ema_200.iloc[-1] else False
            h1 = True if signals_1h.df.ema_50.iloc[-1] > signals_1h.df.ema_200.iloc[-1] else False
            m15 = True if signals_15m.df.ema_50.iloc[-1] > signals_15m.df.ema_200.iloc[-1] else False
            # m1 = True if signals_1m.df.ema_50.iloc[-1] > signals_1m.df.ema_200.iloc[-1] else False
            self.trend_markers[symbol] = (m15, h1, h4)
        return self.trend_markers

    def long_condition(self):
        self.get_signals()
        self.check_emas()
        for symbol in self.signals_dict.keys():
            if self.trend_markers[symbol][1]:
                if self.signals_dict[symbol][0].rsi_ob_os_dict['oversold'] or self.signals_dict[symbol][0].rsi_div_dict['confirmed bullish divergence']:
                    alert = f'LONG {symbol} at {datetime.now().strftime("%H:%M:%S")}\n'
                    with open('buys.txt', 'a') as f:
                        f.write(alert)
                    print(alert)
        print('long_condition checked')

    def short_condition(self):
        self.get_signals()
        self.check_emas()
        for symbol in self.signals_dict.keys():
            if not self.trend_markers[symbol][1]:
                if self.signals_dict[symbol][0].rsi_ob_os_dict['overbought'] or self.signals_dict[symbol][0].rsi_div_dict['confirmed bearish divergence']:
                    alert = f'SHORT {symbol} at {datetime.now().strftime("%H:%M:%S")}\n'
                    with open('buys.txt', 'a') as f:
                        f.write(alert)
                    print(alert)
        print('short_condition checked')

    def schedule_tasks(self):
        self.scheduler.add_job(self.data.save_latest_data, trigger='cron', minute='*/1', second="58")
        self.scheduler.add_job(self.long_condition, trigger='cron', minute='*/1')
        self.scheduler.add_job(self.short_condition, trigger='cron', minute='*/1')
        self.scheduler.start()

    def stop_tasks(self):
        self.scheduler.remove_all_jobs()
        self.scheduler.shutdown()


if __name__ == '__main__':
    at = AlgoTrader()
    at.long_condition()
    at.short_condition()
    try:
        at.schedule_tasks()
    except KeyboardInterrupt as e:
        at.stop_tasks()
        raise e