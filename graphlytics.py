import datetime
import discord
import country_converter as coco
import geopandas as gpd
import os
import random
import sqlite3
import string
import typing
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

import db
import botlogger
import bot_utils
import kinks

logger = botlogger.get_logger(__name__)

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

def generate_world_heatmap(cmap: str = 'plasma'):
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

@discord.app_commands.guild_only()
class Analytics(discord.app_commands.Group):
    def __init__(self, utils: bot_utils.utils):
        super().__init__()
        self.utils = utils
        self.generator = AnalyticsGenerator()

    async def _handle_internal(self, interaction: discord.Interaction, ensure: typing.Callable, generator: typing.Callable, *gen_args):
        await self.utils.safe_defer(interaction)

        if not await ensure(interaction): return

        report_name = generator(*gen_args)
        logger.debug(f"report_name={report_name}")
        report_file = discord.File(report_name, filename=f"user_report.png")

        await self.utils.safe_send(interaction, content=f"Here you go~", file=report_file, is_followup=True)

        os.remove(report_name)

    @discord.app_commands.command(description='Get analytics data for new users')
    @discord.app_commands.describe(range='Max days to fetch')
    async def joiners_and_leavers(self, interaction: discord.Interaction, range: typing.Optional[int] = 7):
        logger.info(f"{interaction.user} requested joiners_and_leavers")
        await self._handle_internal(interaction, self.utils.ensure_divine, self.generator.generate_new_user_graph, range)

    @discord.app_commands.command(description='Get analytics data for user activity (text channels only)')
    @discord.app_commands.describe(range='Max days to fetch')
    async def active_users(self, interaction: discord.Interaction, range: typing.Optional[int] = 7):
        logger.info(f"{interaction.user} requested active_users")
        await self._handle_internal(interaction, self.utils.ensure_divine, self.generator.generate_active_users_graph, range)

    @discord.app_commands.command(description='Get analytics data for user VC activity')
    @discord.app_commands.describe(range='Max days to fetch')
    async def active_vc_users(self, interaction: discord.Interaction, range: typing.Optional[int] = 7):
        logger.info(f"{interaction.user} requested active_vc_users")
        await self._handle_internal(interaction, self.utils.ensure_divine, self.generator.generate_active_vc_users_graph, range)

    @discord.app_commands.command(description='Get analytics data for VC activity duration')
    @discord.app_commands.describe(range='Max days to fetch')
    async def vc_activity_duration(self, interaction: discord.Interaction, range: typing.Optional[int] = 7):
        logger.info(f"{interaction.user} requested vc_activity_duration")
        await self._handle_internal(interaction, self.utils.ensure_divine, self.generator.generate_vc_activity_time_graph, range)

    @discord.app_commands.command(description='Get analytics data for commands activity')
    @discord.app_commands.describe(range='Max days to fetch')
    async def command_usage(self, interaction: discord.Interaction, range: typing.Optional[int] = 7):
        logger.info(f"{interaction.user} requested command_usage")
        await self._handle_internal(interaction, self.utils.ensure_divine, self.generator.generate_distinct_commands_graph, range)

    @discord.app_commands.command(description='Get analytics data for command user activity')
    @discord.app_commands.describe(range='Max days to fetch')
    async def command_users(self, interaction: discord.Interaction, range: typing.Optional[int] = 7):
        logger.info(f"{interaction.user} requested command_usage")
        await self._handle_internal(interaction, self.utils.ensure_divine, self.generator.generate_command_users_graph, range)

