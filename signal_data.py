import os
import asyncio
from datetime import datetime

import aiohttp
import nest_asyncio
import sqlite3
import pandas as pd
import pandas_ta as ta
import numpy as np
import scipy.signal
from binance.websockets import BinanceSocketManager
from twisted.internet import reactor

from trader import Trader
from utils import get_popular_coins
nest_asyncio.apply()

file_path = os.path.abspath(os.path.dirname(__file__))
os.chdir(file_path)

client = Trader().client
loop = asyncio.get_event_loop()

TIME_FRAMES = ['15m', '1h', '4h']


class SymbolData:
    """Start websocket for live klines and get historical klines that don't exist"""


class SignalData:

    @classmethod
    async def return_dataframes(cls, symbol, event_loop):
        """Get complete dataframes for given symbol with signals data for all given timeframes
        Main method for initial data preparation"""
        return await cls.add_ta_data(await cls.get_original_data(symbol), event_loop)
        # return await cls.get_original_data(symbol)

    @classmethod
    async def get_original_data(cls, symbol):
        """Load price data from the database
        This has to happen first"""
        conn = sqlite3.connect('symbols.db')
        dfs = []
        for tf in TIME_FRAMES:
            query = f'SELECT * from {symbol}_{tf}'
            df = pd.read_sql_query(query, conn)
            dfs.append(df)
        conn.close()
        return dfs

    @classmethod
    async def add_ta_data(cls, dfs, event_loop):
        """Create columns for RSI, MACD(m/s/h), EMAs(20/50/200), Heiken Ashi
        These can all be run as coroutine tasks"""
        coroutines = [[],[],[]]
        for i, df in enumerate(dfs):
            coroutines[i].append(cls.get_rsi(df))
            coroutines[i].append(cls.get_macd(df))
            coroutines[i].append(cls.get_emas(df))
            coroutines[i].append(cls.get_heiken_ashi(df))
        # run coroutines with event loop and get return VALUES
        sep_dfs = event_loop.run_until_complete(asyncio.gather(*coroutines))
        comp_dfs = []
        for t in sep_dfs:
            df = pd.concat([t[i] for i in range(len(t))], axis=1)
            comp_dfs.append(df)
        # return return values
        return comp_dfs

    @classmethod
    async def get_rsi(cls, df):
        return ta.rsi(df.close, 14)

    @classmethod
    async def get_macd(cls, df):
        return ta.macd(df.close, 12, 26, 9)

    @classmethod
    async def get_emas(cls, df):
        df['ema_20'], df['ema_50'] = ta.ema(df.close, 20), ta.ema(df.close, 50)
        if len(df) >= 288:
            df['ema_200'] = ta.ema(df.close, 200)
        else:
            df['ema_200'] = ta.ema(df.close, len(df.close) - 3)
        df = df.tail(88)
        return df[['ema_20', 'ema_50', 'ema_200']]

    @classmethod
    async def get_heiken_ashi(cls, df):
        df['HA_Close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
        idx = df.index.name
        df.reset_index(inplace=True)

        for i in range(0, len(df)):
            if i == 0:
                df.at[i, 'HA_Open'] = ((df._get_value(i, 'open') + df._get_value(i, 'close')) / 2)
            else:
                df.at[i, 'HA_Open'] = ((df._get_value(i - 1, 'HA_Open') + df._get_value(i - 1, 'HA_Close')) / 2)

        if idx:
            df.set_index(idx, inplace=True)

        df['HA_High'] = df[['HA_Open', 'HA_Close', 'high']].max(axis=1)
        df['HA_Low'] = df[['HA_Open', 'HA_Close', 'low']].min(axis=1)

        return df[['HA_Open', 'HA_High', 'HA_Low', 'HA_Close']]

    @classmethod
    async def check_df(cls, df, event_loop):
        coroutines = [cls.check_rsi(df), cls.check_macd(df), cls.check_heiken_ashi(df)]
        results = event_loop.run_until_complete(asyncio.gather(*coroutines))
        return results

    @classmethod
    async def check_rsi(cls, df):
        # await asyncio.sleep(2)
        print('checked rsi')
        return 'RSI'

    @classmethod
    async def check_macd(cls, df):
        # await asyncio.sleep(1)
        print('checked macd')
        return False, True

    @classmethod
    async def check_heiken_ashi(cls, df):
        # await asyncio.sleep(2)
        print('checked ha')
        return 'HA'

    @classmethod
    async def main(cls, symbol, event_loop):
        start_time = datetime.now()
        dfs = await cls.return_dataframes(symbol, event_loop)
        coroutines = [cls.check_df(dfs[i], event_loop) for i in range(len(dfs))]
        results = event_loop.run_until_complete(asyncio.gather(*coroutines))
        print(f'took: ' + str(datetime.now() - start_time))
        return results


if __name__ == '__main__':
    start_time = datetime.now()
    for s in get_popular_coins():
        print(asyncio.run(SignalData.main(s, loop)))
    loop.close()
    print(f'took: ' + str(datetime.now() - start_time))
