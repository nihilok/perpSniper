function loadUrl(newLocation){
  window.location = newLocation;
  return false;
}

function getRecentAlerts(){
  var table = document.getElementById('recent_alerts_table')
  var thead = document.getElementById('recent_alerts')
//  var hotCoins = document.getElementById('hot_coins')
  fetch(`${window.origin}/api/signals`)
  .then(function(response){
    if (response.status !== 200) {
      displayMessage(`Bad response from api: ${response.status}`)
      return ;
    }
    response.json().then(function(data){
      var alertRows = document.getElementsByClassName('alert_row')
      thead.innerHTML = '';
      data.signals.sort(function(a,b){
        var c = new Date(a.date);
        var d = new Date(b.date);
        return c-d;
        });
      data.signals.reverse();
      for (i = 0; i < data.signals.length; i++) {
        var row = thead.insertRow(0);
        row.classList.add('alert_row')
        var words = data.signals[i].alert.split(' ');
        var bullish = ['up', 'bullish', 'oversold']
        var bearish = ['down', 'bearish', 'overbought']
        for (j = 0; j < words.length; j++) {
          for (k = 0; k < bullish.length; k++) {
            if (words[j] == bullish[k]) {
              row.classList.add('text-green-500')
            } 
          }
          for (k = 0; k < bearish.length; k++) {
            if (words[j] == bearish[k]) {
              row.classList.add('text-red-500')
            } 
          }
        }
        var cell1 = row.insertCell(0);
        var cell2 = row.insertCell(1);
        var cell3 = row.insertCell(2);
        cell1.innerHTML = data.signals[i].time;
        cell2.innerHTML = data.signals[i].symbol;
        cell2.classList.add('font-bold')
        cell2.addEventListener('click', changeChart, false);
        cell3.innerHTML = data.signals[i].alert;
      }
//      hot_coins.innerHTML = ''
//      for (i = 0; i < data.hot_coins.length; i++) {
//        var entry = document.createElement('li')
//        entry.innerHTML = `${data.hot_coins[i][0]} (${data.hot_coins[i][1]} alerts)`
//        hotCoins.appendChild(entry)
//      }
    return ;
    })
  })
}