class AnalyticsGenerator():
    def _min_date(self, time_range: int):
        today = datetime.datetime.today()
        min_date = datetime.datetime.min if time_range is None else today - datetime.timedelta(days=time_range)
        min_date_str = datetime.datetime.strftime(min_date, '%Y-%m-%d')
        return today, min_date, min_date_str

    def generate_new_user_graph(self, time_range: int=None):
        today, min_date, min_date_str = self._min_date(time_range)

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
            WHERE date(substr(created_at, 1, 10)) > date('{min_date_str}')
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
            WHERE date(substr(created_at, 1, 10)) > date('{min_date_str}')
            GROUP BY tag''').fetchall()}
        con.close()
        
        logger = botlogger.get_logger(__name__)
        logger.debug(f"[GRAPHLYTICS] Got {len(joiners_data)}/{len(leavers_data)} datapoints (expected max {time_range * len(conditionals)})")

        day_count = (today - min_date).days + 1 # FIXME this '+ 1' might be causing first value = 0?
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

        joiners_split = {k: np.array(joiners_split[k][1:]) for k in joiners_split} # FIXME first value is always 0
        leavers_split = {k: -1 * np.array(leavers_split[k][1:]) for k in leavers_split} # FIXME first value is always 0

        fig, ax = plt.subplots()
        width = 0.75
        xaxis = [datetime.datetime.strftime(d, '%Y-%m-%d') for d in list(min_date + datetime.timedelta(n) for n in range(day_count))][1:] # FIXME first value is always 0

        bottoms = np.zeros(day_count - 1) # FIXME first value is always 0
        for key in joiners_split:
            ax.bar(xaxis, joiners_split[key], width, bottom=bottoms, label=key, color=colors[key])
            bottoms += joiners_split[key]

        bottoms = np.zeros(day_count - 1) # FIXME first value is always 0
        for key in leavers_split:
            ax.bar(xaxis, leavers_split[key], width, bottom=bottoms, label=f"{key} quit", color=neg_colors[key])
            bottoms += leavers_split[key]
        ax.set_ylabel('Users')
        ax.set_title('Daily users gained/lost')
        plt.xticks(rotation=90)
        fig.set_size_inches(15, 10)
        ax.legend()

        name = "trash/" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=string_len)) + ".png"
        plt.savefig(name)
        return name

    def generate_active_users_graph(self, time_range=None):
        today, min_date, min_date_str = self._min_date(time_range)

        con = sqlite3.connect(db.activity_db_file)
        cur = con.cursor()
        raw_activity_data = {line[1]: line[0] for line in cur.execute(f"""
            SELECT
                count(distinct user) as "active_members",
                date(substr(date, 1, 10)) as "created_at"
            FROM messages 
            WHERE date(substr(date, 1, 10)) > date('{min_date_str}')
            GROUP BY 
                date(substr(date, 1, 10))
            ORDER BY
                created_at DESC
            """).fetchall()}
        con.close()
        
        logger.debug(f"[GRAPHLYTICS] Got {len(raw_activity_data)} datapoints (expected max {time_range})")

        day_count = (today - min_date).days + 1 # FIXME this '+ 1' might be causing first value = 0?
        activity_data = []
        for single_date in (min_date + datetime.timedelta(n) for n in range(day_count)):
            key = datetime.datetime.strftime(single_date, '%Y-%m-%d')
            activity_data += [key in raw_activity_data and raw_activity_data[key] or 0]

        fig, ax = plt.subplots()
        xaxis = [datetime.datetime.strftime(d, '%Y-%m-%d') for d in list(min_date + datetime.timedelta(n) for n in range(day_count))][1:] # FIXME first value is always 0
        activity_data = activity_data[1:] # FIXME first value is always 0

        ax.plot(xaxis, activity_data)
        ax.set_ylabel('Users')
        ax.set_title('Daily active users')
        plt.xticks(rotation=90)
        fig.set_size_inches(15, 10)
        ax.set_ylim(ymin=0)
        ax.legend()

        name = "trash/" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=string_len)) + ".png"
        plt.savefig(name)
        return name

    def generate_active_vc_users_graph(self, time_range=None):
        today, min_date, min_date_str = self._min_date(time_range)

        con = sqlite3.connect(db.vc_activity_db_file)
        cur = con.cursor()
        raw_activity_data = {line[1]: line[0] for line in cur.execute(f"""
            SELECT
                COUNT(DISTINCT user),
                day
            FROM sessions 
            WHERE DATE(day) > DATE('{min_date_str}')
            GROUP BY 
                day
            ORDER BY
                day DESC
            """).fetchall()}
        con.close()
        
        logger.debug(f"[GRAPHLYTICS] Got {len(raw_activity_data)} datapoints (expected max {time_range})")

        day_count = (today - min_date).days + 1 # FIXME this '+ 1' might be causing first value = 0?
        activity_data = []
        for single_date in (min_date + datetime.timedelta(n) for n in range(day_count)):
            key = datetime.datetime.strftime(single_date, '%Y-%m-%d')
            activity_data += [key in raw_activity_data and raw_activity_data[key] or 0]

        fig, ax = plt.subplots()
        xaxis = [datetime.datetime.strftime(d, '%Y-%m-%d') for d in list(min_date + datetime.timedelta(n) for n in range(day_count))][1:] # FIXME first value is always 0
        activity_data = activity_data[1:] # FIXME first value is always 0

        ax.plot(xaxis, activity_data)
        ax.set_ylabel('Users')
        ax.set_title('Daily active VC users')
        plt.xticks(rotation=90)
        fig.set_size_inches(15, 10)
        ax.set_ylim(ymin=0)
        ax.legend()

        name = "trash/" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=string_len)) + ".png"
        plt.savefig(name)
        return name

    def generate_vc_activity_time_graph(self, time_range=None):
        today, min_date, min_date_str = self._min_date(time_range)
        _activities = ['video', 'stream', 'voice']
        colors = {
            'video': 'red',
            'stream': 'green',
            'voice': 'blue'
        }

        con = sqlite3.connect(db.vc_activity_db_file)
        cur = con.cursor()
        raw_data = {line[1]: line[0] for line in cur.execute(f"""
            SELECT
                SUM(duration)/60.,
                day || '_' || activity AS tag
            FROM sessions 
            WHERE date(day) > date('{min_date_str}')
            GROUP BY 
                tag
            ORDER BY
                day DESC
            """).fetchall()}
        con.close()
        
        logger.debug(f"[GRAPHLYTICS] Got {len(raw_data)} datapoints (expected max {time_range * len(_activities)})")

        day_count = (today - min_date).days + 1 # FIXME this '+ 1' might be causing first value = 0?
        i = 0
        data_split = {x: [] for x in _activities}
        for single_date in (min_date + datetime.timedelta(n) for n in range(day_count)):
            for tag in _activities:
                key = f"{datetime.datetime.strftime(single_date, '%Y-%m-%d')}_{tag}"
                # print(key)
                data_split[tag] += [key in raw_data and raw_data[key] or 0]
            i += 1

        data_split = {k: np.array(data_split[k][1:]) for k in data_split} # FIXME first value is always 0

        fig, ax = plt.subplots()
        width = 0.75
        xaxis = [datetime.datetime.strftime(d, '%Y-%m-%d') for d in list(min_date + datetime.timedelta(n) for n in range(day_count))][1:] # FIXME first value is always 0

        bottoms = np.zeros(day_count - 1) # FIXME first value is always 0
        for key in _activities[::-1]:
            ax.bar(xaxis, data_split[key], width, bottom=bottoms, label=key, color=colors[key])
            bottoms += data_split[key]

        ax.set_ylabel('Usage [minutes]')
        ax.set_title('Combined VC usage per activity')
        plt.xticks(rotation=90)
        fig.set_size_inches(15, 10)
        ax.set_ylim(ymin=0)
        ax.legend()

        name = "trash/" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=string_len)) + ".png"
        plt.savefig(name)
        return name

    def generate_distinct_commands_graph(self, time_range=None):
        today, min_date, min_date_str = self._min_date(time_range)

        con = sqlite3.connect(db.cmds_analytics_db_file)
        cur = con.cursor()
        raw_data = {x[0]: x[1] for x in cur.execute(f'''
            SELECT 
                command || '@' || date(substr(created_at, 1, 10)) as tag,
                count(*) as "issued_commands"
            FROM commands 
            WHERE failed=FALSE AND date(substr(created_at, 1, 10)) > date('{min_date_str}')
            GROUP BY 
                date(substr(created_at, 1, 10)),
                command
            ORDER BY 
				date(substr(created_at, 1, 10))''').fetchall()}
        con.close()

        """
        raw_data = {
            'cmd_1@date_1': amount1,
            'cmd_2@date_1': amount2,
            'cmd_1@date_2': amount3,
            'cmd_2@date_3': amount4,
            ...
        }
        """
        
        logger = botlogger.get_logger(__name__)
        logger.debug(f"[GRAPHLYTICS] Got {len(raw_data)} datapoints")

        day_count = (today - min_date).days + 1 # FIXME this '+ 1' might be causing first value = 0?
        i = 0
        data_split = {}
        for tag in raw_data:
            tag_cmd, tag_date = tag.split('@')
            if tag_cmd not in data_split:
                data_split[tag_cmd] = {}
            data_split[tag_cmd][tag_date] = raw_data[tag]
        
        """
        data_split = {
            'cmd_1': {
                'date_1': amount1,
                'date_2': amount2,
                ...
            },
            'cmd_2': {
                'date_1': amount3,
                'date_3': amount4,
                ...
            },
            ...
        }
        """

        data_filled = {}
        for cmd in data_split:
            data_filled[cmd] = []
            for single_date in (min_date + datetime.timedelta(n) for n in range(day_count)):
                date_str = datetime.datetime.strftime(single_date, '%Y-%m-%d')
                data_filled[cmd] += [date_str in data_split[cmd] and data_split[cmd][date_str] or 0]
        
        """
        data_filled = {
            'cmd_1': [amount1, amount2, 0, ...],
            'cmd_2': [amount3, 0, amount4, ...],
            ...
        }
        """

        # Merge kink commands
        # TODO maybe generate this automatically from the bot's command tree?
        merge_rules = {
            'kink': [kinks.safe_name(cat) for cat in kinks.kinklist]
        }
        data_cleaned = {}
        # logger.debug(f"[generate_distinct_commands_graph] Cleaning {data_filled}")
        # logger.debug(f"[generate_distinct_commands_graph] Merge rules = {merge_rules}")
        for cmd in data_filled:
            merged = False
            for rule in merge_rules:
                if cmd in merge_rules[rule]:
                    # logger.debug(f"[generate_distinct_commands_graph] Found {cmd} as mergeable for {rule}")
                    if rule not in data_cleaned:
                        data_cleaned[rule] = np.zeros(day_count - 1) # FIXME first value is always 0
                    data_cleaned[rule] += np.array(data_filled[cmd][1:]) # FIXME first value is always 0
                    merged = True
                    break
            if not merged:
                # logger.debug(f"[generate_distinct_commands_graph] Could not merge {cmd}")
                if cmd not in data_cleaned:
                    data_cleaned[cmd] = np.zeros(day_count - 1) # FIXME first value is always 0
                data_cleaned[cmd] += np.array(data_filled[cmd][1:]) # FIXME first value is always 0

        fig, ax = plt.subplots()
        width = 0.75
        xaxis = [datetime.datetime.strftime(d, '%Y-%m-%d') for d in list(min_date + datetime.timedelta(n) for n in range(day_count))][1:] # FIXME first value is always 0

        bottoms = np.zeros(day_count - 1) # FIXME first value is always 0
        for cmd in data_cleaned:
            ax.bar(xaxis, data_cleaned[cmd], width, bottom=bottoms, label=cmd)
            bottoms += data_cleaned[cmd]

        ax.set_ylabel('Uses')
        ax.set_title('Daily command usage')
        plt.xticks(rotation=90)
        fig.set_size_inches(15, 10)

        handles, labels = ax.get_legend_handles_labels()
        ax.legend(handles[::-1], labels[::-1], title='Commands', loc='upper left')
        # ax.legend()

        name = "trash/" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=string_len)) + ".png"
        plt.savefig(name)
        return name

    def generate_command_users_graph(self, time_range=None):
        today, min_date, min_date_str = self._min_date(time_range)

        con = sqlite3.connect(db.cmds_analytics_db_file)
        cur = con.cursor()
        raw_data = {x[0]: x[1] for x in cur.execute(f'''
            SELECT 
                date(substr(created_at, 1, 10)) as "created_at",
                count(distinct user) as "distinct_users"
            FROM commands 
            WHERE failed=FALSE AND date(substr(created_at, 1, 10)) > date('{min_date_str}')
            GROUP BY 
                date(substr(created_at, 1, 10))
            ORDER BY
                created_at DESC''').fetchall()}
        con.close()

        """
        raw_data = {
            'date_1': amount1,
            'date_1': amount2,
            'date_2': amount3,
            'date_3': amount4,
            ...
        }
        """
        
        logger.debug(f"[GRAPHLYTICS] Got {len(raw_data)} datapoints (expected max {time_range})")

        day_count = (today - min_date).days + 1 # FIXME this '+ 1' might be causing first value = 0?
        activity_data = []
        for single_date in (min_date + datetime.timedelta(n) for n in range(day_count)):
            key = datetime.datetime.strftime(single_date, '%Y-%m-%d')
            activity_data += [key in raw_data and raw_data[key] or 0]

        fig, ax = plt.subplots()
        xaxis = [datetime.datetime.strftime(d, '%Y-%m-%d') for d in list(min_date + datetime.timedelta(n) for n in range(day_count))][1:] # FIXME first value is always 0
        activity_data = activity_data[1:] # FIXME first value is always 0

        ax.plot(xaxis, activity_data)
        ax.set_ylabel('Users')
        ax.set_title('Daily command users')
        plt.xticks(rotation=90)
        fig.set_size_inches(15, 10)
        ax.legend()

        name = "trash/" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=string_len)) + ".png"
        plt.savefig(name)
        return name
