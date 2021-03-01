import time
from datetime import datetime
from threading import Thread

from coin_data import CoinData
from trader import Trader, PerpetualTrade

from signals import Signals
from utils import get_popular_coins


class HeikenAshiPerpetualTrader:

    def __init__(self, symbol):
        self.tf = '1m'
        self.tr = Trader()
        self.tr.settings['qty'] = 0.005
        self.tr.settings['sl'] = 0.05
        self.tr.check_positions_cancel_open_orders()
        quantity, approx_price, info = self.tr.calculate_max_qty(symbol)
        HA_trend = Signals.get_heiken_ashi_trend(Signals.get_heiken_ashi(CoinData.get_dataframe(symbol, self.tf)))
        self.pt = PerpetualTrade(symbol, HA_trend, quantity,
                            self.tr.settings['tp'], self.tr.settings['sl'],
                            self.tr.settings['db'], info, self.tr)
        print(f'INITIAL TRADE: Going {"LONG" if HA_trend is True else "SHORT" if HA_trend is False else "FLAT"} on {symbol}')

    def subsequent_trades(self, symbol):
        HA_trend = Signals.get_heiken_ashi_trend(Signals.get_heiken_ashi(CoinData.get_dataframe(symbol, self.tf)))
        # print(symbol, HA_trend)
        try:
            open_positions = [(position['symbol'], position['direction']) for position in
                              self.tr.return_open_positions()]
            if symbol in {op[0] for op in open_positions}:
                log = ''
                if HA_trend is True:
                    if (symbol, 'SHORT') in open_positions:
                        log = f'Going {"LONG" if HA_trend is True else "SHORT" if HA_trend is False else "FLAT"} on {symbol}'
                        self.pt.long()
                    else:
                        pass
                elif HA_trend is False:
                    if (symbol, 'LONG') in open_positions:
                        log = f'Going {"LONG" if HA_trend is True else "SHORT" if HA_trend is False else "FLAT"} on {symbol}'
                        self.pt.short()
                else:
                    log = f'Going {"LONG" if HA_trend is True else "SHORT" if HA_trend is False else "FLAT"} on {symbol}'
                    self.pt.flat()
                if log:
                    print(log)
            else:
                quantity, approx_price, info = self.tr.calculate_max_qty(symbol)
                if HA_trend is not None:
                    log = f'REOPENED: Going {"LONG" if HA_trend is True else "SHORT" if HA_trend is False else "FLAT"} on {symbol}'
                    self.pt = PerpetualTrade(symbol, HA_trend, quantity,
                                             self.tr.settings['tp'], self.tr.settings['sl'],
                                             self.tr.settings['db'], info, self.tr)
                    print(log)
        except Exception as e:
            print(e)


def mainloop(coin_data_instance):
    ha_trades = {}
    current_symbols = coin_data_instance.most_volatile_symbols
    for symbol, volatility in current_symbols:
        ha_trades[symbol] = HeikenAshiPerpetualTrader(symbol)
    while True:
        for symbol, volatility in current_symbols:
            ha_trades[symbol].subsequent_trades(symbol)
        now = datetime.now()
        if now.minute == 59 and 0 < now.second <= 1:
            print('reassessing most volatile coins')
            coin_data_instance.most_volatile_symbols = coin_data_instance.return_most_volatile()
            for symbol in ha_trades.keys():
                if symbol not in coin_data_instance.most_volatile_symbols:
                    ha_trades[symbol].tr.close_position(symbol)


def save_data(coin_data_instance):
    while True:
        coin_data_instance.save_latest_data()
        time.sleep(5)


if __name__ == '__main__':
    c = CoinData()
    t = Thread(target=save_data, args=(c,))
    t.setDaemon(True)
    t.start()
    time.sleep(10)
    mainloop(c)