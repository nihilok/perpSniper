import time
from threading import Thread

from binance.websockets import BinanceSocketManager
from twisted.internet import reactor

import trader as tr

t = tr.Trader()
bsm = BinanceSocketManager(t.client)


def return_open_positions():
    positions = t.client.futures_position_information()
    position_list = []
    for position in positions:
        if float(position['positionAmt']) > 0:
            roe = (float(position['unRealizedProfit']) / (
                        (float(position['positionAmt']) * float(position['markPrice'])) / int(
                    position['leverage']))) * 100
            direction = 'LONG'
        elif float(position['positionAmt']) < 0:
            roe = -(float(position['unRealizedProfit']) / (
                        (float(position['positionAmt']) * float(position['markPrice'])) / int(
                    position['leverage']))) * 100
            direction = 'SHORT'
        else:
            continue
        position = {
            'symbol': position['symbol'],
            'qty': position['positionAmt'],
            'pnl': float(position['unRealizedProfit']),
            'roe': roe,
            'direction': direction,
        }
        position_list.append(position)
    return position_list


def open_positions():
    positions = t.client.futures_position_information()
    messages = []
    for position in positions:
        if float(position['positionAmt']) > 0:
            pnl = (float(position['unRealizedProfit'])/((float(position['positionAmt'])*float(position['markPrice']))/int(position['leverage'])))*100
            direction = 'LONG'
        elif float(position['positionAmt']) < 0:
            pnl = -(float(position['unRealizedProfit'])/((float(position['positionAmt'])*float(position['markPrice']))/int(position['leverage'])))*100
            direction = 'SHORT'
        else:
            continue
        message = f'''symbol: {position['symbol']}
positionAmt: {position['positionAmt']} {direction} ({position['leverage']}x)
entryPrice: {str(position['entryPrice'])[:10]}
markPrice: {str(position['markPrice'])[:10]}
unRealizedProfit: {str(position['unRealizedProfit'])[:5]} USDT ({str(pnl)[:5]}% ROE)
'''
        messages.append(message)
    return messages


local_tickers = {}

check_tickers = []


def live_vol_data(tickers):
    futures_symbols = t.client.futures_exchange_info()
    futures_symbols = [symbol['symbol'] for symbol in futures_symbols['symbols']]
    futures_symbols = set(futures_symbols)
    for symbol in tickers:
        if symbol['e'] == '24hrTicker':
            if symbol['s'][-4:] == 'USDT' and symbol['s'] in futures_symbols:
                local_tickers[symbol['s']] = symbol['q']
    if len(check_tickers) >= 88:
        check_tickers.pop(0)
        check_tickers.append(local_tickers)
    else:
        check_tickers.append(local_tickers)


def ticker_websocket_loop():
    data = bsm.start_ticker_socket(live_vol_data)
    try:
        bsm.start()
        while not len(local_tickers):
            time.sleep(1)
    finally:
        bsm.stop_socket(data)

def get_popular_coins():
    ticker_websocket_loop()
    tickers = local_tickers
    sorted_tickers_list = [ticker[0] for ticker in sorted(tickers.items(), key=lambda ticker: float(ticker[1]))]
    print('found ' + str(len(sorted_tickers_list)) + ' symbols')
    return list(reversed(sorted_tickers_list))


if __name__ == '__main__':
    t = Thread(target=ticker_websocket_loop)
    t.setDaemon(True)
    t.start()
    while not len(check_tickers):
        time.sleep(1)
    print(get_popular_coins())

# ex = {'symbol': 'ETHBTC', 'status': 'TRADING', 'baseAsset': 'ETH', 'baseAssetPrecision': 8, 'quoteAsset': 'BTC',
#       'quotePrecision': 8, 'quoteAssetPrecision': 8, 'baseCommissionPrecision': 8, 'quoteCommissionPrecision': 8,
#       'orderTypes': ['LIMIT', 'LIMIT_MAKER', 'MARKET', 'STOP_LOSS_LIMIT', 'TAKE_PROFIT_LIMIT'], 'icebergAllowed': True,
#       'ocoAllowed': True, 'quoteOrderQtyMarketAllowed': True, 'isSpotTradingAllowed': True,
#       'isMarginTradingAllowed': True, 'filters': [
#         {'filterType': 'PRICE_FILTER', 'minPrice': '0.00000100', 'maxPrice': '100000.00000000',
#          'tickSize': '0.00000100'},
#         {'filterType': 'PERCENT_PRICE', 'multiplierUp': '5', 'multiplierDown': '0.2', 'avgPriceMins': 5},
#         {'filterType': 'LOT_SIZE', 'minQty': '0.00100000', 'maxQty': '100000.00000000', 'stepSize': '0.00100000'},
#         {'filterType': 'MIN_NOTIONAL', 'minNotional': '0.00010000', 'applyToMarket': True, 'avgPriceMins': 5},
#         {'filterType': 'ICEBERG_PARTS', 'limit': 10},
#         {'filterType': 'MARKET_LOT_SIZE', 'minQty': '0.00000000', 'maxQty': '2729.13846842', 'stepSize': '0.00000000'},
#         {'filterType': 'MAX_NUM_ORDERS', 'maxNumOrders': 200},
#         {'filterType': 'MAX_NUM_ALGO_ORDERS', 'maxNumAlgoOrders': 5}], 'permissions': ['SPOT', 'MARGIN']}
