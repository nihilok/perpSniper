import os
import sqlite3
import time
from datetime import datetime, timedelta
from threading import Thread

import pandas as pd
from binance.websockets import BinanceSocketManager
from twisted.internet import reactor

from trader import Trader
from utils import get_popular_coins

client = Trader().client
file_path = os.path.abspath(os.path.dirname(__file__))
os.chdir(file_path)

data_path = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(data_path, 'data')


NUMBER_OF_SYMBOLS = 50


class CoinData:
    def __init__(self):
        """Get most popular symbols, download historical data, start live data web socket"""
        print('Getting symbol list')
        self.symbols = get_popular_coins()  # [:NUMBER_OF_SYMBOLS]
        self.intervals = ['1m', '15m', '1h', '4h']    # '1m',
        self.latest_klines = {}
        self.data_dict = {}
        for s in self.symbols:
            self.data_dict[s] = {}
            self.latest_klines[s] = {}
            for interval in self.intervals:
                self.data_dict[s][interval] = []
                self.latest_klines[s][interval] = {}

        self.tf_dict = {
            '1m': 1,
            '15m': 15,
            '1h': 60,
            '4h': 240,
        }
        self.bsm = BinanceSocketManager(client)
        self.conn_key = self.bsm.start_multiplex_socket(self.get_streams(), self.get_data)
        self.shutdown = False
        self.t = Thread(target=self.websocket_loop)
        self.t.setDaemon(True)
        self.t.start()
        self.create_database()
        print('Coin data initialized')

    def get_data(self, msg):
        static = msg
        if not self.latest_klines[static['data']['k']['s']][static['data']['k']['i']]:
            self.latest_klines[static['data']['k']['s']][static['data']['k']['i']] = static['data']['k']
        elif datetime.fromtimestamp(static['data']['k']['t']/1000) >= datetime.fromtimestamp(self.latest_klines[static['data']['k']['s']][static['data']['k']['i']]['t']/1000):
            self.latest_klines[static['data']['k']['s']][static['data']['k']['i']] = static['data']['k']
        else:
            print('______WARNING______')
            print('caught irrelevant timestamp: ' + datetime.fromtimestamp(static['data']['k']['t']/1000).strftime('%H:%M:%S'))
            print(static['data']['k']['s'] + static['data']['k']['i'])

    @staticmethod
    def get_dataframe(symbol, interval):
        if not symbol[0].isalpha():
            symbol = symbol[1:]
        conn = sqlite3.connect('symbols.db')
        try:
            df = pd.read_sql_query(f'SELECT * FROM {symbol}_{interval}', conn)
            df.date = pd.to_datetime(df.date)
            df.set_index('date', inplace=True)
            df.rename_axis('date', inplace=True)
        finally:
            conn.close()
        return df

    def create_database(self):
        if os.path.isfile('symbols.db'):
            conn = sqlite3.connect('symbols.db')
            cursor = conn.cursor()
            tabs = {tab[0] for tab in cursor.execute("select name from sqlite_master where type = 'table'").fetchall()}
            time = cursor.execute('SELECT MAX(date) FROM BTCUSDT_15m').fetchone()[0]
            if time and datetime.strptime(time, '%Y-%m-%d %H:%M:%S') >= datetime.now() - timedelta(minutes=30):
                for symbol in self.symbols:
                    if self.check_symbol(symbol + '_15m') in tabs:
                        continue
                    else:
                        print(f'{symbol} not in tabs')
                        os.remove('symbols.db')
                        self.create_database()
                        break
                return
            else:
                print(f'{time} is too old')
                os.remove('symbols.db')
                self.create_database()
        else:
            print('recreating database from scratch')
            conn = sqlite3.connect('symbols.db')
            cursor = conn.cursor()
            try:
                for symbol in self.symbols:
                    for interval in self.intervals:
                        safe_symbol = self.check_symbol(symbol)
                        query = f'CREATE TABLE {safe_symbol}_{interval} (date datetime, open dec(6, 8), ' \
                                f'high dec(6, 8), low dec(6, ' \
                                f'8), close dec(' \
                                f'6, 8), volume dec(12, 2))'
                        try:
                            cursor.execute(query)
                        except sqlite3.OperationalError as e:
                            if str(e)[-6:] == 'exists':
                                continue
                            else:
                                raise e
                print('created tables for ' + ', '.join(self.symbols))
                self.save_original_data()
            finally:
                conn.commit()
                conn.close()

    def check_symbol(self, symbol):
        safe_symbol = symbol
        if not symbol[0].isalpha():
            safe_symbol = symbol[1:]
            self.check_symbol(safe_symbol)
        return safe_symbol

    def save_original_data(self):
        print('Downloading historical data')
        conn = sqlite3.connect('symbols.db')
        cursor = conn.cursor()
        try:
            for symbol in self.symbols:
                for interval in self.intervals:
                    data = client.futures_klines(symbol=symbol, interval=interval, requests_params={'timeout': 20})
                    for kline in data:
                        row = [datetime.fromtimestamp(kline[0] / 1000),
                               float(kline[1]),
                               float(kline[2]),
                               float(kline[3]),
                               float(kline[4]),
                               float(kline[7]),
                               ]
                        safe_symbol = self.check_symbol(symbol)
                        query = f'''INSERT INTO {safe_symbol}_{interval} VALUES 
    ("{row[0]}", {row[1]}, {row[2]}, {row[3]}, {row[4]}, {row[5]})'''
                        cursor.execute(query)
        finally:
            conn.commit()
            conn.close()

    def save_latest_data(self):
        conn = sqlite3.connect('symbols.db')
        cursor = conn.cursor()
        try:
            for symbol in self.symbols:
                for interval in self.intervals:
                    if self.latest_klines[symbol][interval]:
                        new_row = [datetime.fromtimestamp(self.latest_klines[symbol][interval]['t'] / 1000),
                                   self.latest_klines[symbol][interval]['o'],
                                   self.latest_klines[symbol][interval]['h'],
                                   self.latest_klines[symbol][interval]['l'],
                                   self.latest_klines[symbol][interval]['c'],
                                   self.latest_klines[symbol][interval]['q']]
                        safe_symbol = self.check_symbol(symbol)
                        date_query= f'SELECT MAX(date) FROM {safe_symbol}_{interval}'
                        old_row_date = cursor.execute(date_query).fetchone()[0]
                        if str(old_row_date) == str(new_row[0]):
                            query = f'UPDATE {safe_symbol}_{interval} SET open = {new_row[1]}, high = {new_row[2]}, low = {new_row[3]}, close = {new_row[4]}, volume = {new_row[5]} WHERE date = (SELECT MAX(date) FROM {safe_symbol}_{interval})'
                        else:
                            query = f'''INSERT INTO {safe_symbol}_{interval} VALUES 
    ("{new_row[0]}", {new_row[1]}, {new_row[2]}, {new_row[3]}, {new_row[4]}, {new_row[5]})'''
                        cursor.execute(query)
        finally:
            conn.commit()
            conn.close()

    def get_streams(self):
        streams = []
        for symbol in self.symbols:
            for interval in self.intervals:
                streams += [f'{symbol.lower()}@kline_{interval.lower()}']
        return streams

    def websocket_loop(self):
        try:
            self.bsm.start()
            while True:
                time.sleep(1)
        except Exception as e:
            print(e)
        finally:
            self.bsm_tear_down()

    def bsm_tear_down(self):
        self.bsm.stop_socket(self.conn_key)
        reactor.stop()
        print('bsm tear down success')


if __name__ == "__main__":
    # c = CoinData()
    print(CoinData.get_dataframe('BTCUSDT', '1h'))