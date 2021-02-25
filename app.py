import datetime
import json
import os
from threading import Thread
import logging
from flask import Flask, redirect, url_for, render_template, request, session, jsonify, make_response
import sqlite3

import trader
from charts import Charts
from thread_manager import ThreadManager

file_path = os.path.abspath(os.path.dirname(__file__))
os.chdir(file_path)

logger = logging.getLogger(__name__)
logging.basicConfig(filename='log.log')

app = Flask('PerpSniper')
tr = None
thread_manager = None


def start_signals(*args):
    global tr
    global thread_manager
    try:
        with open('log.log', 'r') as f:
            lines = f.readlines()
        if len(lines) >= 88:
            with open('log.log', 'w') as f:
                f.writelines(lines[-88:])
    except FileNotFoundError:
        print('No log file to flush')
    thread_manager = ThreadManager()
    tr = thread_manager.trader


def tear_down():
    thread_manager.teardown()
    print('app teardown completed')


@app.route('/')
def quick_trade():
    return render_template('quicktrade.html', title='PerpSniper v0.2')

@app.route('/old')
def home():
    return render_template('index.html', title='PerpSniper v0.2')


@app.route('/api/signals', methods=['GET'])
def signals_api():
    conn = sqlite3.connect('signals.db')
    c = conn.cursor()
    qs = c.execute('SELECT * FROM signals')
    recent_sigs = list(reversed([alert for alert in qs]))
    conn.close()
    data = {
        'signals': [],
    }
    for sig in recent_sigs:
        sig_dict = {
            'time': sig[0],
            'symbol': sig[1],
            'alert': sig[2],
        }
        data['signals'].append(sig_dict)
    response = make_response(jsonify(data))
    return response


def long_thread(coin):
    t = tr.trade(coin, True)


@app.route('/api/long', methods=['POST'])
def long_api():
    try:
        coin = request.get_json()['coin']
        t = Thread(target=long_thread, args=(coin,))
        t.setDaemon(True)
        t.start()
        message = f'Opened long on {coin}'
        data = {'message': message}
        response = make_response(jsonify(data))
    except KeyError:
        return 'Failure', 500
    return response, 200


def short_thread(coin):
    t = tr.trade(coin, False)


@app.route('/api/short', methods=['POST'])
def short_api():
    try:
        coin = request.get_json()['coin']
        t = Thread(target=short_thread, args=(coin,))
        t.setDaemon(True)
        t.start()
        message = f'Opened short on {coin}'
        data = {'message': message}
        response = make_response(jsonify(data))
    except Exception as e:
        return e, 500
    return response, 200


@app.route('/wave')
def wave_trade():
    return render_template('wavetrade.html', title='PerpSniper WaveTrade')


@app.route('/api/positions')
def positions_api():
    positions = tr.return_open_positions()
    data = {'positions':positions}
    response = make_response(jsonify(data))
    return response, 200


@app.route('/api/account')
def account_api():
    account = tr.get_account_info()
    response = make_response(jsonify(account))
    return response, 200


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    global tr
    if request.method == 'GET':
        with open('settings.json', 'r') as f:
            settings_dict = json.load(f)
        return render_template('settings.html', settings=settings_dict)
    else:
        tp = float(request.form['TP'])/100
        sl = float(request.form['SL'])/100
        db = float(request.form['DB'])
        qty = float(request.form['QTY'])/100
        with open('settings.json', 'r') as f:
            settings_dict = json.load(f)
        if tp:
            settings_dict['tp'] = tp
        if sl:
            settings_dict['sl'] = sl
        if db:
            settings_dict['db'] = db
        if qty:
            settings_dict['qty'] = qty
        with open('settings.json', 'w') as f:
            json.dump(settings_dict, f, indent=4)
        if any({tp, sl, db, qty}):
            tr = trader.Trader()
        return redirect(url_for('quick_trade'))


def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()

@app.route('/shutdown', methods=['POST'])
def shutdown():
    shutdown_server()
    return 'Server shutting down...'


@app.route('/api/close_old_orders')
def close_old_orders():
    tr.check_positions_cancel_open_orders()
    return 'Success', 200


@app.route('/api/close_position', methods=['POST'])
def close_position():
    try:
        coin = request.get_json()['coin']
        tr.close_position(coin)
        return 'Success', 200
    except Exception as e:
        print(e)
        return f'Failure: {e}', 500


@app.route('/api/close_all_positions', methods=['POST'])
def close_all_positions():
    try:
        tr.close_all_positions()
        response = make_response(jsonify({'message': 'Positions closed'}))
        return response, 200
    except Exception as e:
        print(e)
        return f'Failure: {e}', 500


@app.route('/plot', methods=['POST'])
def build_plot():
    try:
        req_json = request.get_json()
        symbol = req_json['symbol']
        tf = req_json['interval']
        positions = tr.return_open_positions()
        entry = None
        direction = None
        if positions:
            symbols = [p['symbol'] for p in positions]
            if symbol in symbols:
                entry = positions[symbols.index(symbol)]['entry']
                direction = positions[symbols.index(symbol)]['direction']
        plot_url = Charts(symbol, tf, entry, direction).main_chart()
        response = make_response(jsonify({'plot_url': '<img src="data:image/png;base64,{}">'.format(plot_url),
                                          'base64': 'data:image/png;base64,{}'.format(plot_url)}))
        return response, 200
        # return 'Success', 200
    except Exception as error:
        print(error)
        return 'Failure', 500

@app.route('/server_time')
def server_time():
    time = tr.return_server_time()
    response = make_response(jsonify({'serverTime': datetime.datetime.fromtimestamp(time).strftime('%H:%M:%S')}))
    return response, 200



if __name__ == '__main__':
    start_signals()
    app.run(host='0.0.0.0', port=9000, use_reloader=False, debug=True)
