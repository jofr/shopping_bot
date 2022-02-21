#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import datetime
import calendar
from matplotlib import pyplot
import squarify
import io

from ledger import Ledger

plural = {
    "user": "users",
    "category": "categories"
}

def currency(x, pos):
    return "{:.0f} €".format(x)

def plot_treemap(ax, categories, values, colors=None, title=None):
    squarify.plot(values, color=colors, label=categories, value=values, ax=ax, pad=True)

    return 5

def plot_hbars(ax, categories, values, colors=None, title=None):
    ax.grid(visible=False, axis="y")
    ax.grid(visible=True, which="major", axis="x")

    labels = ax.get_xticklabels()
    pyplot.setp(labels, rotation=45, horizontalalignment="right")
    ax.xaxis.set_major_formatter(currency)

    container = ax.barh(list(reversed(categories)), list(reversed(values)), height=.8, color=list(reversed(colors)))
    ax.bar_label(container, fmt="%.2f €", label_type="edge", padding=8)

    return len(values)

def plot_stacked(ax, categories, values, colors=None, title="", horizontal=False):
    if horizontal:
        ax.grid(visible=False, axis="y")
        ax.grid(visible=True, which="major", axis="x")
    else:
        ax.grid(visible=True, which="major", axis="y")
        ax.grid(visible=False, axis="x")

    if len(values) == 0:
        ax.bar(title, [0], width=.8, bottom=[0], color=["gray"])

    i = 0
    bottom = 0
    old_value_sum = 0
    while i < len(values):
        if i > 0:
            bottom += values[i-1]
        if horizontal:
            container = ax.barh(title, [values[i]], height=.8, left=[bottom], color=[colors[i]])
            if i == len(values)-1:
                ax.bar_label(container, fmt="%.2f €", label_type="edge", padding=8)
        else:
            container = ax.bar(title, [values[i]], width=.8, bottom=[bottom], color=[colors[i]])
            if i == len(values)-1:
                ax.bar_label(container, fmt="%.2f €", label_type="edge", padding=6)
        
        if categories:
            left, right = ax.get_xlim()
            width = right - left
            value_sum = old_value_sum + values[i]
            value_center = old_value_sum + (value_sum - old_value_sum)/2

            if horizontal:
                rotation="horizontal"
                if values[i] < .15*width:
                    rotation="vertical"
                if values[i] > .05*width:
                    ax.text(value_center, title, categories[i] + "\n{:.2f} €".format(values[i]), va="center", ha="center", rotation=rotation)
                
            old_value_sum = value_sum

        i += 1

def plot_stacked_bar(ax, categories, values, colors=None, title=""):
    ax.grid(visible=True, which="major", axis="y")
    ax.grid(visible=False, axis="x")

    xticklabels = ax.get_xticklabels()
    pyplot.setp(xticklabels, rotation=45, horizontalalignment="right")
    ax.yaxis.set_major_formatter(currency)

    plot_stacked(ax, categories, values, colors, title)

    return 3

def plot_stacked_hbar(ax, categories, values, colors=None, title=""):
    ax.grid(visible=False, axis="y")
    ax.grid(visible=True, which="major", axis="x")

    xticklabels = ax.get_xticklabels()
    pyplot.setp(xticklabels, rotation=45, horizontalalignment="right")
    ax.xaxis.set_major_formatter(currency)

    plot_stacked(ax, categories, values, colors, title, horizontal=True)

    return 1

def save_to_buffer(fig):
    buffer = io.BytesIO()
    fig.savefig(buffer, format="pdf")
    buffer.seek(0)

    return buffer

def calculate_data_and_plot(ax, plot, ledger, from_time, to_time, recipient, config, automatic_title):
    hbars = 0
    for data in reversed(plot):
        sort = False
        if "sort" in data:
            sort = data["sort"]
        result = getattr(ledger, "calculate_" + data["what"] + "_per_" + data["per"])(from_time, to_time, recipient, sort)
        categories = list(map(lambda x: config[plural[data["per"]]][x[0]]["display_name"], result))
        values = list(map(lambda x: x[1], result))
        colors = list(map(lambda x: config[plural[data["per"]]][x[0]]["color"], result))
        title = ""
        if "title" in data:
            title = data["title"]
        else:
            title = automatic_title
        hbars += globals()["plot_" + data["type"]](ax, categories, values, colors=colors, title=title)

    return hbars

def generate_report(type, user, ledger, config):
    """
    Generates a report (a plot using Matplotlib) for the specified user from the
    given ledger. Returns a buffer containing the image.
    """

    pyplot.style.use('style.mplstyle')
    pyplot.rcParams.update({'figure.autolayout': True,
                            'font.family': 'sans-serif',
                            'font.sans-serif': 'Noto Emoji',
                            'font.size': '15'})
    pyplot.rcParams['font.family'] = ['Roboto Condensed', 'sans-serif']

    report_axes = config[type + "_report"]["figures"]
    fig, axs = pyplot.subplots(len(report_axes), 1)
    today = datetime.date.today()
    fig.suptitle(
        config[type + "_report"]["title"] + " {} (bis {})".format(today.strftime("%Y"), today.strftime("%d.%m.")),
        fontsize=25,
        fontweight="bold")
    fig.set_size_inches(11.69, 16.54, forward=True)
    fig.set_dpi(300)
    hsizes = []

    i = 0
    for report_axe in report_axes:
        ax = axs[i]

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_visible(True)
        ax.spines["left"].set_visible(True)

        if "title" in report_axe:
            ax.set_title(report_axe["title"], loc="center")

        recipient = report_axe["recipient"]
        if recipient == "user":
            recipient = user

        hbars = 0
        if report_axe["period"] == "year" or report_axe["period"] == "month":
            from_time = 0
            to_time = 9999999999
            if report_axe["period"] == "month":
                from_time = time.mktime(datetime.date(today.year, today.month, 1).timetuple())
                to_time = time.mktime(today.timetuple())
            
            hbars += calculate_data_and_plot(ax, report_axe["plot"], ledger, from_time, to_time, recipient, config, "default")
        elif report_axe["period"] == "per_month_of_year":
            local_hbars = 0
            for month in range(1, 13):
                from_time_date = datetime.date(today.year, month, 1)
                from_time = time.mktime(from_time_date.timetuple())
                (_, last_day) = calendar.monthrange(today.year, month)
                to_time = time.mktime(datetime.date(today.year, month, last_day).timetuple())

                local_hbars = calculate_data_and_plot(ax, report_axe["plot"], ledger, from_time, to_time, recipient, config, "{}".format(from_time_date.strftime("%b")))
            hbars += local_hbars

        hsizes.append(hbars)

        #axs[i].set_box_aspect(hbars/4)

        i += 1

    return save_to_buffer(fig)