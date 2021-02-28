import logging
import sys
import time
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from http.client import RemoteDisconnected
from trader import Trader
from coin_data import CoinData
from signals import Signals


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - [ %(levelname)s ] - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class AlgoTrader:

    """Check each coin for signals and make trades in certain conditions.
    Conditions:
    - 15m RSI oversold and RSI divergence, and 1h ema_50/ema_200 trend"""

    data = CoinData()
    trader = Trader()
    scheduler = BackgroundScheduler()

    def __init__(self):
        self.signals_dict = {}
        self.trend_markers = {}
        self.get_signals()
        self.check_emas()
        self.event_loop = None
        self.recent_alerts = []
        self.trader = Trader()
        self.trader.settings['sl'] = 0.005
        self.trader.settings['tp'] = 0.02
        self.trader.settings['qty'] = 0.01

    async def get_signals(self):
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

    def long_condition(self, open_positions, recent_alerts):
        for symbol in self.signals_dict.keys():
            if self.trend_markers[symbol][1] and self.trend_markers[symbol][2]:
                if self.signals_dict[symbol][0].rsi_div_dict['confirmed bullish divergence']:
                    alert = f'LONG {symbol} at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
                    if symbol not in open_positions and symbol not in recent_alerts:
                        self.trader.trade(symbol, True)
                        with open('buys.txt', 'a') as f:
                            f.write(alert + '\n')
                        self.recent_alerts.append(alert)
                        logger.info(alert)

    def short_condition(self, open_positions, recent_alerts):
        for symbol in self.signals_dict.keys():
            if not self.trend_markers[symbol][1] and not self.trend_markers[symbol][2]:
                if self.signals_dict[symbol][0].rsi_div_dict['confirmed bearish divergence']:
                    alert = f'SHORT {symbol} at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
                    if symbol not in open_positions and symbol not in recent_alerts:
                        self.trader.trade(symbol, False)
                        with open('buys.txt', 'a') as f:
                            f.write(alert)
                        self.recent_alerts.append(alert)
                        logger.info(alert)

    def purge_alerts(self):
        old_alerts = []
        for alert in self.recent_alerts:
            split_alert = alert.split(' ')
            if datetime.strptime(split_alert[3], '%Y-%m-%d %H:%M:%S') < datetime.now() - timedelta(minutes=45):
                old_alerts.append(alert)
        for alert in old_alerts:
            self.recent_alerts.remove(alert)

    def check_conditions(self):
        try:
            logger.debug('checking signals')
            start_time = datetime.now()
            self.get_signals()
            self.check_emas()
            self.purge_alerts()
            recent_alerts_symbols = [alert.split(' ')[1] for alert in self.recent_alerts]
            open_positions = [position['symbol'] for position in self.trader.return_open_positions()]
            log_statement = 'took: %s'.format(datetime.now() - start_time)
            logger.debug(log_statement)
            logger.debug('checking long')
            self.long_condition(open_positions, recent_alerts_symbols)
            logger.debug('checking short')
            self.short_condition(open_positions, recent_alerts_symbols)
            self.trader.check_positions_cancel_open_orders()
            logger.debug('done')
            if self.recent_alerts:
                recent = ', '.join(self.recent_alerts)
                logger.debug(recent)
            total_time = datetime.now() - start_time
            log_statement = 'total_time: %s'.format(total_time)
            logger.debug(log_statement)
        except Exception as e:
            log_statement = f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}: {e}'
            logger.warning(log_statement)


    # def start_async(self):
    #     self.event_loop.run_until_complete(self.check_conditions())

    def save_data(self):
        self.data.save_latest_data()

    def schedule_tasks(self):
        self.scheduler.add_job(self.save_data, trigger='cron', minute='*/1', second="58")
        self.scheduler.add_job(self.check_conditions, trigger='cron', minute='*/1')
        self.scheduler.start()

    def stop_tasks(self):
        self.scheduler.remove_all_jobs()
        self.scheduler.shutdown()

    def loop(self):
        try:
            # self.event_loop = asyncio.get_event_loop()
            self.schedule_tasks()
            while True:
                time.sleep(1)
        except KeyboardInterrupt as e:
            self.stop_tasks()
            # self.event_loop.close()
            raise e


if __name__ == '__main__':
    at = AlgoTrader()
    at.loop()
