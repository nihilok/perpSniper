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

    var bubble_id = this.id

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

        } else {
            $(this).css({
              'animation': 'slideSwipeDrawerClose .2s linear',
              '-webkit-transform' : 'translateX(' + 0 + 'rem)',
              '-moz-transform'    : 'translateX(' + 0 + 'rem)',
              '-ms-transform'     : 'translateX(' + 0 + 'rem)',
              '-o-transform'      : 'translateX(' + 0 + 'rem)',
              'transform'         : 'translateX(' + 0 + 'rem)'
            });
        }
    }
    /* reset values */
    xDown = null;
    yDown = null;
};

function addBubble(colour) {
    var bubbleDiv = document.getElementById('waveBubbleParent')
    var newBubble = document.createElement('div')
    newBubble.classList.add('waveBubble', `bg-${colour}-500`, `hover:bg-${colour}-600`, 'flex-none')
    bubbleDiv.appendChild(newBubble)
    console.log('done')
}