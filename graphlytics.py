import datetime
import random
import sqlite3
import string
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

import db

string_len = 20

def _get_label(age):
    if age > 100: return "tags"
    if age > 17: return "adult"
    if age > 0: return "minor"
    return "unknown"

def _get_daily(parsed, date):
    return len(parsed[date]["tags"]) + len(parsed[date]["adult"]) + len(parsed[date]["minor"]) + len(parsed[date]["unknown"])

def generate_new_user_graph(logger, time_range=None):
    con = sqlite3.connect(db.validations_db_file)
    cur = con.cursor()

    min_date = datetime.min if time_range is None else datetime.datetime.now() - datetime.timedelta(days=time_range)

    data = cur.execute("SELECT * FROM age_data WHERE date > :date", {"date": min_date}).fetchall()
    con.close()
    
    logger.debug(f"[GRAPHLYTICS] Got {len(data)} datapoints")

    dates = sorted(list(set([datetime.datetime.strptime(entry[2], '%Y-%m-%d %H:%M:%S.%f').date() for entry in data])))
    parsed = {x: {"tags": [], "adult": [], "minor": [], "unknown": []} for x in dates}

    for user, age, date in data:
        parsed[datetime.datetime.strptime(date, '%Y-%m-%d %H:%M:%S.%f').date()][_get_label(age)] += [user] # TODO do we need all users? or just a count?

    split = {'tags': [], 'adult': [], 'minor': [], 'unknown': []}

    for date in dates:
        split['tags'] += [parsed[date]['tags']]
        split['adult'] += [parsed[date]['adult']]
        split['minor'] += [parsed[date]['minor']]
        split['unknown'] += [parsed[date]['unknown']]

    split = {'tags': [], 'adult': [], 'minor': [], 'unknown': []}

    start_date = min(dates)
    day_count = (max(dates) - min(dates)).days + 1
    i = 0
    for single_date in (start_date + datetime.timedelta(n) for n in range(day_count)):
        logger.debug(f"[GRAPHLYTICS] {i} Single date = {single_date}")
        if single_date in dates:
            logger.debug(f"[GRAPHLYTICS] {i} Found {single_date}")
            split['tags'] += [parsed[single_date]['tags']]
            split['adult'] += [parsed[single_date]['adult']]
            split['minor'] += [parsed[single_date]['minor']]
            split['unknown'] += [parsed[single_date]['unknown']]
        else:
            logger.debug(f"[GRAPHLYTICS] {i} NOT found {single_date}")
            split['tags'] += [[]]
            split['adult'] += [[]]
            split['minor'] += [[]]
            split['unknown'] += [[]]
        i += 1

    fig, ax = plt.subplots()

    start_date = min(dates)
    day_count = (max(dates) - min(dates)).days + 1

    width = 0.75
    xaxis = [str(d) for d in list(start_date + datetime.timedelta(n) for n in range(day_count))]
    print(len(xaxis))
    print(str(xaxis))
    bottoms = [0 for _ in xaxis]
    bar = [len(x) for x in split['unknown']]
    print(str(bar))
    print(str(bottoms))
    ax.bar(xaxis, bar, width, bottom=bottoms, label="Unknown", color="grey")
    for i in range(len(xaxis)):
        bottoms[i] += bar[i]
    bar = [len(x) for x in split['minor']]
    print(str(bar))
    print(str(bottoms))
    ax.bar(xaxis, bar, width, bottom=bottoms, label="Minors", color="red")
    for i in range(len(xaxis)):
        bottoms[i] += bar[i]
    bar = [len(x) for x in split['tags']]
    print(str(bar))
    print(str(bottoms))
    ax.bar(xaxis, bar, width, bottom=bottoms, label="Tags", color="darkgreen")
    for i in range(len(xaxis)):
        bottoms[i] += bar[i]
    bar = [len(x) for x in split['adult']]
    print(str(bar))
    print(str(bottoms))
    ax.bar(xaxis, bar, width, bottom=bottoms, label="Adults", color="green")

    ax.set_ylabel('Users')
    ax.set_title('New users daily')
    plt.xticks(rotation=90)
    ax.legend()

    name = "trash/" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=string_len)) + ".png"
    plt.savefig(name)
    return name