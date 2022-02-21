#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from functools import wraps
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
import yaml
import re
from datetime import time
import pytz
from shutil import copyfile

from ledger import Ledger
from report import generate_report

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

config = yaml.safe_load(open("configuration.yaml"))
ledger = Ledger(config["ledger_file"])
list_of_users = []
for user_data in config["users"].values():
    if "telegram_id" in user_data:
        list_of_users.append(user_data["telegram_id"])

def set_up_keyboard(categories, prefix):
    """
    Given a dict of categories creates a Telegram keyboard (e.g. an input method
    with a button for each category) and returns it. The callback data of the
    Telegram keyboard is set as prefix + ":" + the category name.
    
    Each category should contain a dict that further specifies that category.
    For the keyboard the "display_name" and "emoji_name" properties are used as
    the label for the buttons in the keyboard.
    """

    keyboard = []

    row = []
    for category, data in categories.items():
        keyboard_text = "{} {}".format(data.get("display_name", ""), data.get("emoji_name", ""))
        row.append(InlineKeyboardButton(keyboard_text, callback_data=prefix+":"+category))
        # Restrict keyboard to two columns so that the labels (ideally) won't be word-wrapped
        if len(row) == 2:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    return keyboard

recipient_keyboard = set_up_keyboard(config["users"], "recipient")
user_keyboard = set_up_keyboard(config["users"], "user")
category_keyboard = set_up_keyboard(config["categories"], "category")

def restricted(func):
    """
    Function wrapper that should be used for all Telegram bot functions to
    restrict access to the bot to the users configured in the configuration.
    """

    @wraps(func)
    def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in list_of_users:
            update.message.reply_text('Du stehst leider nicht auf der Liste '
                                      'der Leute die mich benutzen dürfen! 😊')
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
                              'einfach den Befehl /help ein 😊')

@restricted
def help(update, context):
    update.message.reply_text('Wenn du mir schreibst, wer für was wieviel ausgegeben hat '
                              'speicher ich dies und schicke euch am Ende von jedem Monat '
                              'eine Auswertung! 📊')

def create_report(user, bot):
    buffer_personal_report = generate_report("personal", user, ledger, config)
    buffer_common_report = generate_report("common", user, ledger, config)

    bot.send_media_group(config["users"][user]["telegram_id"],
                         [InputMediaPhoto(buffer_personal_report),
                          InputMediaPhoto(buffer_common_report)])

    buffer_personal_report.close()
    buffer_common_report.close()

@restricted
def report(update, context):
    user_name = ""
    user_id = update.effective_user.id
    for user, data in config["users"].items():
        if data.get("telegram_id") == user_id:
            user_name = user
            create_report(user_name, context.bot)

def monthly_report(context):
    for user in config["users"].keys():
        create_report(user, context.bot)

def find_name_or_synonym_in_message(name, synonyms, message):
    """
    Find either the name or one of the list of synonyms in message and return
    the name if either of those is found or an empty string otherwise.
    """

    if name in message:
        return name
    else:
        for synonym in synonyms:
            if synonym in message:
                return name
    
    return ""

def is_information_missing(user_data):
    if user_data["recipient"] == "" or user_data["user"] == "" or user_data["category"] == "":
        return True
    else:
        return False

def get_next_missing_information(user_data):
    if user_data["recipient"] == "":
        text = "Mir fehlt noch die Information, für wen der Einkauf war?"
        reply_markup = InlineKeyboardMarkup(recipient_keyboard)
        return text, reply_markup
    elif user_data["user"] == "":
        text = "Jetzt musst du mir noch sagen, wer bezahlt hat:"
        reply_markup = InlineKeyboardMarkup(user_keyboard)
        return text, reply_markup
    elif user_data["category"] == "":
        text = "In welche Kategorie fällt der Einkauf?"
        reply_markup = InlineKeyboardMarkup(category_keyboard)
        return text, reply_markup

