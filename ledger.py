#!/usr/bin/env python
# -*- coding: utf-8 -*-

import csv
import io
import time

class Ledger:
    """
    The ledger contains all financial expenses in one large table with 6
    columns: user (who payed?), value, category, time (as unix timestamp),
    recipient (who was the purchase for?) and an optional comment.
    
    New purchases can be entered into the ledger and expenses per category or
    per user for specific timeframes and specific recipients can be calculated.

    Ledger data is persisted in a CSV file.
    """

    column_to_index = {
        "user": 0,
        "value": 1,
        "category": 2,
        "time": 3,
        "recipient": 4,
        "comment": 5
    }

    csv_delimiter = " "
    csv_quoting = csv.QUOTE_NONNUMERIC

    def __init__(self, filename):
        self.ledger = []
        self.filename = filename

        with open(filename) as file:
            for row in csv.reader(file, delimiter=self.csv_delimiter, quoting=self.csv_quoting):
                self.ledger.append(row)

    def enter(self, user, value, category="", unixtime=None, recipient="", comment=""):
        if not unixtime:
            unixtime = int(time.time())

        # If no specific recipient is given assume that this is a purchase for
        # the person who payed and not for someone else
        if recipient == "":
            recipient = user

        self.ledger.append([user, value, category, unixtime, recipient, comment])
        with open(self.filename, "w") as file:
            csv_writer = csv.writer(file, delimiter=self.csv_delimiter, quoting=self.csv_quoting)
            csv_writer.writerows(self.ledger)

    def __filter_time_and_recipient(self, from_time, to_time, recipient):
        filtered_ledger = []
        time_index = self.column_to_index["time"]
        recipient_index = self.column_to_index["recipient"]

        for transaction in self.ledger:
            pass_time_filter = transaction[time_index] < to_time and transaction[time_index] > from_time
            pass_recipient_filter = transaction[recipient_index] == recipient
            if pass_time_filter and pass_recipient_filter:
                filtered_ledger.append(transaction)

        return filtered_ledger

    def __calculate_expenses_per_x(self, from_time, to_time, recipient, x, sort):
        filtered_ledger = self.__filter_time_and_recipient(from_time, to_time, recipient)
        x_index = self.column_to_index[x]
        value_index = self.column_to_index["value"]
        
        # Dictionary containing summarized expenses for every distinct value in
        # column x (e.g. if x is the user column this is a dict mapping each
        # user to a value of all the money spent on purchases for the specified
        # recipient)
        sums = dict()
        for transaction in filtered_ledger:
            x_value = transaction[x_index]
            if not (x_value in sums):
                sums[x_value] = .0
            sums[x_value] += transaction[value_index]

        result = sums.items()
        if sort:
            result = sorted(result, key=lambda x: x[1], reverse=True)

        return result

    def calculate_expenses_per_category(self, from_time, to_time, recipient, sort=False):
        return self.__calculate_expenses_per_x(from_time, to_time, recipient, "category", sort)

    def calculate_expenses_per_user(self, from_time, to_time, recipient, sort=False):
        return self.__calculate_expenses_per_x(from_time, to_time, recipient, "user", sort)