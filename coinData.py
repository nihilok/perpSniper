import csv
import os
import sys
import time
from datetime import datetime, timedelta
from threading import Thread

import pandas as pd
from binance.client import Client
from binance.websockets import BinanceSocketManager
from twisted.internet import reactor

from trader import Trader
from utils import get_popular_coins

client = Client(os.getenv('bbot_pub'), os.getenv('bbot_sec'))
file_path = os.path.abspath(os.path.dirname(__file__))
os.chdir(file_path)

data_path = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(data_path, 'data')


NUMBER_OF_SYMBOLS = 50


class CoinData:
    def __init__(self):
        """Get most popular symbols, download historical data, start live data web scoket"""
        print('Getting symbol list')
        self.symbols = get_popular_coins()[:NUMBER_OF_SYMBOLS]
        self.intervals = ['1m', '15m', '1h', '4h']
        self.latest_klines = {}
        self.data_dict = {}
        for s in self.symbols:
            self.data_dict[s] = {}
            self.latest_klines[s] = {}
            for interval in self.intervals:
                self.data_dict[s][interval] = []
                self.latest_klines[s][interval] = {}
        print('Downloading symbol data')
        self.get_original_data()
        self.tf_dict = {
            '1m': 1,
            '15m': 15,
            '1h': 60,
            '4h': 240,
        }
        self.bsm = BinanceSocketManager(client)
        self.conn_key = self.bsm.start_multiplex_socket(self.get_streams(), self.get_data)
        self.shutdown = False


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
        filename = os.path.join(data_path, symbol + f'-{interval}' + '.csv')
        df = pd.read_csv(filename)
        df.datetime = pd.to_datetime(df.datetime)
        df.set_index('datetime', inplace=True)
        df.rename_axis('datetime', inplace=True)
        return df

    def save_new_data(self):
        for symbol in self.symbols:
            for interval in self.intervals:
                filename = os.path.join(data_path, symbol + f'-{interval}' + '.csv')
                if self.latest_klines[symbol][interval]:
                    new_row = [datetime.fromtimestamp(self.latest_klines[symbol][interval]['t']/1000),
                               self.latest_klines[symbol][interval]['o'],
                               self.latest_klines[symbol][interval]['h'],
                               self.latest_klines[symbol][interval]['l'],
                               self.latest_klines[symbol][interval]['c'],
                               self.latest_klines[symbol][interval]['q']]
                    old_rows = []
                    with open(filename, 'r') as f:
                        reader = csv.reader(f)
                        for row in reader:
                            if row:
                                old_rows.append(row)
                    if old_rows:
                        old_dt = str(old_rows[-1][0])
                        new_dt = str(new_row[0])
                        # print(old_rows[-1], new_row)
                        if old_dt == new_dt:
                            old_rows.pop(-1)
                            old_rows.append(new_row)
                            with open(filename, 'w', newline='') as f:
                                writer = csv.writer(f)
                                writer.writerows(old_rows)
                                # print(f'{symbol} {interval} changed old row')
                        else:
                            with open(filename, 'a', newline='') as f:
                                writer = csv.writer(f)
                                writer.writerow(new_row)
                                # print(f'{symbol} {interval} wrote new row')
                    else:
                        with open(filename, 'a', newline='') as f:
                            writer = csv.writer(f)
                            writer.writerow(new_row)
                            # print(f'{symbol} {interval} wrote first row')

    def get_original_data(self):
        for symbol in self.symbols:
            for interval in self.intervals:
                filename = os.path.join(data_path, symbol + f'-{interval}' + '.csv')
                data = client.futures_klines(symbol=symbol, interval=interval, requests_params={'timeout': 20})
                with open(filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    first_row = ['datetime', 'open', 'high', 'low', 'close', 'volume']
                    writer.writerow(first_row)
                    for kline in data:
                        row = [datetime.fromtimestamp(kline[0]/1000),
                               float(kline[1]),
                               float(kline[2]),
                               float(kline[3]),
                               float(kline[4]),
                               float(kline[7]),
                               ]
                        writer.writerow(row)

    def get_streams(self):
        streams = []
        for symbol in self.symbols:
            streams += [f'{symbol.lower()}@kline_1m', f'{symbol.lower()}@kline_15m', f'{symbol.lower()}@kline_1h',
                        f'{symbol.lower()}@kline_4h']
        return streams

    def websocket_loop(self):
        try:
            self.bsm.start()
            while True:
                time.sleep(1)
        except Exception as e:
            self.bsm_tear_down()
            raise e

    def bsm_tear_down(self):
        self.shutdown = True
        self.bsm.stop_socket(self.conn_key)
        reactor.stop()


if __name__ == "__main__":
    c = CoinData()
    c.websocket_loop()