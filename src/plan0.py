# -*- coding: utf-8 -*-
# Copyright: (C) 2018 Lovac42
# Support: https://github.com/lovac42/LeitnerEmulator
# License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html
# Version: 0.0.2


from __future__ import division
# == User Config =========================================

# When IVL exceeds max number provided,
# NEW_IVL = IVL * USE_FACTOR * conf_multiplier
# NEW_IVL = IVL * EF * conf_multiplier
# 0 to disable and use factor from each card.
USE_FACTOR = 2

#Subtract index on hard
GRADE_HARD = 1   # 2?

#Increase index on easy
GRADE_EASY = 1

DEFAULT_IVL = "1 2 3 4 5 1999 1999"   # Leitner
# DEFAULT_IVL = "1 7 16 35"           # SM-0
# DEFAULT_IVL = "1 10 20 30 1"        # Rotate

FILTER_INC_READ_MODEL = False
# DEFAULT_IVL=5 10 20 30 45 60 90 120 200 200   # For IR

# Discount days from overdues cards so it aligns with calendar
ADJUST_FOR_OVERDUE = False

# Enabling this will affect your collection stats.
# As the intervals are manually controled,
# it may not skew your true retention.
ENABLE_REVLOG_LOGGING = False
# Disabling logging will also disable your Rep/Leech count.

# == End Config ==========================================
##########################################################


# Based on Plan9 as Template

from aqt import mw
from anki.hooks import wrap, addHook
from aqt.reviewer import Reviewer
from anki.utils import intTime, fmtTimeSpan, ids2str
from heapq import *
import anki.sched
import time, random


from anki import version
ANKI21 = version.startswith("2.1.")
if ANKI21:
    import anki.schedv2
    from PyQt5 import QtCore, QtGui, QtWidgets
else:
    from PyQt4 import QtCore, QtGui as QtWidgets


#####################################################################
####   Filters, don't apply addon to certain models  ################
#####################################################################
isFilteredCard = False

def isFiltered():
    card = mw.reviewer.card
    conf = mw.col.decks.confForDid(card.did)
    if conf['dyn']:
        if not conf['resched']: return True
        conf = mw.col.decks.confForDid(card.odid)

    if not conf.get("sm0emu", False):
        return True

    if FILTER_INC_READ_MODEL: #Avoid IR Cards
        model = card.model()['name']
        if model=='IR3' or model[:6]=='IRead2': 
            return True

    return False


def onShowQuestion():
    global isFilteredCard
    isFilteredCard=isFiltered()

addHook('showQuestion', onShowQuestion)


#####################################################################
####      Button Display                         ####################
#####################################################################

def answerButtons(self, card, _old):
    if isFilteredCard:
        return _old(self, card)
    return 4

def answerButtonList(self, _old):
    if isFilteredCard:
        return _old(self)
    return ((1, _('Reset')), 
            (2, _('Lower')),
            (3, _('Same')), 
            (4, _('Higher')) )


def buttonTime(self, i, _old):
    if isFilteredCard:
        return _old(self, i)
    if i==1: return "Clear<br>"
    if i==2: return "Repeat<br>"
    return '%s<br>'%nextIntervalString(self.card, i)


#####################################################################
########   Custom Scheduler                              ############
#####################################################################


LOG_LEARNED=0
LOG_REVIEWED=1
LOG_RELEARNED=2
LOG_CRAM=3 #not used
LOG_RESCHED=4