function openLong() {
  var coin = document.getElementById('coinInput')
  fetch(`${window.origin}/api/long`, {
    method: 'post',
    headers: {
      'Content-Type': 'application/json'
      // 'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: JSON.stringify({coin: coinInput.value}),
    })
  .then(function(response){
    if (response.status !== 200) {
      displayMessage(`Bad response from api: ${response.status}`)
      return ;
    }
    else {displayMessage(`Opened LONG on: ${coin.value}`)}
  })
}


function openShort() {
  var coin = document.getElementById('coinInput')
  fetch(`${window.origin}/api/short`, {
    method: 'post',
    headers: {
      'Content-Type': 'application/json'
      // 'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: JSON.stringify({coin: coinInput.value}),
    })
  .then(function(response){
    if (response.status !== 200) {
      displayMessage(`Bad response from api: ${response.status}`)
      return ;
    }
    else {displayMessage(`Opened SHORT on: ${coin.value}`)}
  })
}

function openQuickShort(coin) {
  fetch(`${window.origin}/api/short`, {
    method: 'post',
    headers: {
      'Content-Type': 'application/json'
      // 'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: JSON.stringify({coin: coin}),
    })
  .then(function(response){
    if (response.status !== 200) {
      displayMessage(`Bad response from api: ${response.status}`)
      return ;
    }
    else {
        response.json().then(function(data) {
            if (data.message) {
                displayMessage(data.message)
            }
        })
    }
  })
}

function testMessage() {
    displayMessage('Hello World');
}

function openQuickLong(coin) {
  fetch(`${window.origin}/api/long`, {
    method: 'post',
    headers: {
      'Content-Type': 'application/json'
      // 'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: JSON.stringify({coin: coin}),
    })
  .then(function(response){
    if (response.status !== 200) {
      displayMessage(`Bad response from api: ${response.status}`)
      return ;
    }
    else {
        response.json().then(function(data) {
            if (data.message) {
                displayMessage(data.message)
            }
        })
    }
  })
}

function shutDown() {
  fetch(`${window.origin}/shutdown`, {
    method: 'post'})
}

function getPositions() {
  fetch(`${window.origin}/api/positions`)
  .then(function(response){
    if (response.status !== 200) {
      displayMessage(`Bad response from api: ${response.status}`)
      return ;
    }
    response.json().then(function(data){
      var tBody = document.getElementById('tBody')
      tBody.innerHTML = ''
      for (i = 0; i < data.positions.length; i++) {
        var row = tBody.insertRow(0);
//        row.classList.add('')
        var cell1 = row.insertCell(0);
        var cell2 = row.insertCell(1);
        var cell3 = row.insertCell(2);
        var cell4 = row.insertCell(3);
        var cell5 = row.insertCell(4);
        cell1.innerHTML = data.positions[i].symbol;
        cell1.addEventListener('click', changeChart, false);
        cell2.innerHTML = data.positions[i].direction;
        cell3.innerHTML = data.positions[i].qty;
        cell4.innerHTML = '$' + data.positions[i].pnl.toFixed(2);
        cell5.innerHTML = data.positions[i].roe.toFixed(2) +'%';
      }
    })
  })
}

function getBalance() {
  fetch(`${window.origin}/api/account`)
  .then(function(response){
    if (response.status !== 200) {
      displayMessage(`Bad response from api: ${response.status}`)
      return ;
    }
    response.json().then(function(data){
        var tBody = document.getElementById('accountTBody')
        var balance = document.getElementById('balance')
        var pnl = document.getElementById('pnl')
        balance.innerHTML = 'Balance: $' + parseFloat(data.balance).toFixed(2);
        pnl.innerHTML = 'PNL: $' + parseFloat(data.total_pnl).toFixed(2);
        // tBody.innerHTML = ''
        // var row = tBody.insertRow(0);
        // row.classList.add('text-left')
        // var cell1 = row.insertCell(0);
        // var cell2 = row.insertCell(1);
        // var cell3 = row.insertCell(2);
        // cell1.innerHTML = '$' + parseFloat(data.balance).toFixed(2);
        // cell2.innerHTML = '$' + parseFloat(data.total_pnl).toFixed(2);
        // cell3.innerHTML = '$' + parseFloat(data.margin_balance).toFixed(2);
    })
  })
}

function closeOldOrders(){
  fetch(`${window.origin}/api/positions`)
  .then(function(response){
    if (response.status !== 200) {
      displayMessage(`Bad response from api: ${response.status}`)
      return ;
    }
    else {
      displayMessage('Orders cleared')
    }
  })
}

var xDown = null;
var yDown = null;

function getTouches(evt) {
  return evt.touches ||             // browser API
         evt.originalEvent.touches; // jQuery
}

function handleTouchStart(evt) {
    const firstTouch = getTouches(evt)[0];
    xDown = firstTouch.clientX;
    yDown = firstTouch.clientY;
};

function handleTouchMove(evt) {
    if ( ! xDown || ! yDown ) {
        return;
    }

    var xUp = evt.touches[0].clientX;
    var yUp = evt.touches[0].clientY;

    var xDiff = xDown - xUp;
    var yDiff = yDown - yUp;

    var coinName = this.id
    var closeId = `${coinName}Close`


    if ( Math.abs( xDiff ) > Math.abs( yDiff ) ) {
        if ( xDiff > 0 ) {
            $(this).css({
              'animation': 'slideSwipeDrawerOpen .2s linear',
              '-webkit-transform' : 'translateX(' + -6 + 'rem)',
              '-moz-transform'    : 'translateX(' + -6 + 'rem)',
              '-ms-transform'     : 'translateX(' + -6 + 'rem)',
              '-o-transform'      : 'translateX(' + -6 + 'rem)',
              'transform'         : 'translateX(' + -6 + 'rem)'
            });
            document.getElementById(closeId).style.display = 'flex'

        } else {
            $(this).css({
              'animation': 'slideSwipeDrawerClose .2s linear',
              '-webkit-transform' : 'translateX(' + 0 + 'rem)',
              '-moz-transform'    : 'translateX(' + 0 + 'rem)',
              '-ms-transform'     : 'translateX(' + 0 + 'rem)',
              '-o-transform'      : 'translateX(' + 0 + 'rem)',
              'transform'         : 'translateX(' + 0 + 'rem)'
            });
            document.getElementById(closeId).style.display = 'none'
        }
    }
    /* reset values */
    xDown = null;
    yDown = null;
};

function handleRightClick(evt) {
  var coinName = this.id
  var closeId = `${coinName}Close`
  evt.preventDefault()
  if (this.getAttribute('data-open')) {
    document.getElementById(closeId).style.display = 'none'
    $(this).css({
              'animation': 'slideSwipeDrawerClose .2s linear',
              '-webkit-transform' : 'translateX(' + 0 + 'rem)',
              '-moz-transform'    : 'translateX(' + 0 + 'rem)',
              '-ms-transform'     : 'translateX(' + 0 + 'rem)',
              '-o-transform'      : 'translateX(' + 0 + 'rem)',
              'transform'         : 'translateX(' + 0 + 'rem)'
    });
    this.removeAttribute('data-open')
  }
  else {
    document.getElementById(closeId).style.display = 'flex'
    $(this).css({
              'animation': 'slideSwipeDrawerOpen .2s linear',
              '-webkit-transform' : 'translateX(' + -6 + 'rem)',
              '-moz-transform'    : 'translateX(' + -6 + 'rem)',
              '-ms-transform'     : 'translateX(' + -6 + 'rem)',
              '-o-transform'      : 'translateX(' + -6 + 'rem)',
              'transform'         : 'translateX(' + -6 + 'rem)'
    });
    this.setAttribute('data-open', true)
  }
}

function removeCoin(coin) {
  coin.parentNode.parentNode.parentNode.removeChild(coin.parentNode.parentNode);
}

function closeOpenPositions(coinCloseIcon) {
  var coin = coinCloseIcon.parentNode.parentNode.parentNode.id
  fetch(`${window.origin}/api/close_all`, {
      method: 'post',
      headers: {
        'Content-Type': 'application/json'
        // 'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: JSON.stringify({coin: coin}),
      })
  .then(function(response){
    if (response.status !== 200) {
      displayMessage(`Bad response from api: ${response.status}`)
      return ;
    }
    else {displayMessage(`Closed position: ${coin}`);}
  })
}

function closeOpenPosition(coinCloseIcon) {
  var coin = coinCloseIcon.parentNode.parentNode.parentNode.id
  fetch(`${window.origin}/api/close_position`, {
      method: 'post',
      headers: {
        'Content-Type': 'application/json'
        // 'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: JSON.stringify({coin: coin}),
      })
  .then(function(response){
    if (response.status !== 200) {
      displayMessage(`Bad response from api: ${response.status}`)
      return ;
    }
    else {displayMessage(`Closed position: ${coin}`);}
  })
}

function apiPostRequest(endpoint, data, responseSuccessFunc) {
  fetch(`${window.origin}/${endpoint}`, {
      method: 'post',
      headers: {
        'Content-Type': 'application/json'
        // 'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: JSON.stringify(data),
      })
  .then(function(response){
    if (response.status !== 200) {
      displayMessage(`Bad response from api: ${response.status}`)
      return ;
    }
    else {responseSuccessFunc(response)}
  })
}

function closeAllPositions() {
  var data = {}
  apiPostRequest('/api/close_all_positions', data, function(response) {displayMessage('Positions closed')})
}

function addCoin() {
  var quickTradeDiv = document.getElementById('quickTradeDiv')
  var coin = document.getElementById('coinInput')
  coin_value = coin.value
  coin.value = ''
  coin = coin_value.toUpperCase()
  coin += 'USDT'
//  var quickTradeComponent = document.createElement('div')
  var innerDiv = document.createElement('div')
  innerDiv.innerHTML = `<div class="flex flex-row justify-center items-center space-x-2"><div onclick="openQuickLong('${coin}')" class="flex items-center justify-center text-2xl text-white font-bold cursor-pointer bg-green-500 hover:bg-green-600 shadow-lg hover:shadow-sm rounded-xl h-16 w-24">LONG</div><div id="${coin}QuickTradeCoinText" class="flex flex-col items-center justify-center text-2xl text-white font-bold w-64 cursor-pointer">${coin}</div><div onclick="openQuickShort('${coin}')" class="flex items-center justify-center text-2xl text-white font-bold cursor-pointer bg-red-500 hover:bg-red-600 shadow-lg hover:shadow-sm rounded-xl h-16 w-24">SHORT</div><div id="${coin}Close" class="text-3xl text-red-500 px-10" style="display: none"><div class="flex-col-center" onclick="closeOpenPosition(this)"><i class="fas fa-dollar-sign"></i><div class="text-xs">Close</div></div><div onclick="removeCoin(this)" class="flex-col-center ml-10"><i class="fas fa-trash"></i><div class="text-xs">Remove</div></div></div></div>`;
  innerDiv.id = coin
  innerDiv.style.opacity = 1
  innerDiv.style.animation = 'fadeIn 1s linear'
  innerDiv.addEventListener('touchstart', handleTouchStart, false);
  innerDiv.addEventListener('touchmove', handleTouchMove, false);
  innerDiv.addEventListener('contextmenu', handleRightClick, false);
  quickTradeDiv.appendChild(innerDiv)
  document.getElementById(`${coin}QuickTradeCoinText`).addEventListener('click', changeChart, false);
//  quickTradeDiv.appendChild(quickTradeComponent)
}

function hideMessages() {
    document.getElementById('messageBoxDiv').innerHTML = ''
}

function displayMessage(message) {
    var messageDiv = document.getElementById('messageBoxDiv')
    var component = `<div class="flex flex-row justify-center items-center mx-auto my-auto message-alert bg-green-200 rounded-lg text-green-500 text-center h-20 text-2xl" style="width: 90%">${message}</div>`
    messageDiv.innerHTML = component;
    setTimeout(hideMessages, 3000);

}

function updateChart() {
//    console.log('updating chart');
    var coinText = document.getElementById('coinText')
    var intervalText = document.getElementById('intervalText').innerHTML
    var coin = coinText.innerHTML
//    console.log(coin)
    fetch(`${window.origin}/plot`, {
        method: 'post',
        headers: {
        'Content-Type': 'application/json'
        // 'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: JSON.stringify({
            symbol: coin,
            interval: intervalText
        }),
    })
        .then(function(response){
        if (response.status !== 200) {
            displayMessage(`Bad response from chart api: ${response.status}`)
            return ;
        }
        response.json().then(function(data){
            var chartSpace = document.getElementById('chartSpace')
            var imgTag = new Image();
            imgTag.onload = function() {
                chartSpace.setAttribute('src', data.base64)
            }
            imgTag.src = data.base64;
        })
    })
}

function changeChart() {
    var symbol = this.innerHTML
    var coinText = document.getElementById('coinText')
    coinText.innerHTML = symbol
    updateChart()
//    console.log(symbol)
//    apiPostRequest('/plot', data, function(response) {updateChart()})
}

var chartInterval = 10000;
var intervalId;

function getInterval() {
    return chartInterval
}

function startInterval(_interval) {
    intervalId = setInterval(function() {
        updateChart()
    }, _interval);
}

function selectInterval(btn) {
    var intervalText = document.getElementById('intervalText')
    var interval = btn.innerHTML
    intervalText.innerHTML = interval
    switch(interval) {
        case '1m':
            chartInterval = 2000;
            break;
        case '15m':
            chartInterval = 5000;
            break;
        case '1h':
            chartInterval = 10000;
            break;
        case '4h':
            chartInterval = 10000;
            break;
    }
//    console.log(interval)
//    console.log(chartInterval)
    clearInterval(intervalId);
    startInterval(chartInterval);
    updateChart();
}

function startTime(clock) {
  var today = new Date();
  var h = today.getHours();
  var m = today.getMinutes();
  var s = today.getSeconds();
  m = checkTime(m);
  s = checkTime(s);
  clock.innerHTML =
  h + ":" + m + ":" + s;
  var t = setTimeout(function(){startTime(clock)}, 500);
}
function checkTime(i) {
  if (i < 10) {i = "0" + i};  // add zero in front of numbers < 10
  return i;
}