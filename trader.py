import csv
import http
import json
import logging
import os
import sqlite3
import time
import stdiomask
from datetime import datetime
from math import fabs
from threading import Thread
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException
from binance.websockets import BinanceSocketManager
from http.client import RemoteDisconnected
from urllib3.exceptions import ProtocolError
from requests.exceptions import ConnectionError

file_path = os.path.abspath(os.path.dirname(__file__))
os.chdir(file_path)
data_path = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(data_path, 'data')

logger = logging.getLogger(__name__)


def check_symbol(symbol):
    safe_symbol = symbol
    if not symbol[0].isalpha():
        safe_symbol = symbol[1:]
        check_symbol(safe_symbol)
    return safe_symbol


def setup():
    """Initial setup getting user input"""
    os.system('cls' if os.name == 'nt' else 'clear')
    print('Welcome to perpSniper v0.2 *alpha version, not financial advice, use at your own risk!')
    print('Initial setup needed....')
    print('\n\n\n\n')
    settings = {'api_key': input('api_key: '), 'api_secret': stdiomask.getpass('api_secret: '),
                'sl': float(input('stop loss percentage (price %, e.g. 0.5): ')) / 100,
                'tp': float(input('take profit percentage (price %, e.g. 2.5): ')) / 100,
                'db': float(input('trailing stop drawback (price %, e.g. 0.1): ')),
                'qty': float(input('percentage stake (margin balance %, e.g. 5: ')) / 100}
    with open('settings.json', 'w') as f:
        json.dump(settings, f)


def get_settings():
    """Check for and get settings"""
    try:
        keycheck = ['api_key', 'api_secret', 'sl', 'tp', 'db', 'qty']
        # file_path = os.path.dirname(__file__)
        # file = os.path.join(file_path, 'settings.json')
        with open('settings.json', 'r') as f:
            settings = json.load(f)
        for key in keycheck:
            if key not in settings.keys():
                raise KeyError
        return settings
    except (FileNotFoundError, KeyError) as e:
        print(e)
        setup()
        return get_settings()


class Trade:
    def __init__(self,
                 symbol: str,
                 direction: bool,
                 quantity: float,
                 tp: float,
                 sl: float,
                 db: float,
                 info: dict,
                 trader,
                 perpetual=False):
        """
            Create long or short trade.
            :param symbol: str denoting symbol pair to be traded, e.g. 'BTCUSDT'
            :param direction: bool indicating if trade direction is long (True) or short (False)
            :param quantity: float percentage of balance to be traded
            :param tp: float take profit activation price
            :param sl: float stop loss stop price
            :param db: float callback/drawback rate for trailing tp
            :param info: dict symbol exchange information such as 'pricePrecision'
            :param trader: Trader class object with Binance api client
        """
        self.date = datetime.now()
        self.symbol = symbol
        self.direction = direction
        # self.price = float(approx_price)
        self.quantity = float(quantity)
        self.trader = trader
        self.client = trader.client
        self.info = info
        self.tp = tp
        self.sl = sl
        self.db = float(db)
        self.price_decimals = f"{{:.{self.info['pricePrecision']}f}}"
        if not perpetual:
            self.trade()
            self.price = self.update_entry_price()
            self.stop_loss()
            self.take_profit()

    def update_entry_price(self):
        for position in self.trader.return_open_positions():
            if position['symbol'] == self.symbol:
                self.price = position['entry']
                return self.price
        time.sleep(0.1)
        self.update_entry_price()

    def trade(self):
        order_type = 'MARKET'
        side = 'BUY' if self.direction else 'SELL'
        try:
            self.client.futures_create_order(
                type=order_type,
                side=side,
                quantity=self.quantity,
                symbol=self.symbol,
            )
        except (BinanceAPIException, BinanceOrderException) as e:
            raise e

    def take_profit(self):
        order_type = 'TRAILING_STOP_MARKET'
        side = 'SELL' if self.direction else 'BUY'
        if self.direction:
            stop_price = float(self.price_decimals.format(self.price + (self.price * self.tp)))
        else:
            stop_price = float(self.price_decimals.format(self.price - (self.price * self.tp)))
        try:
            self.client.futures_create_order(
                type=order_type,
                side=side,
                quantity=self.quantity,
                reduceOnly=True,
                workingType='MARK_PRICE',
                symbol=self.symbol,
                activationPrice=stop_price,
                callbackRate=self.db
            )
        except (BinanceAPIException, BinanceOrderException) as e:
            raise e

    def stop_loss(self):
        order_type = 'STOP_MARKET'
        side = 'SELL' if self.direction else 'BUY'
        if self.direction:
            stop_price = float(self.price_decimals.format(self.price - (self.price * self.sl)))
        else:
            stop_price = float(self.price_decimals.format(self.price + (self.price * self.sl)))
        try:
            self.client.futures_create_order(
                type=order_type,
                side=side,
                quantity=self.quantity,
                reduceOnly=True,
                symbol=self.symbol,
                stopPrice=stop_price,
                workingType='MARK_PRICE',
            )
        except (BinanceAPIException, BinanceOrderException) as e:
            raise e


