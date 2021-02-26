import logging
import asyncio
import time
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
        self.get_signals()
        self.check_emas()
        self.event_loop = None

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

    async def long_condition(self):
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
        return True

    async def short_condition(self):
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
        return True

    async def check_conditions(self):
        l = self.event_loop.create_task(self.long_condition())
        s = self.event_loop.create_task(self.short_condition())
        await asyncio.wait([l,s])

    def start_async(self):
        try:
            self.event_loop = asyncio.get_event_loop()
            self.event_loop.run_until_complete(self.check_conditions())
        except Exception as e:
            pass
        finally:
            self.event_loop.close()

    def save_data(self):
        self.data.save_latest_data()
        print('latest data saved')

    def schedule_tasks(self):
        self.scheduler.add_job(self.save_data, trigger='cron', minute='*/1', second="58")
        # self.scheduler.add_job(self.start_async, trigger='cron', minute='*/1')
        self.scheduler.start()

    def stop_tasks(self):
        self.scheduler.remove_all_jobs()
        self.scheduler.shutdown()

    def loop(self):
        try:
            self.schedule_tasks()
            while True:
                self.start_async()
                time.sleep(60)
        except KeyboardInterrupt as e:
            self.stop_tasks()
            raise e


if __name__ == '__main__':
    at = AlgoTrader()
    at.loop()