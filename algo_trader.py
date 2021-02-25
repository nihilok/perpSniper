import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from trader import Trader, Trade
from coin_data import CoinData
from signals import Signals


class AlgoTrader:

    """Check each coin for signals and make trades in certain conditions.
    Conditions:
    - 15m RSI overbought and 4h ema_50 above ema_200"""

    data = CoinData()
    trader = Trader()

    def __init__(self):
        self.signals_dict = {}
        self.trend_markers = {}
        self.get_signals()

    def get_signals(self):
        for symbol in self.data.symbols:
            self.signals_dict[symbol] = (Signals(symbol, '1m'),
                                         Signals(symbol, '15m'),
                                         Signals(symbol, '1h'),
                                         Signals(symbol, '4h'))
            self.trend_markers[symbol] = None
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
        for symbol in self.data.symbols:
            if self.trend_markers[symbol][3] and self.trend_markers[symbol][2]:
                if self.signals_dict[symbol][1].rsi_ob_os_dict['oversold'] or self.signals_dict[symbol][1].rsi_div_dict['confirmed bullish divergence']:
                    print('BUY ' + symbol)

    def schedule_task(self):
        scheduler = BlockingScheduler()
        scheduler.add_job(self.long_condition_rsi_ema, trigger='cron', minutes='1,14,16,29,31,44,46,59')
        scheduler.start()


if __name__ == '__main__':
    at = AlgoTrader()
    at.schedule_task()