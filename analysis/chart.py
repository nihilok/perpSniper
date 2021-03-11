import base64
import datetime
import io
import os
import sys

import matplotlib

matplotlib.use('agg')

import mplfinance as mpf
import pandas as pd
import pandas_ta as ta

from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

from matplotlib import pyplot as plt

from coin_data import CoinData

plt.style.use('dark_background')
import numpy as np
import numba as nb
import csv

from binance.client import Client

client = Client(os.getenv('bbot_pub'), os.getenv('bbot_sec'))

data_dict = {}

def read_data():
    with open('recent_trades.csv', newline='') as f:
        trade_reader = csv.reader(f, delimiter=' ', quotechar='|')
        for row in trade_reader:
            if row:
                # print()
                if row[1] not in data_dict.keys():
                    data_dict[row[1]] = [[row[0]] + row[2:]]
                else:
                    data_dict[row[1]].append([row[0]] + row[2:])
    return data_dict


@nb.jit(fastmath=True, nopython=True)
def calc_rsi( array, deltas, avg_gain, avg_loss, n ):

    # Use Wilder smoothing method
    up   = lambda x:  x if x > 0 else 0
    down = lambda x: -x if x < 0 else 0
    i = n+1
    for d in deltas[n+1:]:
        avg_gain = ((avg_gain * (n-1)) + up(d)) / n
        avg_loss = ((avg_loss * (n-1)) + down(d)) / n
        if avg_loss != 0:
            rs = avg_gain / avg_loss
            array[i] = 100 - (100 / (1 + rs))
        else:
            array[i] = 100
        i += 1

    return array

def get_rsi( array, n = 14 ):

    deltas = np.append([0],np.diff(array))

    avg_gain =  np.sum(deltas[1:n+1].clip(min=0)) / n
    avg_loss = -np.sum(deltas[1:n+1].clip(max=0)) / n

    array = np.empty(deltas.shape[0])
    array.fill(np.nan)

    array = calc_rsi( array, deltas, avg_gain, avg_loss, n )
    return array

