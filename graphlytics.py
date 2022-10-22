import datetime
import country_converter as coco
import geopandas as gpd
import random
import sqlite3
import string
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

import db
import botlogger

string_len = 20

cmaps = [   'viridis', 'plasma', 'inferno', 'magma', 'cividis',
            'Greys', 'Purples', 'Blues', 'Greens', 'Oranges', 'Reds',
            'YlOrBr', 'YlOrRd', 'OrRd', 'PuRd', 'RdPu', 'BuPu',
            'GnBu', 'PuBu', 'YlGnBu', 'PuBuGn', 'BuGn', 'YlGn',
            'binary', 'gist_yarg', 'gist_gray', 'gray', 'bone', 'pink',
            'spring', 'summer', 'autumn', 'winter', 'cool', 'Wistia',
            'hot', 'afmhot', 'gist_heat', 'copper',
            'PiYG', 'PRGn', 'BrBG', 'PuOr', 'RdGy', 'RdBu',
            'RdYlBu', 'RdYlGn', 'Spectral', 'coolwarm', 'bwr', 'seismic',
            'twilight', 'twilight_shifted', 'hsv',
            'Pastel1', 'Pastel2', 'Paired', 'Accent',
            'Dark2', 'Set1', 'Set2', 'Set3',
            'tab10', 'tab20', 'tab20b', 'tab20c',
            'flag', 'prism', 'ocean', 'gist_earth', 'terrain', 'gist_stern',
            'gnuplot', 'gnuplot2', 'CMRmap', 'cubehelix', 'brg',
            'gist_rainbow', 'rainbow', 'jet', 'turbo', 'nipy_spectral',
            'gist_ncar']

def _get_label(age):
    if age > 100: return "tags"
    if age > 17: return "adult"
    if age > 0: return "minor"
    return "unknown"

def _get_daily(parsed, date):
    return len(parsed[date]["tags"]) + len(parsed[date]["adult"]) + len(parsed[date]["minor"]) + len(parsed[date]["unknown"])

def generate_new_user_graph(time_range=None):
    con = sqlite3.connect(db.validations_db_file)
    cur = con.cursor()

    min_date = datetime.datetime.min if time_range is None else datetime.datetime.now() - datetime.timedelta(days=time_range)

    # TODO a lot of this processing can be done with better SQL queries
    data = cur.execute("SELECT * FROM age_data WHERE date > :date", {"date": min_date}).fetchall()
    con.close()
    
    logger = botlogger.get_logger(__name__)
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
    bottoms = [0 for _ in xaxis]
    bar = [len(x) for x in split['unknown']]
    ax.bar(xaxis, bar, width, bottom=bottoms, label="Unknown", color="grey")
    for i in range(len(xaxis)):
        bottoms[i] += bar[i]
    bar = [len(x) for x in split['minor']]
    ax.bar(xaxis, bar, width, bottom=bottoms, label="Minors", color="red")
    for i in range(len(xaxis)):
        bottoms[i] += bar[i]
    bar = [len(x) for x in split['tags']]
    ax.bar(xaxis, bar, width, bottom=bottoms, label="Tags", color="darkgreen")
    for i in range(len(xaxis)):
        bottoms[i] += bar[i]
    bar = [len(x) for x in split['adult']]
    ax.bar(xaxis, bar, width, bottom=bottoms, label="Adults", color="green")

    ax.set_ylabel('Users')
    ax.set_title('New users daily')
    plt.xticks(rotation=90)
    ax.legend()

    name = "trash/" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=string_len)) + ".png"
    plt.savefig(name)
    return name

def _fib(until):
    res = [0, 1]
    while res[-1] < until:
        res += [res[-1] + res[-2]]
    if len(res) > 2:
        del(res[1]) # remove extra copy of 1 (make sure we keep at least 1 - edge case)
    if res[-1] != until:
        res += [until] # make sure we have the max value
    return res

def generate_world_heatmap(cmap: str = 'gist_ncar'):
    if cmap not in cmaps: return None

    con = sqlite3.connect(db.worldmap_db_file)
    cur = con.cursor()
    data = cur.execute("SELECT location, COUNT(location) FROM world GROUP BY location").fetchall()

    # Setting the path to the shapefile
    SHAPEFILE = 'data/shapefiles/worldmap/ne_10m_admin_0_countries.shp'

    # Read shapefile using Geopandas
    geo_df = gpd.read_file(SHAPEFILE)[['ADMIN', 'ADM0_A3', 'geometry']]

    # Rename columns.
    geo_df.columns = ['country', 'country_code', 'geometry']
    
    # Drop row for 'Antarctica'. It takes a lot of space in the map and is not of much use
    geo_df = geo_df.drop(geo_df.loc[geo_df['country'] == 'Antarctica'].index)

    # Get ISO3 names for the countries
    iso3_codes_list = coco.convert(names=geo_df['country'].to_list(), to='ISO3', not_found='NULL')

    # Add the list with iso2 codes to the dataframe
    geo_df['iso3_code'] = iso3_codes_list

    # Default is 0 users per country
    geo_df['users'] = 0
    
    # Add the values we have from the DB
    for line in data:
        loc, users = line[0], line[1]
        geo_df.loc[geo_df['iso3_code'] == loc, 'users'] = users

    title = 'World users'
    col = 'users'
    vmin = geo_df[col].min()
    vmax = geo_df[col].max()

    # Create figure and axes for Matplotlib
    fig, ax = plt.subplots(1, figsize=(20, 8))

    # Remove the axis
    ax.axis('off')
    geo_df.plot(column=col, ax=ax, edgecolor='0.8', linewidth=1, cmap=cmap)

    # Add a title
    ax.set_title(title, fontdict={'fontsize': '25', 'fontweight': '3'})

    # Create an annotation for the data source
    # ax.annotate(source, xy=(0.1, .08), xycoords='figure fraction', horizontalalignment='left', 
    #             verticalalignment='bottom', fontsize=10)
                
    # Create colorbar as a legend
    sm = plt.cm.ScalarMappable(norm=plt.Normalize(vmin=vmin, vmax=vmax), cmap=cmap)

    # Empty array for the data range
    sm._A = []

    # Add the colorbar to the figure
    ticks = sorted(set([0] + [line[1] for line in data]))
    cbaxes = fig.add_axes([0.15, 0.25, 0.01, 0.4])
    cbar = fig.colorbar(sm, cax=cbaxes, ticks=ticks)

    name = "trash/" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=string_len)) + ".png"
    plt.savefig(name)
    return name
