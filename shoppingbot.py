#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import time
from pathlib import Path
from functools import wraps
import re
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, Filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import telegram
import matplotlib.pyplot as plot
import csv
from shutil import copyfile

from .configuration import kategorien, LIST_OF_USERS, API_TOKEN

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

zahlungen = []

def restricted(func):
    @wraps(func)
    def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in LIST_OF_USERS:
            update.message.reply_text('Du stehst leider nicht auf der Liste '
                                      'von Leuten die mich benutzen dürfen! 😊')
            logger.info('Zugriff wurde untersagt für ' + str(user_id) + ' (' +
                        update.effective_user.first_name + ')')
            return
        return func(update, context, *args, **kwargs)
    return wrapped

def start(update, context):
    update.message.reply_text('Hi! Ich bin der Shopping Bot und kümmer mich darum '
                              'den Überblick über die Finanzen zu behalten! 🛒📃'
                              '\n'
                              'Wenn du wissen willst, was ich machen kann, gib '
                              'einfach den Befehl /hilfe ein 😊')

@restricted
def hilfe(update, context):
    update.message.reply_text('Wenn du mir schreibst, wer für was wieviel ausgegeben hat '
                              'speicher ich dies und schicke euch am Ende von jedem Monat '
                              'eine Auswertung! 📊')

def finanzreport_erstellen(from_time, to_time):
    betrag_alice = 0.0
    betrag_bob = 0.0
    for zahlung in zahlungen:
        if zahlung[3] < to_time and zahlung[3] > from_time:
            if zahlung[0] == "Alice":
                betrag_alice += zahlung[1]
            elif zahlung[0] == "Bob":
                betrag_bob += zahlung[1]

    plot.clf()
    x_werte = ["Alice", "Bob"]
    y_werte = [betrag_alice, betrag_bob]
    plot.ylabel("Euro")
    plot.bar(x_werte, y_werte)
    plot.savefig("/tmp/menschen.png")

    kategorie_betrag = dict()
    print(kategorie_betrag)
    for kategorie in kategorien.keys():
        print(kategorie)
        for zahlung in zahlungen:
            print(zahlung[2])
            if zahlung[3] < to_time and zahlung[3] > from_time:
                if zahlung[2] == kategorie:
                    print("true")
                    if kategorie in kategorie_betrag:
                        kategorie_betrag[kategorie] += zahlung[1]
                    else:
                        kategorie_betrag[kategorie] = zahlung[1]

    plot.clf()
    x_werte = list(kategorie_betrag.keys())
    y_werte = list(kategorie_betrag.values())
    plot.ylabel("Euro")
    plot.bar(x_werte, y_werte)
    plot.savefig("/tmp/kategorien.png")

@restricted
def finanzreport(update, context):
    finanzreport_erstellen(0, 9999999999)
    update.message.reply_photo(open("/tmp/menschen.png", "rb"))
    update.message.reply_photo(open("/tmp/kategorien.png", "rb"))

def verbuchen(user_data):
    zahlungen.append([user_data["name"], user_data["betrag"], user_data["kategorie"], int(time.time())])
    with open('shopping_db.csv', 'w') as csvfile:
        csv.writer(csvfile, delimiter=' ', quoting=csv.QUOTE_NONNUMERIC).writerows(zahlungen)
    print(zahlungen)

def information_fehlt(user_data):
    if user_data["name"] == "" or user_data["kategorie"] == "":
        return True
    else:
        return False

def naechste_fehlende_information(context):
    if context.user_data["name"] == "":
        text = "Mir fehlt allerdings noch die Information, wer bezahlt hat:"

        keyboard = [
            [
                InlineKeyboardButton("Alice", callback_data='nAlice'),
                InlineKeyboardButton("Bob", callback_data='nBob'),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        return text, reply_markup
    elif context.user_data["kategorie"] == "":
        text = "Jetzt musst du mir noch sagen, in welche Kategorie der Einkauf fällt:"

        keyboard = [
            [ InlineKeyboardButton("Ernährung 🍜", callback_data="kErnährung"),
            InlineKeyboardButton("Drogerie 🧴", callback_data="kDrogerie") ],
            [ InlineKeyboardButton("Elektronik 💻", callback_data="kElektronik"),
            InlineKeyboardButton("Bücher 📚", callback_data="kBücher") ],
            [ InlineKeyboardButton("Kleidung 👕", callback_data="kKleidung"),
            InlineKeyboardButton("Jungle 🪴", callback_data="kJungle") ],
            [ InlineKeyboardButton("Reise 🚁", callback_data="kReise"),
            InlineKeyboardButton("Einrichtung 🛋️", callback_data="kEinrichtung") ],
            [ InlineKeyboardButton("Sonstiges 🎁", callback_data="kSonstiges") ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        return text, reply_markup

@restricted
def nachricht(update, context):
    nachricht = update.message.text
    context.user_data["betrag"] = float(re.findall(r"((?:[0-9]*[.,])?[0-9]+)", nachricht)[0].replace(',', '.'))
    context.user_data["name"] = ""

    context.user_data["kategorie"] = ""
    for kategorie in kategorien.keys():
        for wort in kategorien[kategorie]:
            if wort in nachricht:
                context.user_data["kategorie"] = kategorie

    print(context.user_data["betrag"], context.user_data["name"], context.user_data["kategorie"])

    reply = "Cool, ein neuer Einkauf, werde ich direkt verbuchen. 😊📝 "

    if not information_fehlt(context.user_data):
        verbuchen(context.user_data)
        update.message.reply_text(reply)
    else:
        text, reply_markup = naechste_fehlende_information(context)
        update.message.reply_text(reply + text, reply_markup=reply_markup)
    
@restricted
def set_name(update, context):
    query = update.callback_query
    query.answer()
    edit = query.message.text

    context.user_data["name"] = query.data[1:]
    edit += " " + context.user_data["name"] + ". "

    if not information_fehlt(context.user_data):
        verbuchen(context.user_data)
        query.edit_message_text(edit)
    else:
        text, reply_markup = naechste_fehlende_information(context)
        edit += text
        query.edit_message_text(edit, reply_markup=reply_markup)

@restricted
def set_kategorie(update, context):
    query = update.callback_query
    query.answer()
    edit = query.message.text

    context.user_data["kategorie"] = query.data[1:]
    edit += " " + context.user_data["kategorie"] + ". "

    if not information_fehlt(context.user_data):
        verbuchen(context.user_data)
        query.edit_message_text(edit)
    else:
        text, reply_markup = naechste_fehlende_information(context)
        edit += text
        query.edit_message_text(edit, reply_markup=reply_markup)

def error(update, context):
    logger.warning('Update "%s" caused error "%s"', update, context.error)

def main():
    copyfile('shopping_db.csv', 'shopping_db.csv.backup')
    with open('shopping_db.csv') as shopping_db_file:
        for row in csv.reader(shopping_db_file, delimiter=' ', quoting=csv.QUOTE_NONNUMERIC):
            zahlungen.append(row)


    updater = Updater(API_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CommandHandler('hilfe', hilfe))
    dispatcher.add_handler(CommandHandler('help', hilfe))
    dispatcher.add_handler(CommandHandler('finanzreport', finanzreport))
    dispatcher.add_handler(MessageHandler(Filters.text, nachricht))
    dispatcher.add_handler(CallbackQueryHandler(set_name, pattern='^n'))
    dispatcher.add_handler(CallbackQueryHandler(set_kategorie, pattern='^k'))
    dispatcher.add_error_handler(error)

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