def answerCard(self, card, ease, _old):
    if isFilteredCard:
        return _old(self, card, ease)

    self.col.log()
    assert ease >= 1 and ease <= 4
    self.col.markReview(card) #for undo
    if self._burySiblingsOnAnswer:
        self._burySiblings(card)

    #SETUP LOGGING PARAMS
    delay=0
    revType = 'rev'
    logType = LOG_REVIEWED
    card.factor=adjustFactor(card,0) #initialize new/malformed cards

    #LOG TIME (for Display only)
    if card.queue==2:
        card.lastIvl = card.ivl
    elif card.queue==3:
        card.lastIvl = -86400 #1d learning step in secs
    else:
        card.lastIvl = -getDelay(self, card)

    #LOG TYPE
    if card.type==0 and card.queue==0:
        logType = LOG_LEARNED
        revType = 'new'
    elif card.queue in (1,3):
        logType=LOG_RELEARNED if card.type==2 else LOG_LEARNED
        revType = 'lrn'


    #PROCESS GRADES
    if ease==1: #reset
        card.ivl=1 #Can't be 0
        if not isLeechCard(card): #chk suspend
            delay=repeatCard(self, card) #sets queue to 1

    elif ease==2: #repeat
        card.ivl = nextInterval(self, card, ease)
        delay=repeatCard(self, card) #sets queue to 1

    else: #advance
        overdue=0
        if ADJUST_FOR_OVERDUE and card.queue==2:
            # Note: due on learning cards count by secs
            #       due on review cards count by days
            overdue = max(0, self.today - card.due)
        card.ivl = nextInterval(self, card, ease)
        card.due = self.today + max(1, card.ivl-overdue)
        card.type = card.queue = 2
        card.left = 0
        if card.odid:
            card.did = card.odid
            card.odid=card.odue=0

    #LOG THIS REVIEW
    if ENABLE_REVLOG_LOGGING:
        logStats(card, ease, logType, delay)
        card.reps += 1
    self._updateStats(card, revType)
    self._updateStats(card, 'time', card.timeTaken())
    card.mod = intTime()
    card.usn = self.col.usn()
    card.flushSched()


def nextIntervalString(card, ease): #button date display
    ivl=nextInterval(mw.col.sched, card, ease)
    return fmtTimeSpan(ivl*86400, short=True)


def nextInterval(self, card, ease):
    conf=mw.col.decks.confForDid(card.did)
    if conf['dyn']:
        conf = mw.col.decks.confForDid(card.odid)

    custom_ivl=[int(x) for x in conf['sm0Steps'].split()]
    if card.ivl<=1 and ease<4:
        return custom_ivl[0]

    LEN=len(custom_ivl)
    try:
        idx=custom_ivl.index(card.ivl)
    except ValueError:
        idx=LEN
        #find best match, in case user changes profiles
        for i,v in enumerate(custom_ivl):
            if card.ivl <= v: idx=i; break;

    #Adjust index base on grade
    if ease==2: idx -= GRADE_HARD
    elif ease>3: idx += GRADE_EASY

    if idx<1:
        idealIvl=custom_ivl[0]
    elif idx<LEN:
        idealIvl=custom_ivl[idx]
    else:
        modifier=conf['rev'].get('ivlFct', 1)
        if ease==2:
            if USE_FACTOR:
                idealIvl = card.ivl / USE_FACTOR / modifier
            else:
                card.factor=adjustFactor(card,0) #initialize new/malformed cards
                idealIvl = card.ivl / (card.factor/1000.0) / modifier
            idealIvl = min(card.ivl, int(idealIvl)) #prevent larger ivls from %modifier%
        elif ease==3:
            idealIvl=card.ivl
        elif ease==4:
            if USE_FACTOR:
                idealIvl = card.ivl * USE_FACTOR * modifier
            else:
                card.factor=adjustFactor(card,0) #initialize new/malformed cards
                idealIvl = card.ivl * (card.factor/1000.0) * modifier
            idealIvl = max(card.ivl, int(idealIvl)) #prevent smaller ivls from %modifier%

    idealIvl=max(1,idealIvl) #no funny stuff, no 0 ivl
    return min(idealIvl, conf['rev']['maxIvl'])



#####################################################################
#######          Utils                                ##############
#####################################################################


#log type
#0 = learned
#1 = review
#2 = relearned
#3 = filtered, not used here

def logStats(card, ease, type, delay): #copied & modded from anki.sched.logStats
    def log():
        mw.col.db.execute(
            "insert into revlog values (?,?,?,?,?,?,?,?,?)",
            int(time.time()*1000), card.id, mw.col.usn(), ease,
            -delay or card.ivl or 1, card.lastIvl,
            card.factor, card.timeTaken(), type)
    try:
        log()
    except:
        time.sleep(0.01) # duplicate pk; retry in 10ms
        log()

def adjustFactor(card, n):
    fct=2500 if card.factor==0 else card.factor
    fct += n
    return max(fct,1300)

def isLeechCard(card): #review cards only
    if not ENABLE_REVLOG_LOGGING: return False
    if card.queue!=2: return False
    card.lapses += 1
    conf=mw.col.sched._lapseConf(card)
    leech=mw.col.sched._checkLeech(card,conf)
    return leech and card.queue == -1