class PerpetualTrade(Trade):

    trade_counter = 0

    def __init__(self, *args):
        super().__init__(*args, perpetual=True)
        if self.direction is True:
            self.long()
        elif self.direction is False:
            self.short()
        else:
            return
        self.update_entry_price()
        self.stop_loss()

    def long(self):
        if self.direction is True:
            self.trade()
        elif self.direction is False:
            self.reverse_trade()
        self.trade_counter += 1

    def short(self):
        if self.direction is False:
            self.trade()
        elif self.direction is True:
            self.reverse_trade()
        self.trade_counter += 1

    def flat(self):
        if self.trade_counter > 2:
            self.quantity /= 2
        self.trader.close_position(self.symbol)
        self.trade_counter = 0
        self.direction = None

    def reverse_trade(self):
        self.client.futures_cancel_all_open_orders(symbol=self.symbol)
        self.direction = False if self.direction else True
        if self.trade_counter == 1:
            self.quantity *= 2
        self.trade()
        try:
            self.update_entry_price()
            self.stop_loss()
        except (BinanceAPIException, BinanceOrderException) as e:
            raise e


class Trader:
    def __init__(self):
        """
        Set up constants, and keep track of trades
        """
        self.threads = []
        self.LEVERAGE = 20
        self.config = []
        self.open_trades = {}
        self.mark_prices = {}
        self.open_positions_local = []
        self.settings = get_settings()
        self.client = Client(self.settings['api_key'], self.settings['api_secret'], requests_params={'timeout': 30})
        self.server_time = datetime.fromtimestamp(self.return_server_time()).strftime('%H:%M:%S')
        self.bsm_1 = BinanceSocketManager(self.client)

    def start_thread(self, func):
        t = Thread(target=func)
        t.setDaemon(True)
        t.start()
        self.threads.append(t)

    def stop_threads(self):
        for thread in self.threads:
            thread.join()

    def trade(self, symbol, direction):
        symbol = symbol.upper()
        quantity, approx_price, info = self.calculate_max_qty(symbol)
        try:
            t = Trade(symbol,
                      direction,
                      quantity,
                      float(self.settings['tp']),
                      float(self.settings['sl']),
                      float(self.settings['db']),
                      info,
                      self)
            self.open_trades[t.date] = t
        except (BinanceAPIException, BinanceOrderException) as e:
            raise e

    @staticmethod
    def get_price(symbol):
        conn = sqlite3.connect('symbols.db')
        c = conn.cursor()
        symbol = check_symbol(symbol)
        try:
            q = f'SELECT * FROM {symbol}_15m WHERE date = (SELECT MAX(date) FROM {symbol}_15m)'
            price = c.execute(q).fetchone()[3]
        finally:
            conn.close()
        return price

    def get_account_info(self):
        ac_info = self.client.futures_account()
        maintenance = '{:.2f}'.format(float(ac_info['totalMaintMargin']))
        balance = '{:.2f}'.format(float(ac_info['totalWalletBalance']))
        total_pnl = '{:.2f}'.format(float(ac_info['totalUnrealizedProfit']))
        margin_balance = '{:.2f}'.format(float(ac_info['totalMarginBalance']))
        account_dict = {
            'maintenance': maintenance,
            'balance': balance,
            'total_pnl': total_pnl,
            'margin_balance': margin_balance
        }
        return account_dict

    def get_usdt_balance(self):
        return float(self.get_account_info()['balance'])

    def calculate_max_qty(self, symbol):
        price = float(self.get_price(symbol))
        usdt_bal = self.get_usdt_balance()
        affordable = usdt_bal / price
        qty = affordable * float(self.settings['qty']) * self.LEVERAGE
        info = [s for s in self.client.futures_exchange_info()['symbols'] if s['symbol'] == symbol][0]
        qty_precision = info['quantityPrecision']
        decimals = f'{{:.{qty_precision}f}}'
        qty = float(decimals.format(qty))
        return qty, price, info

    def return_open_positions(self):
        acc = self.client.futures_account()
        positions = acc['positions']
        position_list = []
        for position in positions:
            if float(position['positionAmt']) > 0:
                roe = (float(position['unrealizedProfit']) / (
                      (float(position['positionAmt']) * float(position['entryPrice'])) / int(
                       position['leverage']))) * 100
                direction = 'LONG'
            elif float(position['positionAmt']) < 0:
                roe = -(float(position['unrealizedProfit']) / (
                       (float(position['positionAmt']) * float(position['entryPrice'])) / int(
                        position['leverage']))) * 100
                direction = 'SHORT'
            else:
                continue
            position = {
                'symbol': position['symbol'],
                'qty': position['positionAmt'],
                'entry': float(position['entryPrice']),
                'pnl': float(position['unrealizedProfit']),
                'roe': roe,
                'direction': direction,
            }
            position_list.append(position)
        return position_list

    def positions_set(self):
        return set([position['symbol'] for position in self.return_open_positions()])

    def check_positions_cancel_open_orders(self):
        try:
            positions_symbols = set([position['symbol'] for position in self.return_open_positions()])
            orders = self.client.futures_get_open_orders()
            orders_symbols = set([order['symbol'] for order in orders])
            diff = orders_symbols.difference(positions_symbols)
            for s in diff:
                self.client.futures_cancel_all_open_orders(symbol=s)
            return orders_symbols
        except (RemoteDisconnected, ProtocolError, ConnectionError) as e:
            error = f'Binance connection error: {e}'
            logger.error(error)
            time.sleep(1)
            self.check_positions_cancel_open_orders()

    def close_position(self, symbol):
        for position in self.return_open_positions():
            if position['symbol'] == symbol:
                direction = True if position['direction'] == 'LONG' else False
                side = 'SELL' if direction else 'BUY'
                qty = fabs(float(position['qty']))
                self.client.futures_create_order(
                    type='MARKET',
                    reduceOnly=True,
                    symbol=symbol,
                    side=side,
                    quantity=qty
                )
                self.check_positions_cancel_open_orders()
                break

    def close_all_positions(self):
        for position in self.return_open_positions():
            direction = True if position['direction'] == 'LONG' else False
            side = 'SELL' if direction else 'BUY'
            qty = fabs(float(position['qty']))
            self.client.futures_create_order(
                type='MARKET',
                reduceOnly=True,
                symbol=position['symbol'],
                side=side,
                quantity=qty
            )

    def return_server_time(self):
        time_dict = self.client.get_server_time()
        original_server_time = time_dict['serverTime']/1000
        return original_server_time

    def count_server_time(self, ost):
        while True:
            ost += 1
            time.sleep(1)
            self.server_time = datetime.fromtimestamp(ost).strftime('%H:%M:%S')


if __name__ == '__main__':
    print(Trader.get_price('BTCUSDT'))
