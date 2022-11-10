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
            

conditionals = {
    '18-19': 'WHERE age = 1005699733353922611 OR age BETWEEN 18 AND 19',
    '20-24': 'WHERE age = 1005699809270833202 OR age BETWEEN 20 AND 24',
    '25-29': 'WHERE age = 1005699867873660979 OR age BETWEEN 25 AND 29',
    '30+': 'WHERE age = 1005700845159063552 OR age >= 30',
    'minor': 'WHERE age > 0 AND age < 18',
    'unknown': 'WHERE age < 1'
}

colors = {
    '18-19': 'green',
    '20-24': 'green',
    '25-29': 'green',
    '30+': 'green',
    'minor': 'red',
    'unknown': 'darkgrey'
}
neg_colors = {
    '18-19': 'darkgreen',
    '20-24': 'darkgreen',
    '25-29': 'darkgreen',
    '30+': 'darkgreen',
    'minor': 'darkred',
    'unknown': 'grey'
}

def _get_label(age):
    if age > 100: return "tags"
    if age > 17: return "adult"
    if age > 0: return "minor"
    return "unknown"

def _get_daily(parsed, date):
    return len(parsed[date]["tags"]) + len(parsed[date]["adult"]) + len(parsed[date]["minor"]) + len(parsed[date]["unknown"])

def generate_new_user_graph(time_range=None):
    today = datetime.datetime.today()
    min_date = datetime.datetime.min if time_range is None else today - datetime.timedelta(days=time_range)
    min_date_str = datetime.datetime.strftime(min_date, '%Y-%m-%d')

    con = sqlite3.connect(db.member_analytics_db_file)
    cur = con.cursor()
    joiners_data = {x[1]: x[0] for x in cur.execute(f'''
        SELECT
            count(*) as amount, 
            CASE
                WHEN age = 1005699733353922611 OR age BETWEEN 18 AND 19 THEN "18-19"
                WHEN age = 1005699809270833202 OR age BETWEEN 20 AND 24 THEN "20-24"
                WHEN age = 1005699867873660979 OR age BETWEEN 25 AND 29 THEN "25-29"
                WHEN age = 1005700845159063552 OR age >= 30 THEN "30+"
                WHEN age > 0 AND age < 18 THEN "minor"
                ELSE "unknown"
            END || '-' || date(substr(created_at, 1, 10)) AS tag
        FROM joiners 
        WHERE date(substr(date, 1, 10)) > date('{min_date_str}')
        GROUP BY tag''').fetchall()}
    leavers_data = {x[1]: x[0] for x in cur.execute(f'''
        SELECT
            count(*) as amount, 
            CASE
                WHEN age = 1005699733353922611 OR age BETWEEN 18 AND 19 THEN "18-19"
                WHEN age = 1005699809270833202 OR age BETWEEN 20 AND 24 THEN "20-24"
                WHEN age = 1005699867873660979 OR age BETWEEN 25 AND 29 THEN "25-29"
                WHEN age = 1005700845159063552 OR age >= 30 THEN "30+"
                WHEN age > 0 AND age < 18 THEN "minor"
                ELSE "unknown"
            END || '-' || date(substr(created_at, 1, 10)) AS tag
        FROM leavers 
        WHERE date(substr(date, 1, 10)) > date('{min_date_str}')
        GROUP BY tag''').fetchall()}
    con.close()
    
    logger = botlogger.get_logger(__name__)
    logger.debug(f"[GRAPHLYTICS] Got {len(joiners_data)}/{len(leavers_data)} datapoints (expected max {time_range * len(conditionals)})")

    day_count = (today - min_date).days + 1
    i = 0
    joiners_split = {x: [] for x in conditionals}
    leavers_split = {x: [] for x in conditionals}
    for single_date in (min_date + datetime.timedelta(n) for n in range(day_count)):
        for tag in conditionals:
            key = f"{tag}-{datetime.datetime.strftime(single_date, '%Y-%m-%d')}"
            # print(key)
            joiners_split[tag] += [key in joiners_data and joiners_data[key] or 0]
            leavers_split[tag] += [key in leavers_data and leavers_data[key] or 0]
        i += 1

    joiners_split = {k: np.array(joiners_split[k]) for k in joiners_split}
    leavers_split = {k: -1 * np.array(leavers_split[k]) for k in leavers_split}

    fig, ax = plt.subplots()
    width = 0.75
    xaxis = [datetime.datetime.strftime(d, '%Y-%m-%d') for d in list(min_date + datetime.timedelta(n) for n in range(day_count))]

    bottoms = np.zeros(day_count)
    for key in joiners_split:
        ax.bar(xaxis, joiners_split[key], width, bottom=bottoms, label=key, color=colors[key])
        bottoms += joiners_split[key]

    bottoms = np.zeros(day_count)
    for key in leavers_split:
        data = np.minimum(leavers_split[key], -1 * joiners_split[key]) if key in ['unknown', 'minor'] else leavers_split[key]
        ax.bar(xaxis, data, width, bottom=bottoms, label=f"{key} quit", color=neg_colors[key])
        bottoms += data
    ax.set_ylabel('Users')
    ax.set_title('Daily users gained/lost')
    plt.xticks(rotation=90)
    fig.set_size_inches(15, 10)
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