class Charts:

    def __init__(self, symbol='BTCUSDT', tf='1h', entry=None, direction=None):
        """When initialised, creates chart for given symbol and timeframe
        :param symbol: str uppercase eg. 'BTCUSDT'
        :param tf: str lowercase eg. '1m', '15m', '1h', '4h'
        :param entry: float if open positions
        :param direction: str 'LONG', 'SHORT' or None depending on position"""
        self.symbol = symbol.upper()
        self.tf = tf
        self.df = CoinData.get_dataframe(self.symbol, self.tf)
        self.df = self.df_ta()
        self.entry = entry
        self.direction = True if direction == 'LONG' else False
        self.tp = 0.03
        self.sl = 0.01

    def df_ta(self) -> pd.DataFrame:
        df = self.df
        # df['rsi'] = ta.rsi(df.close, 14)
        df['rsi'] = get_rsi(df.close, 14)
        df = pd.concat((df, ta.macd(df.close, 12, 26, 9)), axis=1)
        df['ema_20'], df['ema_50'] = ta.ema(df.close, 20), ta.ema(df.close, 50)
        if len(df) >= 288:
            df['ema_200'] = ta.ema(df.close, 200)
        else:
            df['ema_200'] = ta.ema(df.close, len(df.close) - 3)
        df = df.tail(88)
        return df

    def trades_series(self, symbol):
        d = read_data()
        for key in d.keys():
            if key == symbol:
                trades = [{'datetime': datetime.datetime.strptime(d[symbol][i][0], "%Y-%m-%d %H:%M:%S.%f"), 'price': d[symbol][i][2]} for i in range(len(d[symbol]))]
                df = pd.DataFrame(trades)
                df.set_index('datetime', inplace=True)
                df.rename_axis('date', inplace=True)
                return df

    @staticmethod
    def get_rsi_timeseries(prices, n=14):
        # RSI = 100 - (100 / (1 + RS))
        # where RS = (Wilder-smoothed n-period average of gains / Wilder-smoothed n-period average of -losses)
        # Note that losses above should be positive values
        # Wilder-smoothing = ((previous smoothed avg * (n-1)) + current value to average) / n
        # For the very first "previous smoothed avg" (aka the seed value), we start with a straight average.
        # Therefore, our first RSI value will be for the n+2nd period:
        #     0: first delta is nan
        #     1:
        #     ...
        #     n: lookback period for first Wilder smoothing seed value
        #     n+1: first RSI

        # First, calculate the gain or loss from one price to the next. The first value is nan so replace with 0.
        deltas = (prices - prices.shift(1)).fillna(0)

        # Calculate the straight average seed values.
        # The first delta is always zero, so we will use a slice of the first n deltas starting at 1,
        # and filter only deltas > 0 to get gains and deltas < 0 to get losses
        avg_of_gains = deltas[1:n + 1][deltas > 0].sum() / n
        avg_of_losses = -deltas[1:n + 1][deltas < 0].sum() / n

        # Set up pd.Series container for RSI values
        rsi_series = pd.Series(0.0, deltas.index)

        # Now calculate RSI using the Wilder smoothing method, starting with n+1 delta.
        up = lambda x: x if x > 0 else 0
        down = lambda x: -x if x < 0 else 0
        i = n + 1
        for d in deltas[n + 1:]:
            avg_of_gains = ((avg_of_gains * (n - 1)) + up(d)) / n
            avg_of_losses = ((avg_of_losses * (n - 1)) + down(d)) / n
            if avg_of_losses != 0:
                rs = avg_of_gains / avg_of_losses
                rsi_series[i] = 100 - (100 / (1 + rs))
            else:
                rsi_series[i] = 100
            i += 1

        return rsi_series


    def main_chart(self):
        fig, axes = plt.subplots(nrows=3, ncols=1, gridspec_kw={'height_ratios': [3, 1, 1]})
        fig.suptitle(f"{self.symbol} {self.tf}", fontsize=16)
        ax_r = axes[0].twinx()
        mc = mpf.make_marketcolors(up='#00e600', down='#ff0066',
                                   edge={'up': '#00e600', 'down': '#ff0066'},
                                   wick={'up': '#00e600', 'down': '#ff0066'},
                                   volume={'up': '#808080', 'down': '#4d4d4d'},
                                   ohlc='black')
        s = mpf.make_mpf_style(marketcolors=mc)
        ax_r.set_alpha(0.01)
        axes[0].set_zorder(2)
        for ax in axes:
            ax.set_facecolor((0, 0, 0, 0))
        ax_r.set_zorder(1)

        axes[1].set_ylabel('RSI')
        axes[1].margins(x=0, y=0.1)
        axes[0].margins(x=0, y=0.05)
        axes[2].set_ylabel('MACD')
        ax_r.set_ylabel('')
        ax_r.yaxis.set_visible(False)
        axes[2].margins(0, 0.05)
        axes[0].xaxis.set_visible(False)
        axes[1].xaxis.set_visible(False)

        axes[0].yaxis.tick_left()
        axes[0].yaxis.set_label_position('right')
        axes[1].yaxis.set_label_position('right')
        axes[2].yaxis.set_label_position('right')
        plt.tight_layout()
        fig.autofmt_xdate()
        self.df.volume = self.df.volume.div(2)
        addplot_200 = mpf.make_addplot(self.df['ema_200'], type='line', ax=axes[0], width=1, color='#ff0066')
        addplot_50 = mpf.make_addplot(self.df['ema_50'], type='line', ax=axes[0], width=1, color='#00e600')
        addplot_trades = mpf.make_addplot(self.trades_series(self.symbol), type='scatter', ax=axes[0], width=5, color='#fff')
        mpf.plot(self.df, ax=axes[0], type="candle", style=s, volume=ax_r, ylabel='', addplot=[addplot_200, addplot_50])
        max_vol = max({y for index, y in self.df.volume.items()})
        ax_r.axis(ymin=0, ymax=max_vol * 3)
        self.df['rsi'].plot(ax=axes[1], legend=False, use_index=True, sharex=axes[0], color='#00e600')
        self.df['MACD_12_26_9'].plot(ax=axes[2], legend=False, use_index=True, sharex=axes[0], color='#00e600')
        self.df['MACDs_12_26_9'].plot(ax=axes[2], legend=False, use_index=True, sharex=axes[0], color='#ff0066')
        axes[2].axhline(0, color='gray', ls='--', linewidth=1)
        axes[1].axhline(70, color='gray', ls='--', linewidth=1)
        axes[1].axhline(30, color='gray', ls='--', linewidth=1)
        if self.entry:
            tp = self.entry + self.entry * self.tp if self.direction else self.entry - self.entry * self.tp
            sl = self.entry - self.entry * self.sl if self.direction else self.entry + self.entry * self.sl
            tp_color = 'red' if self.direction else 'green'
            sl_color = 'red' if not self.direction else 'green'
            axes[0].axhline(self.entry, color='yellow', ls="--", linewidth=.5)
            axes[0].axhline(tp, color=tp_color, ls="--", linewidth=.5)
            axes[0].axhline(sl, color=sl_color, ls="--", linewidth=.5)
        axes[2].set_xlabel('')
        img = io.BytesIO()
        FigureCanvas(fig).print_png(img)
        plot_url = base64.b64encode(img.getvalue()).decode()
        fig.savefig('plot.png', format='png')
        plt.close(fig)
        return plot_url

    # def plot_rsi_div(self):
    #     rsi_array = np.array(self.df['rsi'].tail(20).array)
    #     close_array = np.array(self.df['close'].tail(20).array)
    #     rsi_peaks, _ = scipy.signal.find_peaks(rsi_array)
    #     rsi_troughs, _ = scipy.signal.find_peaks(-rsi_array)
    #     fig, (ax1, ax2) = plt.subplots(2, sharex=True)
    #     fig.suptitle(f'{self.symbol} RSI Divergence {self.tf}')
    #     ax1.set_ylabel('Close')
    #     ax2.set_ylabel('RSI')
    #     ax2.axhline(70, color='gray', ls='--')
    #     ax2.axhline(30, color='gray', ls='--')
    #     ax1.xaxis.set_visible(False)
    #     ax2.xaxis.set_visible(False)
    #     ax1.plot(close_array)
    #     ax2.plot(rsi_array, color='green')
    #     ax1.plot(rsi_peaks, close_array[rsi_peaks], '.', color="#ff0066")
    #     ax2.plot(rsi_peaks, rsi_array[rsi_peaks], '.', color="#ff0066")
    #     ax1.plot(rsi_troughs, close_array[rsi_troughs], '.', color="#00e600")
    #     ax2.plot(rsi_troughs, rsi_array[rsi_troughs], '.', color="#00e600")
    #     _, new_close_array, new_rsi_array, indices = self.rsi_divergence()
    #     if len(close_array) != len(new_close_array):
    #         ax1.plot(indices, new_close_array, color="#ff0066")
    #         ax2.plot(indices, new_rsi_array, color="#ff0066")
    #     img = io.BytesIO()
    #     fig.savefig(img, format='png')
    #     img.seek(0)
    #     plot_url = base64.b64encode(img.getvalue()).decode()
    #     plt.close()
    #     return plot_url

    def plot_charts(self):
        self.main_chart()
        # self.plot_rsi_div()


if __name__ == '__main__':
    c = Charts('SNXUSDT', '15m')
    print('plotting charts')
    c.plot_charts()
    print('done')
    sys.exit()
    # print(Charts('SNXUSDT', '15m').trades_series('SNXUSDT'))
