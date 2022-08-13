import asyncio
import discord
from discord.member import Member
import discord_slash
import logging
import os
import sys
from discord import flags
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
from discord.ext import commands
from discord_slash import SlashCommand, SlashContext
import sqlite3
import time
import re

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
if TOKEN is None:
    print("DISCORD_TOKEN env var not set! Exiting")
    exit(1)

LENIENCY_TIME_S = 30 # time to reply
LENIENCY_COUNT = 3 # messages before ban

bot_home = os.getenv("BOT_HOME") or os.getcwd()

validations_db_file = bot_home + 'validations.db'

_ids = os.getenv('GUILD_IDS') or ""
_guild_ids = [int(id) for id in _ids.split('.') if id != ""]
guild_ids = _guild_ids if len(_guild_ids) else None
_ids = os.getenv('CHANNEL_IDS') or ""
_channel_ids = [int(id) for id in _ids.split('.') if id != ""]
channel_ids = _channel_ids if len(_channel_ids) else None

bot = commands.Bot(command_prefix="/", self_bot=True, intents=discord.Intents.all())
slash = SlashCommand(bot, sync_commands=True)
app = Flask(__name__)
app.logger.root.setLevel(logging.getLevelName(os.getenv('LOG_LEVEL') or 'DEBUG'))
app.logger.addHandler(logging.StreamHandler(sys.stdout))

app.logger.info(f"channel ID = {channel_ids[0]}")
app.logger.info(f"guild ID = {channel_ids[0]}")

# Age regex
age_prog = re.compile("(18|19|[2-9][0-9])") # 18, 19 or 20+
minor_prog = re.compile("([0-9]|1[0-7])") # 0-9 or 10-17

# Initialize db
if not os.path.exists(validations_db_file):
    con = sqlite3.connect(validations_db_file)
    cur = con.cursor()
    cur.execute(f"""
    CREATE TABLE validations (
        user int NOT NULL, 
        leniency int NOT NULL, 
        PRIMARY KEY (user)
    );""")
    con.commit()
    con.close()

def get_leniency(user):
    con = sqlite3.connect(validations_db_file)
    cur = con.cursor()
    res = cur.execute("SELECT * FROM validations WHERE user = :id", {"id": user}).fetchone()
    con.close()
    if res is None: return None
    return int(res[1])

def create_entry(user):
    con = sqlite3.connect(validations_db_file)
    cur = con.cursor()
    res = cur.execute("INSERT INTO validations VALUES (?, ?)", [user, LENIENCY_COUNT])
    con.commit()
    con.close()

def decr_leniency(user):
    con = sqlite3.connect(validations_db_file)
    cur = con.cursor()
    res = cur.execute("UPDATE validations SET leniency=leniency - 1 WHERE user=:id", {"id": user})
    con.commit()
    con.close()

def delete_entry(user):
    try:
        con = sqlite3.connect(validations_db_file)
        cur = con.cursor()
        res = cur.execute("DELETE FROM validations WHERE user=:id", {"id": user})
        con.commit()
        con.close()
    except:
        pass

async def do_ban(channel, user):
    await channel.guild.ban(user, reason="minor")
    # await channel.send(f"Ban {user.mention} | minor")

@bot.event
async def on_ready():
    app.logger.info(f"{bot.user} has connected to Discord")

@bot.event
async def on_message(msg: discord.Message):
    if msg.author.id == bot.user.id or len(msg.content) == 0: return
    app.logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} says \"{msg.content}\"")
    leniency = get_leniency(msg.author.id)
    if leniency is not None and leniency > 0:
        app.logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} is still on watchlist, parsing message")
        if is_valid_age(msg.content):
            app.logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} said a valid age")
            delete_entry(msg.author.id)
            await msg.channel.send(f"Thank you {msg.author.mention}! Welcome to the server!")
        elif is_insta_ban(msg.content):
            app.logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} said a non-valid age")
            await do_ban(msg.channel, msg.author)
            delete_entry(msg.author.id)
        elif leniency > 0:
            app.logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} said a non-valid message")
            decr_leniency(msg.author.id)
        else:
            app.logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} is out of messages")
            await do_ban(msg.channel, msg.author)
            delete_entry(msg.author.id)

def is_valid_age(msg: str):
    return age_prog.search(msg) is not None

def is_insta_ban(msg: str): # TODO add filters? racism, etc.
    return minor_prog.search(msg) is not None

@bot.event
async def on_member_join(member: discord.Member):
    if member.id == bot.user.id: return
    channel = bot.get_channel(channel_ids[0])
    app.logger.debug(f"[{channel.guild.name} / {channel}] {member} just joined")

    create_entry(member.id)
    await channel.send(f"Hello {member.mention}! May I ask your age, pls?")

    await asyncio.sleep(LENIENCY_TIME_S)

    # check
    leniency = get_leniency(member.id)
    if (leniency is not None):
        app.logger.debug(f"[{channel.guild.name} / {channel}] Leniency data found")
        await do_ban(member)
    else:
        app.logger.debug(f"[{channel.guild.name} / {channel}] Leniency data NOT found, user OK")

    delete_entry(member.id)
    
    app.logger.debug(f"[{channel.guild.name} / {channel}] Exit on_member_join")

bot.run(TOKEN)
