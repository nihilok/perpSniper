import os
import pandas as pd
import pandas_ta as ta
import numpy as np
import scipy.signal
from trader import Trader
from coin_data import CoinData

client = Trader().client
file_path = os.path.abspath(os.path.dirname(__file__))
os.chdir(file_path)


class Signals:

    def __init__(self, symbol='BTCUSDT', tf='4h'):

        """Check for signals for given symbol and timeframe"""

        self.symbol = symbol.upper()
        self.tf = tf
        self.df = CoinData.get_dataframe(symbol, tf)
        self.df = self.df_ta()
        self.vol_signal = self.vol_rise_fall()
        self.vol_candle = self.large_vol_candle()
        self.rsi_ob_os_dict = {
            'overbought': False,
            'oversold': False,
        }
        self.rsi_overbought_oversold()
        self.rsi_div_dict = {
            'possible bearish divergence': False,
            'possible bullish divergence': False,
            'confirmed bearish divergence': False,
            'confirmed bullish divergence': False,
        }
        self.rsi_divergence()
        self.macd_dict = {
            'MACD cross': None,
            'MACD 0 cross': None,
        }
        self.macd_signals()
        self.ema_signals_dict = {
            'Price crossing EMA200': None,
            'EMA20 crossing EMA50': None,
            'EMA50 crossing EMA200': None,
        }
        self.ema_signals()

    def full_check(self):
        self.rsi_divergence()
        self.ema_signals()
        self.macd_signals()
        self.rsi_overbought_oversold()
        self.vol_rise_fall()
        self.large_vol_candle()

    def df_ta(self) -> pd.DataFrame:
        df = self.df
        df['rsi'] = ta.rsi(df.close, 14)
        df = pd.concat((df, ta.macd(df.close, 12, 26, 9)), axis=1)
        df['ema_20'], df['ema_50'] = ta.ema(df.close, 20), ta.ema(df.close, 50)
        if len(df) >= 288:
            df['ema_200'] = ta.ema(df.close, 200)
        else:
            df['ema_200'] = ta.ema(df.close, len(df.close) - 3)
        df = df.tail(88)
        return df

    def rsi_divergence(self):
        rsi_array = np.array(self.df['rsi'].tail(20).array)
        close_array = np.array(self.df['close'].tail(20).array)
        rsi_peaks, _ = scipy.signal.find_peaks(rsi_array)
        rsi_troughs, _ = scipy.signal.find_peaks(-rsi_array)
        original_index = len(close_array)
        indices = np.array([])

        # bearish divergence confirmed: rsi formed lower peak while price formed higher peak
        if rsi_array[rsi_peaks[-2]] >= rsi_array[rsi_peaks[-1]] >= rsi_array[-1]:
            if close_array[rsi_peaks[-2]] <= close_array[rsi_peaks[-1]]:
                close_array = np.array([close_array[rsi_peaks[-2]], close_array[rsi_peaks[-1]]])
                rsi_array = np.array([rsi_array[rsi_peaks[-2]], rsi_array[rsi_peaks[-1]]])
                indices = np.array([rsi_peaks[-2], rsi_peaks[-1]])
                self.rsi_div_dict['confirmed bearish divergence'] = True

        # possible bearish divergence: rsi forming lower peak while price forming higher peak
        elif rsi_array[rsi_peaks[-1]] >= rsi_array[-1]:
            if close_array[rsi_peaks[-1]] <= close_array[-1]:
                close_array = np.array([close_array[rsi_peaks[-1]], close_array[-1]])
                rsi_array = np.array([rsi_array[rsi_peaks[-1]], rsi_array[-1]])
                indices = np.array([rsi_peaks[-1], original_index])
                self.rsi_div_dict['possible bearish divergence'] = True

        # bullish divergence confirmed: rsi formed higher trough while price formed lower trough
        elif rsi_array[rsi_troughs[-2]] <= rsi_array[rsi_troughs[-1]] <= rsi_array[-1]:
            if close_array[rsi_troughs[-2]] >= close_array[rsi_troughs[-1]]:
                close_array = np.array([close_array[rsi_troughs[-2]], close_array[rsi_troughs[-1]]])
                rsi_array = np.array([rsi_array[rsi_troughs[-2]], rsi_array[rsi_troughs[-1]]])
                indices = np.array([rsi_troughs[-2], rsi_troughs[-1]])
                self.rsi_div_dict['confirmed bullish divergence'] = True

        # possible bullish divergence: rsi forming higher trough while price forming lower trough
        elif rsi_array[rsi_troughs[-1]] <= rsi_array[-1]:
            if close_array[rsi_troughs[-1]] >= close_array[-1]:
                close_array = np.array([close_array[rsi_troughs[-1]], close_array[-1]])
                rsi_array = np.array([rsi_array[rsi_troughs[-1]], rsi_array[-1]])
                indices = np.array([rsi_troughs[-1], original_index])
                self.rsi_div_dict['possible bullish divergence'] = True

        return self.rsi_div_dict, close_array, rsi_array, indices

    def rsi_overbought_oversold(self, o_s=30, o_b=70):
        rsi_array = self.df['rsi'].array
        if rsi_array[-1] > o_s > rsi_array[-2]:
            self.rsi_ob_os_dict['oversold'] = True
        elif rsi_array[-1] < o_b < rsi_array[-2]:
            self.rsi_ob_os_dict['overbought'] = True
        return self.rsi_ob_os_dict

    def macd_signals(self):
        if self.df['MACD_12_26_9'].array[-1] > self.df['MACDs_12_26_9'].array[-1]:
            if self.df['MACD_12_26_9'].array[-2] < self.df['MACDs_12_26_9'].array[-2]:
                self.macd_dict['MACD cross'] = True
        elif self.df['MACD_12_26_9'].array[-1] < self.df['MACDs_12_26_9'].array[-1]:
            if self.df['MACD_12_26_9'].array[-2] > self.df['MACDs_12_26_9'].array[-2]:
                self.macd_dict['MACD cross'] = False
        if (self.df['MACD_12_26_9'].array[-1], self.df['MACDs_12_26_9'].array[-1]) > (0, 0):
            if (self.df['MACD_12_26_9'].array[-2], self.df['MACDs_12_26_9'].array[-2]) <= (0, 0):
                self.macd_dict['MACD 0 cross'] = True
        elif (self.df['MACD_12_26_9'].array[-1], self.df['MACDs_12_26_9'].array[-1]) < (0, 0):
            if (self.df['MACD_12_26_9'].array[-2], self.df['MACDs_12_26_9'].array[-2]) >= (0, 0):
                self.macd_dict['MACD 0 cross'] = False

    def ema_signals(self):
        ema_200 = self.df['ema_200'].array[-3:]
        ema_50 = self.df['ema_50'].array[-3:]
        ema_20 = self.df['ema_20'].array[-3:]
        price = self.df['close'].array[-3:]
        if ema_200[0] > price[0] and ema_200[1] >= price[1] and ema_200[2] < price[2]:
            self.ema_signals_dict['Price crossing EMA200'] = True
        elif ema_200[0] < price[0] and ema_200[1] <= price[1] and ema_200[2] > price[2]:
            self.ema_signals_dict['Price crossing EMA200'] = False
        if ema_20[0] > ema_50[0] and ema_20[1] >= ema_50[1] and ema_20[2] < ema_50[2]:
            self.ema_signals_dict['EMA20 crossing EMA50'] = False
        elif ema_20[0] < ema_50[0] and ema_20[1] <= ema_50[1] and ema_20[2] > ema_50[2]:
            self.ema_signals_dict['EMA20 crossing EMA50'] = True
        if ema_50[0] > ema_200[0] and ema_50[1] >= ema_200[1] and ema_50[2] < ema_200[2]:
            self.ema_signals_dict['EMA50 crossing EMA200'] = False
        elif ema_50[0] < ema_200[0] and ema_50[1] <= ema_200[1] and ema_50[2] > ema_200[2]:
            self.ema_signals_dict['EMA50 crossing EMA200'] = True
        return self.ema_signals_dict

    def vol_rise_fall(self):
        recent_vol = self.df.volume.tail(3).array
        self.vol_signal = True if recent_vol[0] < recent_vol[1] < recent_vol[2] else False
        return self.vol_signal

    def large_vol_candle(self):
        self.vol_candle = True if self.df.volume.array[-1] >= self.df.volume.tail(14).values.mean()*2 else False
        return self.vol_candle

if __name__ == '__main__':
    sig = Signals('ADAUSDT')