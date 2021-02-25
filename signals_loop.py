import base64
import io
import os
import sqlite3
import time
import logging

from collections import Counter

from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from binance.exceptions import BinanceAPIException

from signals import Signals
from coinData import CoinData


scheduler = BackgroundScheduler()

file_path = os.path.abspath(os.path.dirname(__file__))
os.chdir(file_path)

# flush log file
try:
    with open('log.log', 'r') as f:
        lines = f.readlines()
    if len(lines) >= 88:
        with open('log.log', 'w') as f:
            f.writelines(lines[-88:])
except FileNotFoundError:
    pass

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, filename='log.log')


class MainLoop:

    def __init__(self, coin_data):
        os.system('cls' if os.name == 'nt' else 'clear')
        print("15m, 1h & 4h signals update every minute to offer an early warning of events occuring on current (unclosed) candle's close. **Expect false positives**\nIf signals are still true they "
              "are only repeated after 30 minutes\nHint: Look for volume signals to confirm other signals")
        self.data_lock = True
        self.data = coin_data
        self.coins = self.data.symbols
        print(f'''Current Symbols (highest volume):
{', '.join(self.coins)}''')
        try:
            self.conn = self.open_database()
            self.flush_db()
            self.data_lock = False
        except Exception as e:
            raise e

    def open_database(self):
        path = os.path.abspath(os.path.dirname(__file__))
        file = os.path.join(path, 'signals.db')
        self.conn = sqlite3.connect(file)
        return self.conn

    def close_database(self):
        if self.conn:
            self.conn.close()

    def get_qs(self):
        self.open_database()
        c = self.conn.cursor()
        qs = [a for a in c.execute('SELECT * FROM signals')]
        c.close()
        self.close_database()
        return qs

    def flush_db(self):
        alert_times = []
        qs = self.get_qs()
        for alert in qs:
            if self.check_time(alert):
                alert_times.append(f'{alert[0]}',)
        at = tuple(alert_times)
        self.delete_multiple_records(at)

    @staticmethod
    def check_time(alert, minutes=30):
        full_time = datetime.strptime(datetime.now().strftime('%Y-%m-%d ') + alert[0],
                                      '%Y-%m-%d %H:%M:%S')
        if full_time < datetime.now() - timedelta(minutes=minutes) or full_time > datetime.now():
            return True

    def delete_multiple_records(self, idList):
        try:
            self.open_database()
            c = self.conn.cursor()
            idList = [(a, ) for a in idList]
            sqlite_update_query = f"""DELETE from signals where time = ?"""
            c.executemany(sqlite_update_query, idList)
            self.conn.commit()
            c.close()

        except sqlite3.Error as error:
            print("Failed to delete multiple records from sqlite table", error)
        finally:
            self.close_database()

    def get_popular_coins(self):
        self.data = CoinData()
        self.coins = self.data.symbols
        print(f'''Current Symbols (highest volume):
{', '.join(self.coins)}''')
        return self.coins

    def register_alert(self, alert, coin, tf):
        try:
            self.open_database()
            c = self.conn.cursor()
            c.execute(f'''INSERT INTO signals VALUES 
            ("{alert[0]}", "{coin}", "({tf}) {alert[1]}{' ' + alert[2] if len(alert) == 3 else ''}")''')
            self.conn.commit()
            c.close()
        except sqlite3.Error as error:
            print("Failed to register alert for " + coin, error)
        finally:
            self.close_database()

    def check_alert(self, alert, coin, tf):
        self.open_database()
        c = self.conn.cursor()
        qs = c.execute(f'''SELECT * FROM signals WHERE symbol="{coin}" AND alert="({tf}) {alert[1]}{' ' + alert[2] if len(alert) == 3 else ''}"''')
        qs = [a for a in qs]
        c.close()
        self.close_database()
        if len(qs):
            return True
        return False

    def check_hot_coins(self):
        self.open_database()
        c = self.conn.cursor()
        qs = c.execute(f'''SELECT * FROM signals''')

        symbols = []
        hot_coins = []
        for rec in qs:
            symbols.append(rec[1])
        C = Counter(symbols)
        for item in C.items():
            if item[1] >= 3:
                hot_coins.append(item)
        c.close()
        self.close_database()
        return list(sorted(hot_coins, key=lambda x: x[1], reverse=True))[:6]

    def mainloop(self):
        bad_coins = []
        for coin in self.coins:
            check_time = datetime.now()
            try:
                signals_15m = Signals(coin, tf='15m')
                self.check_signals_object(signals_15m, coin, check_time)
            except BinanceAPIException as e:
                print(f'Something went wrong with {coin}: {e}')
                continue
            except IndexError:
                bad_coins.append(coin)
                continue
            try:
                signals_1h = Signals(coin, tf='1h')
                self.check_signals_object(signals_1h, coin, check_time)
            except BinanceAPIException as e:
                print(f'Something went wrong with {coin}: {e}')
                continue
            except IndexError:
                pass
            try:
                signals_4h = Signals(coin)
                self.check_signals_object(signals_4h, coin, check_time)
            except BinanceAPIException as e:
                print(f'Something went wrong with {coin}: {e}')
            except IndexError:
                pass
        self.flush_db()
        for coin in bad_coins:
            self.coins.remove(coin)

    def check_signals_object(self, signals_obj, coin, check_time):
        for k, v in signals_obj.ema_signals_dict.items():
            if v is True:
                alert = (check_time.strftime("%H:%M:%S"), k, 'bullish')
                if not self.check_alert(alert, coin, signals_obj.tf):
                    self.register_alert(alert, coin, signals_obj.tf)
            elif v is False:
                alert = (check_time.strftime("%H:%M:%S"), k, 'bearish')
                if not self.check_alert(alert, coin, signals_obj.tf):
                    self.register_alert(alert, coin, signals_obj.tf)
        for k, v in signals_obj.rsi_div_dict.items():
            if v is True:
                alert = (check_time.strftime("%H:%M:%S"), k)
                if not self.check_alert(alert, coin, signals_obj.tf):
                    self.register_alert(alert, coin, signals_obj.tf)
        for k, v in signals_obj.rsi_ob_os_dict.items():
            if v is True:
                alert = (check_time.strftime("%H:%M:%S"), k)
                if not self.check_alert(alert, coin, signals_obj.tf):
                    self.register_alert(alert, coin, signals_obj.tf)
        for k, v in signals_obj.macd_dict.items():
            if v is not None:
                if v is True:
                    v = 'up'
                else:
                    v = 'down'
                alert = (check_time.strftime("%H:%M:%S"), ' '.join((k, v)))
                if not self.check_alert(alert, coin, signals_obj.tf):
                    self.register_alert(alert, coin, signals_obj.tf)
        if signals_obj.vol_signal:
            alert = (check_time.strftime("%H:%M:%S"), 'Volume rising')
            if not self.check_alert(alert, coin, signals_obj.tf):
                self.register_alert(alert, coin, signals_obj.tf)
        if signals_obj.vol_candle:
            alert = (check_time.strftime("%H:%M:%S"), 'Current candle large volume')
            if not self.check_alert(alert, coin, signals_obj.tf):
                self.register_alert(alert, coin, signals_obj.tf)

    def start_jobs(self, jobs=None):
        """@param jobs: list of tuples (job, trigger, interval)"""
        scheduler.start()
        scheduler.add_job(self.mainloop, trigger="cron", minute='*/1')
        scheduler.add_job(self.get_popular_coins, trigger="cron", hour='*/1')
        scheduler.add_job(self.data.save_new_data, trigger="interval", seconds=2)
        if jobs:
            for job in jobs:
                if job[1] == 'interval':
                    scheduler.add_job(job[0], trigger=job[1], seconds=job[2])
                elif job[1] == 'cron':
                    scheduler.add_job(job[0], trigger=job[1], second=job[2])


    def teardown(self):
        self.close_database()
        scheduler.remove_all_jobs()
        scheduler.shutdown()
        self.data.teardown()
        print('signals loop teardown completed')


# if __name__ == '__main__':
#     loop = MainLoop()
#     try:
#         loop.check_hot_coins()
#         loop.mainloop()
#         loop.start_jobs()
#         while True:
#             time.sleep(1)
#     finally:
#         loop.teardown()