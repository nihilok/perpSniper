import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timedelta

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from trader import Trader
from coin_data import CoinData
from signals import Signals

logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - [ %(levelname)s ] - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


# Telegram details
BOT_TOKEN = os.getenv('tg_debug_bot_token')
CHANNEL_ID = os.getenv('tg_debug_channel')


class AlgoTrader:

    """Check each coin for signals and make trades in certain conditions.
    Conditions:
    - 15m RSI oversold/overbought and RSI divergence, and 1h ema_50/ema_200 trend.
    - 15m RSI oversold/overbought in last hour and macd crossing up/down."""

    data = CoinData()
    trader = Trader()
    scheduler = BackgroundScheduler()

    def __init__(self):
        self.signals_dict = {}
        self.trend_markers = {}
        self.rsi_markers = {}
        self.event_loop = None
        self.recent_alerts = []
        self.ready_symbols = {
            'long': [],
            'short': []
        }
        self.trader = Trader()
        self.trader.settings['sl'] = 0.005
        self.trader.settings['tp'] = 0.01
        self.trader.settings['qty'] = 0.01
        self.trader.settings['db'] = 0.2

    @staticmethod
    async def create_signals_instance(symbol, tf):
        s = Signals(symbol, tf)
        return s

    async def get_signals(self):
        logger.debug('Getting signals')
        inadequate_symbols = []
        for symbol in self.data.symbols:
            try:
                m15 = asyncio.create_task(self.create_signals_instance(symbol, '15m'))
                h1 = asyncio.create_task(self.create_signals_instance(symbol, '1h'))
                h4 = asyncio.create_task(self.create_signals_instance(symbol, '4h'))
                self.signals_dict[symbol] = (await m15, await h1, await h4)
            except IndexError:
                inadequate_symbols.append(symbol)
                continue
        for symbol in inadequate_symbols:
            self.data.symbols.remove(symbol)
        return self.signals_dict

    def record_trend(self):
        for symbol in self.data.symbols:
            signals_15m = self.signals_dict[symbol][0]
            signals_1h = self.signals_dict[symbol][1]
            signals_4h = self.signals_dict[symbol][2]
            h4 = True if signals_4h.df.ema_50.iloc[-1] > signals_4h.df.ema_200.iloc[-1] else False
            h1 = True if signals_1h.df.ema_50.iloc[-1] > signals_1h.df.ema_200.iloc[-1] else False
            m15 = True if signals_15m.df.ema_50.iloc[-1] > signals_15m.df.ema_200.iloc[-1] else False
            self.trend_markers[symbol] = (m15, h1, h4)
        return self.trend_markers

    async def purge_alerts(self):
        logger.debug('Purging alerts')
        old_alerts = []
        for alert in self.recent_alerts:
            split_alert = alert.split(' ')
            if datetime.strptime(' '.join(split_alert[3:5]), '%Y-%m-%d %H:%M:%S') < datetime.now() - timedelta(minutes=45):
                old_alerts.append(alert)
        for alert in old_alerts:
            self.recent_alerts.remove(alert)

    def check_rsi_div(self, symbol):
        if self.signals_dict[symbol][0].rsi_div_dict['confirmed bearish divergence']:
            return False
        elif self.signals_dict[symbol][0].rsi_div_dict['confirmed bullish divergence']:
            return True
        else:
            return None

    def check_macd(self, symbol):
        if self.signals_dict[symbol][0].macd_dict['MACD cross'] is False or self.signals_dict[symbol][0].macd_dict['MACD 0 cross'] is False:
            return False
        elif self.signals_dict[symbol][0].macd_dict['MACD cross'] is True or self.signals_dict[symbol][0].macd_dict['MACD 0 cross'] is True:
            return True
        else:
            return None

    def check_rsi_ob_os(self, symbol):
        if self.signals_dict[symbol][0].rsi_ob_os_dict['overbought']:
            return False
        elif self.signals_dict[symbol][0].rsi_ob_os_dict['oversold']:
            return True
        else:
            return None

    def check_4h_trend(self, symbol):
        if self.trend_markers[symbol][2]:
            return True
        elif not self.trend_markers[symbol][2]:
            return False
        else:
            return None

    async def rsi_ob_os_marker(self):
        logger.debug('Checking RSI markers')
        for symbol in self.signals_dict.keys():
            if self.check_4h_trend(symbol) is True:
                if self.check_rsi_ob_os(symbol) is True:
                    self.rsi_markers[symbol] = (True, datetime.now())
            elif self.check_4h_trend(symbol) is False:
                if self.check_rsi_ob_os(symbol) is False:
                    self.rsi_markers[symbol] = (False, datetime.now())

    async def purge_rsi_markers(self):
        logger.debug('Purging RSI markers')
        old_keys = []
        for key, value in self.rsi_markers.items():
            if value[1] < datetime.now() - timedelta(hours=1):
                old_keys.append(key)
        if old_keys:
            for key in old_keys:
                self.rsi_markers.pop(key, None)

    async def rsi_div_trade(self, open_positions, recent_alerts):
        logger.debug('Checking RSI div')
        for symbol in self.signals_dict.keys():
            if open_positions is not None and symbol not in open_positions and symbol not in recent_alerts:
                if self.check_4h_trend(symbol) is True:
                    if self.check_rsi_div(symbol) is True:
                        self.ready_symbols['long'].append(symbol)
                        # self.trader.trade(symbol, True)
                        alert = f'LONG {symbol} at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} (RSI div signal)'
                        self.handle_alert(alert)
                elif self.check_4h_trend(symbol) is False:
                    if self.check_rsi_div(symbol) is False:
                        self.ready_symbols['short'].append(symbol)
                        # self.trader.trade(symbol, False)
                        alert = f'SHORT {symbol} at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} (RSI div signal)'
                        self.handle_alert(alert)

    async def rsi_macd_trade(self, open_positions, recent_alerts):
        logger.debug('Checking MACD')
        for symbol in self.signals_dict.keys():
            if symbol in self.rsi_markers.keys():
                if open_positions is not None and symbol not in open_positions and symbol not in recent_alerts:
                    if self.rsi_markers[symbol][0]:
                        if self.check_4h_trend(symbol) is True:
                            if self.check_macd(symbol) is True:
                                # self.trader.trade(symbol, True)
                                self.ready_symbols['long'].append(symbol)
                                alert = f'LONG {symbol} at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} (MACD signal)'
                                self.handle_alert(alert)
                    else:
                        if self.check_4h_trend(symbol) is False:
                            if self.check_macd(symbol) is False:
                                # self.trader.trade(symbol, False)
                                self.ready_symbols['short'].append(symbol)
                                alert = f'SHORT {symbol} at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} (MACD signal)'
                                self.handle_alert(alert)

    async def ha_long(self):
        for symbol in self.ready_symbols['long']:
            if Signals.get_heiken_ashi_trend(Signals.get_heiken_ashi(CoinData.get_dataframe(symbol, '1m'))[['HA_Open', 'HA_Close']]) is True:
                self.trader.trade(symbol, True)
                alert = f'LONGED {symbol} at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} HEIKEN ASHI FINAL SIGNAL'
                self.handle_alert(alert)
        self.ready_symbols['long'] = []

    async def ha_short(self):
        for symbol in self.ready_symbols['short']:
            if Signals.get_heiken_ashi_trend(Signals.get_heiken_ashi(CoinData.get_dataframe(symbol, '1m'))[['HA_Open', 'HA_Close']]) is False:
                self.trader.trade(symbol, False)
                alert = f'SHORTED {symbol} at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} HEIKEN ASHI FINAL SIGNAL'
                self.handle_alert(alert)
        self.ready_symbols['short'] = []

    async def check_heiken_ashi(self):
        logger.debug('Checking final condition (Heiken Ashi)')
        long_task = asyncio.create_task(self.ha_long())
        short_task = asyncio.create_task(self.ha_short())
        await long_task
        await short_task

    def handle_alert(self, alert):
        self.recent_alerts.append(alert)
        logger.info(alert)
        self.send_message(alert)

    def send_message(self, message):
        message = 'TRADING BOT ALERT: ' + message
        requests.get(f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage?chat_id={CHANNEL_ID}&text={message}')

    async def get_recent_alerts(self):
        return [alert.split(' ')[1] for alert in self.recent_alerts]

    async def get_open_positions(self):
        return self.trader.check_positions_cancel_open_orders()

    async def check_conditions(self):
        start_time = datetime.now()
        logger.debug('Starting check')
        # Get new signals data
        await self.get_signals()
        self.record_trend()
        task1 = asyncio.create_task(self.get_recent_alerts())
        task2 = asyncio.create_task(self.get_open_positions())
        recent_alerts_symbols = await task1
        open_positions = await task2

        log_statement = 'took: {}'.format(datetime.now() - start_time)
        logger.debug(log_statement)

        # Check trade conditions
        task_1 = asyncio.create_task(self.rsi_div_trade(open_positions, recent_alerts_symbols))
        task_2 = asyncio.create_task(self.rsi_macd_trade(open_positions, recent_alerts_symbols))
        task_3 = asyncio.create_task(self.rsi_ob_os_marker())
        await task_1
        await task_2
        await task_3

        heiken_ashi_check = asyncio.create_task(self.check_heiken_ashi())
        task_1 = asyncio.create_task(self.purge_alerts())
        task_2 = asyncio.create_task(self.purge_rsi_markers())
        await heiken_ashi_check
        await task_1
        await task_2

        if self.recent_alerts:
            recent = ', '.join(self.recent_alerts)
            logger.debug(recent)
        total_time = datetime.now() - start_time
        log_statement = 'total_time: {}'.format(total_time)
        logger.debug(log_statement)
        if self.recent_alerts or self.ready_symbols:
            self.debug_statements()

    def save_data(self):
        self.data.save_latest_data()

    def schedule_tasks(self):
        self.scheduler.add_job(self.save_data, trigger='cron', minute='*/1', second='2')
        # self.scheduler.add_job(self.check_conditions, trigger='cron', minute='*/1')
        self.scheduler.start()

    def stop_tasks(self):
        self.scheduler.remove_all_jobs()
        self.scheduler.shutdown()

    def loop(self):
        try:
            asyncio.run(self.get_signals())
            self.record_trend()
            self.schedule_tasks()
            while datetime.now().second != 3:
                time.sleep(1)
            log_statement = f'Starting mainloop at {datetime.now().strftime("%H:%M:%S")}'
            logger.info(log_statement)
            while True:
                asyncio.run(self.check_conditions())
                while datetime.now().second != 3:
                    time.sleep(1)
        except KeyboardInterrupt as e:
            self.stop_tasks()
            sys.exit()

    def debug_statements(self):
        log = 'Recent alerts: ' + ', '.join(self.recent_alerts)
        logger.debug(log)
        log = 'Ready symbols: ' + ', '.join(self.ready_symbols)
        logger.debug(log)


if __name__ == '__main__':
    at = AlgoTrader()
    at.loop()