def repeatCard(self, card):
    #new cards in learning steps: card.type=1
    #lapse cards in learning steps: card.type=2
    card.type=2 if card.type==2 else 1
    card.queue = 1
    card.left = 1001

    delay=getDelay(self,card)
    card.due = intTime() + delay
    self.lrnCount += 1
    heappush(self._lrnQueue, (card.due, card.id))
    return delay


def getDelay(self, card):
    conf=self._lrnConf(card)
    return self._delayForGrade(conf,0)


#####################################################################
## Non-Gui Monkey patch assignment                        ###########
#####################################################################

Reviewer._answerButtonList = wrap(Reviewer._answerButtonList, answerButtonList, 'around')
Reviewer._buttonTime = wrap(Reviewer._buttonTime, buttonTime, 'around')

anki.sched.Scheduler.answerCard = wrap(anki.sched.Scheduler.answerCard, answerCard, 'around')
anki.sched.Scheduler.answerButtons = wrap(anki.sched.Scheduler.answerButtons, answerButtons, 'around')
if ANKI21:
    anki.schedv2.Scheduler.answerCard = wrap(anki.schedv2.Scheduler.answerCard, answerCard, 'around')
    anki.schedv2.Scheduler.answerButtons = wrap(anki.schedv2.Scheduler.answerButtons, answerButtons, 'around')


##################################################
#  Gui stuff
#  Adds deck menu options to enable/disable
#  this addon for specific decks
#################################################
import aqt
import aqt.deckconf
from aqt.qt import *


try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s


def dconfsetupUi(self, Dialog):
    r=self.gridLayout_3.rowCount()

    self.sm0emu = QtWidgets.QCheckBox(self.tab_3)
    self.sm0emu.setObjectName(_fromUtf8("sm0emu"))
    self.sm0emu.setText(_('Use Custom Intervals'))
    self.gridLayout_3.addWidget(self.sm0emu, r, 0, 1, 3)
    self.sm0emu.toggled.connect(lambda:togglesm0emuCB(self))
    r+=1

    self.sm2HLayout = QtWidgets.QHBoxLayout()
    self.sm2HLayout.setObjectName(_fromUtf8("sm2HLayout"))
    self.sm0StepsLabel = QtWidgets.QLabel(Dialog)
    self.sm0StepsLabel.setObjectName(_fromUtf8("sm0StepsLabel"))
    self.sm0StepsLabel.setText(_("Ivl Steps:"))
    self.sm2HLayout.addWidget(self.sm0StepsLabel)

    self.sm0Steps = QtWidgets.QLineEdit(self.tab_3)
    self.sm0Steps.setObjectName(_fromUtf8("sm0Steps"))
    self.sm2HLayout.addWidget(self.sm0Steps)
    self.gridLayout_3.addLayout(self.sm2HLayout, r, 0, 1, 2)


def togglesm0emuCB(self):
    off=self.sm0emu.checkState()==0
    on = not off

    try: #no plan9 addon
        if on and self.sm2emu.checkState():
            self.sm2emu.setCheckState(0)
            self.sm2priority.setDisabled(True)
    except: pass

    self.sm0Steps.setDisabled(off)
    self.lrnGradInt.setDisabled(on)
    self.lrnEasyInt.setDisabled(on)
    self.lrnFactor.setDisabled(on)
    self.lapMinInt.setDisabled(on)
    self.lapMult.setDisabled(on)
    self.easyBonus.setDisabled(on)
    # self.fi1.setDisabled(on) #ivl modifier


def loadConf(self):
    txt=self.conf.get("sm0Steps", DEFAULT_IVL)
    if not txt: txt=DEFAULT_IVL
    self.form.sm0Steps.setText(str(txt))
    cb=self.conf.get("sm0emu", 0)
    self.form.sm0emu.setCheckState(cb)
    togglesm0emuCB(self.form)


def saveConf(self):
    self.conf['sm0emu']=self.form.sm0emu.checkState()
    self.conf['sm0Steps']=self.form.sm0Steps.text()


aqt.forms.dconf.Ui_Dialog.setupUi = wrap(aqt.forms.dconf.Ui_Dialog.setupUi, dconfsetupUi, pos="after")
aqt.deckconf.DeckConf.loadConf = wrap(aqt.deckconf.DeckConf.loadConf, loadConf, pos="after")
aqt.deckconf.DeckConf.saveConf = wrap(aqt.deckconf.DeckConf.saveConf, saveConf, pos="before")
