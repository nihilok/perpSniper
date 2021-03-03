import os
import asyncio
import aiohttp
import sqlite3
import pandas as pd
import numpy as np
import scipy.signal
from binance.websockets import BinanceSocketManager
from twisted.internet import reactor

from trader import Trader


file_path = os.path.abspath(os.path.dirname(__file__))
os.chdir(file_path)


class SignalData:

    client = Trader().client
    loop = asyncio.get_event_loop()

    @classmethod
    async def return_dataframe(cls, symbol, timeframe):
        """Get complete dataframe for given symbol with signals data"""

    @classmethod
    async def get_original_data(cls, symbol, timeframe):
        """Load price data from the database"""

    @classmethod
    async def add_ta_data(cls, df):
        """Create columns for RSI, MACD(m/s/h), EMAs(20/50/200), Heiken Ashi"""