def enter_expense(user_data):
    ledger.enter(user_data["user"],
                 user_data["value"],
                 category=user_data["category"],
                 recipient=user_data["recipient"],
                 comment=user_data["comment"])

@restricted
def text_message(update, context):
    """
    Every text message containing something that is formated like a monetary
    value (e.g. "12", "5.70" or "500,99") is treated as a new ledger entry. If a
    user name is recognized this is interpreted as the user who has payed and if
    a category is recognized in the message it will be used as the category for
    this expense. All missing information is requested using one of the Telegram
    keyboards.
    """

    message = update.message.text
    values = re.findall(r"((?:[0-9]*[.,])?[0-9]+)", message)

    if not values:
        update.message.reply_text("Falls du einen Einkauf verbuchen wolltest, habe ich dich leider "
                                  "nicht verstanden. 🤔")
    else:
        context.user_data["value"] = float(values[0].replace(',', '.'))

        context.user_data["comment"] = message

        context.user_data["recipient"] = ""

        context.user_data["user"] = ""
        for user, data in config["users"].items():
            if context.user_data["user"] == "":
                user_name = find_name_or_synonym_in_message(user, data["synonyms"], message)
                context.user_data["user"] = user_name
            else:
                break

        context.user_data["category"] = ""
        for category, data in config["categories"].items():
            if context.user_data["category"] == "":
                category_name = find_name_or_synonym_in_message(category, data["synonyms"], message)
                context.user_data["category"] = category_name
            else:
                break

        reply = "Cool, ein neuer Einkauf, werde ich direkt verbuchen. 😊📝 "
        reply_markup = None

        if not is_information_missing(context.user_data):
            enter_expense(context.user_data)
        else:
            text, markup = get_next_missing_information(context.user_data)
            reply = reply + text
            reply_markup = markup

        update.message.reply_text(reply, reply_markup=reply_markup)

@restricted
def callback_query(update, context):
    """
    Called every time we get callback data from one of the Telegram keyboards.
    So this is always data that is needed for a new ledger entry and was still
    missing until now, therefore check if there is still other data missing at
    the end of this function and depending on that display the next keyboard or
    enter the new transaction into the ledger.
    """

    # Map provided data for ledger entry (category, recipient or user) to the
    # section of the configuration containing the display name (to be used in
    # the reply by the bot)
    display_map = {
        "category": "categories",
        "recipient": "users",
        "user": "users"
    }

    query = update.callback_query
    query.answer()
    edit = query.message.text

    data = query.data.split(":")
    context.user_data[data[0]] = data[1]
    edit += " " + config[display_map[data[0]]][data[1]]["display_name"] + ". "
    reply_markup = None

    if not is_information_missing(context.user_data):
        enter_expense(context.user_data)
    else:
        text, markup = get_next_missing_information(context.user_data)
        edit += text
        reply_markup = markup

    query.edit_message_text(edit, reply_markup=reply_markup)

def error(update, context):
    logger.warning('Update "%s" caused error "%s"', update, context.error)

def rotate_db_backup(context):
    copyfile(config["ledger_file"], config["ledger_file"] + ".backup")

def main():
    updater = Updater(config["bot_token"], use_context=True)

    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CommandHandler('help', help))
    dispatcher.add_handler(CommandHandler('report', report))
    dispatcher.add_handler(MessageHandler(Filters.text, text_message))
    dispatcher.add_handler(CallbackQueryHandler(callback_query))
    dispatcher.add_error_handler(error)

    job_queue = updater.job_queue
    # TODO: Get time zone from system and/or configuration file?
    # Automatically create a report for every user at the end of each month
    job_queue.run_monthly(monthly_report,
                          time(hour=23, minute=55, tzinfo=pytz.timezone('Europe/Berlin')),
                          day=31,
                          day_is_strict=False)
    # Create a backup of the ledger each day and keep one backup
    job_queue.run_daily(rotate_db_backup,
                        time(hour=4, minute=0, tzinfo=pytz.timezone('Europe/Berlin')))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()