import getpass
import json
import os
import sys
import time
from datetime import datetime
from math import fabs
from threading import Thread

import stdiomask
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException
from binance.websockets import BinanceSocketManager
from twisted.internet import reactor

file_path = os.path.abspath(os.path.dirname(__file__))
os.chdir(file_path)


def setup():
    os.system('cls' if os.name == 'nt' else 'clear')
    print('Welcome to perpSniper v0.2 *alpha version, not financial advice, use at your own risk!')
    print('Initial setup needed....')
    print('\n\n\n\n')
    settings = {}
    settings['api_key'] = input('api_key: ')
    settings['api_secret'] = stdiomask.getpass('api_secret: ')
    settings['sl'] = float(input('stop loss percentage (price %, e.g. 0.5): '))/100
    settings['tp'] = float(input('take profit percentage (price %, e.g. 2.5): '))/100
    settings['db'] = float(input('trailing stop drawback (price %, e.g. 0.1): '))
    settings['qty'] = float(input('percentage stake (margin balance %, e.g. 5: '))/100
    with open('settings.json', 'w') as f:
        json.dump(settings, f)


def get_settings():
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


def tear_down(bsm, conn_key):
    bsm.stop_socket(conn_key)
    reactor.stop()


class Trade:
    def __init__(self,
                 symbol: str,
                 direction: bool,
                 quantity: float,
                 approx_price: float,
                 tp: float,
                 sl: float,
                 db: float,
                 info: dict,
                 trader):
        """
        Create long or short trade.
        :param symbol: str denoting symbol pair to be traded, e.g. 'BTCUSDT'
        :param direction: bool indicating if trade direction is long (True) or short (False)
        :param quantity: float percentage of balance to be traded
        :param approx_price: float approximate mark price at time of trade
        :param tp: float take profit activation price
        :param sl: float stop loss stop price
        :param db: float callback/drawback rate for trailing tp
        :param info: dict symbol exchange information such as 'pricePrecision'
        :param trader: Trader class object with Binance api client
        """
        self.date = datetime.now()
        self.symbol = symbol
        self.direction = direction
        self.price = float(approx_price)
        self.quantity = float(quantity)
        self.trader = trader
        self.client = trader.client
        self.info = info
        self.tp = tp
        self.sl = sl
        self.db = float(db)
        self.price_decimals = f"{{:.{self.info['pricePrecision']}f}}"
        self.trade()
        self.update_entry_price()
        self.stop_loss()
        self.take_profit()

    def update_entry_price(self):
        found = False
        for position in self.trader.return_open_positions():
            if position['symbol'] == self.symbol:
                found = True
                self.price = position['entry']
        if not found:
            time.sleep(0.1)
            self.update_entry_price()

    def trade(self):
        type = 'MARKET'
        side = 'BUY' if self.direction else 'SELL'
        try:
            self.client.futures_create_order(
                type=type,
                side=side,
                quantity=self.quantity,
                symbol=self.symbol,
            )
        except (BinanceAPIException, BinanceOrderException) as e:
            raise e

    def take_profit(self):
        type = 'TRAILING_STOP_MARKET'
        side = 'SELL' if self.direction else 'BUY'
        if self.direction:
            stop_price = float(self.price_decimals.format(self.price + (self.price * self.tp)))
        else:
            stop_price = float(self.price_decimals.format(self.price - (self.price * self.tp)))
        try:
            self.client.futures_create_order(
                type=type,
                side=side,
                quantity=self.quantity,
                reduceOnly=True,
                # closePosition=True,
                workingType='MARK_PRICE',
                symbol=self.symbol,
                activationPrice=stop_price,
                callbackRate=self.db
            )
        except (BinanceAPIException, BinanceOrderException) as e:
            raise e

    def stop_loss(self):
        type = 'STOP_MARKET'
        side = 'SELL' if self.direction else 'BUY'
        if self.direction:
            stop_price = float(self.price_decimals.format(self.price - (self.price * self.sl)))
        else:
            stop_price = float(self.price_decimals.format(self.price + (self.price * self.sl)))
        try:
            self.client.futures_create_order(
                type=type,
                side=side,
                quantity=self.quantity,
                reduceOnly=True,
                symbol=self.symbol,
                stopPrice=stop_price,
                workingType='MARK_PRICE',
            )
        except (BinanceAPIException, BinanceOrderException) as e:
            raise e

class MyBinanceSocketManager(BinanceSocketManager):
    def start_user_socket(self, callback):
        """Start a websocket for user data
        """

        # Get the user listen key
        user_listen_key = self._client.stream_get_listen_key()
        # and start the socket with this specific key
        return self._start_account_socket('userData', user_listen_key, callback)


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
        self.client = Client(self.settings['api_key'], self.settings['api_secret'])
        self.server_time = datetime.fromtimestamp(self.return_server_time()).strftime('%H:%M:%S')
        self.bsm_1 = BinanceSocketManager(self.client)
        # self.bsm_2 = MyBinanceSocketManager(self.client)
        self.start_thread(self.get_symbol_info)
        time.sleep(2)
        # self.start_thread(self.user_socket)

        self.open_positions_actual = self.positions_set()
        self.open_positions_local = self.open_positions_actual

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
                      approx_price,
                      float(self.settings['tp']),
                      float(self.settings['sl']),
                      float(self.settings['db']),
                      info,
                      self)
            self.open_trades[t.date] = t
            self.open_positions_local.add(symbol)
        except (BinanceAPIException, BinanceOrderException) as e:
            raise e

    def get_mark_prices(self, msg):
        for symbol in msg['data']:
            if symbol['e'] == 'markPriceUpdate':
                last_price = float(symbol['p'])
                self.mark_prices[symbol['s']] = last_price

    def get_symbol_info(self):
        # noinspection PyTypeChecker
        conn_key = self.bsm_1.start_all_mark_price_socket(self.get_mark_prices)
        try:
            self.bsm_1.start()
            while True:
                time.sleep(1)
        except KeyboardInterrupt as e:
            tear_down(self.bsm_1, conn_key)
            sys.exit()

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
        price = float(self.mark_prices[symbol])
        usdt_bal = self.get_usdt_balance()
        affordable = usdt_bal / price
        qty = affordable * float(self.settings['qty']) * self.LEVERAGE
        info = [s for s in self.client.futures_exchange_info()['symbols'] if s['symbol'] == symbol][0]
        qtyPrecision = info['quantityPrecision']
        decimals = f'{{:.{qtyPrecision}f}}'
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
        positions_symbols = set([position['symbol'] for position in self.return_open_positions()])
        orders_symbols = set([order['symbol'] for order in self.client.futures_get_open_orders()])
        diff = orders_symbols.difference(positions_symbols)
        for s in diff:
            self.client.futures_cancel_all_open_orders(symbol=s)

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
    t = Trader()