# Plan0: Leitner Emulator (Manual Intervals)
Anki Addon: Leitner System With Manual Intervals

## About:
This addon adds manual intervals to Anki as a custom scheduler. As a result, it also allows the creation of Leitner's boxes using filter decks.

## Logging:
Logging is disabled by default, but can be turned on by editing the script. As this is not proper SRS, doing so could skew your stats.

## Button Operations:
Button1: Reset, start index from 1. Repeat the card again.  
Button2: Move the index back by 1 count. Repeat the card again.  
Button3: Repeat the current schedule (e.g. every 3 days etc...).  
Button4: Move the index forward by 1 count and reschedules the card.  

## Configs:
### Manual Interval Control
Enable addon in deck options menu.  
Set IVL steps for manual control.  

<img src="https://github.com/lovac42/LeitnerEmulator/blob/master/screenshots/optmenu.png?raw=true"/>

IVL auto doubles when it falls out of given range.  
<b>SM-0:</b> 1 7 16 35 <i>(70) (140) (280)  ...</i>  


IVL rotates when it receives a smaller number.  
<b>Loop to beginning:</b> 1 2 3 4 5 <i>1 (2) (3) (4) ...</i>  
<b>Loop to middle:</b> 1 2 3 4 5 <i>3 (4) (5) (3) (4) ...</i>  
<b>Capped at max*:</b> 1 2 3 4 5 <i>5 (5) (5) (5) (5) ...</i>  
<b>Bypass addon**:</b> 1 2 3 4 <i>-5 (regular scheduler) </i>

<i>* The max value is capped only if the current interval is smaller than the maximum. Set "Maximum Interval" to enforce on all cards.</i>  
<i>** Use negative value on the last step to bypass this addon. It will use Anki's regular scheduler (with logging) if the card's current ivl equals or exceeds this interval.</i>  


# Leitner System Setup
Use filter decks to emulate Leitner's learning boxes.  
Make sure "Reschedule" options is turned on.  
<img src="https://github.com/lovac42/LeitnerEmulator/blob/master/screenshots/leitner.png?raw=true"/>

#### Filter Deck Setup
Use filtered decks to sort by IVL.  
<b> (Box1):</b> deck:"MorseDrill" prop:ivl<=1  
<b> (Box2):</b> deck:"MorseDrill" prop:ivl=2  
<b> (Box3):</b> deck:"MorseDrill" prop:ivl=3  
<b> (Box4):</b> deck:"MorseDrill" prop:ivl=4  
<b> (Box5):</b> deck:"MorseDrill" prop:ivl=5  
<b> (TheDayOfLavos):</b> deck:"MorseDrill"  prop:ivl=1999  

<i>*Change filter options as necessary.</i>
