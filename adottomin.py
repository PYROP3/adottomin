import asyncio
import datetime
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

LENIENCY_TIME_S = 1200 # time to reply
LENIENCY_COUNT = 3 # messages before ban

REASON_MINOR = "minor"
REASON_TIMEOUT = "did not say age"
MSG_GREETING = "Hello {}! May I ask your age, pls?"
MSG_WELCOME = "Thank you {}! Welcome to the server!"

bot_home = os.getenv("BOT_HOME") or os.getcwd()

validations_version = 1
validations_db_file = bot_home + f'validations_v{validations_version}.db'

_ids = os.getenv('GUILD_IDS') or ""
_guild_ids = [int(id) for id in _ids.split('.') if id != ""]
guild_ids = _guild_ids if len(_guild_ids) else None
_ids = os.getenv('CHANNEL_IDS') or ""
_channel_ids = [int(id) for id in _ids.split('.') if id != ""]
channel_ids = _channel_ids if len(_channel_ids) else None
_ids = os.getenv('AGE_ROLE_IDS') or ""
_role_ids = [int(id) for id in _ids.split('.') if id != ""]
role_ids = _role_ids if len(_role_ids) else []
tally_channel = int(os.getenv('TALLY_CHANNEL_ID'))

bot = commands.Bot(command_prefix="/", self_bot=True, intents=discord.Intents.all())
slash = SlashCommand(bot, sync_commands=True)
app = Flask(__name__)
app.logger.root.setLevel(logging.getLevelName(os.getenv('LOG_LEVEL') or 'DEBUG'))
app.logger.addHandler(logging.StreamHandler(sys.stdout))

app.logger.info(f"Channel ID = {channel_ids[0]}")
app.logger.info(f"Guild ID = {guild_ids[0]}")
app.logger.info(f"Role IDs = {role_ids}")
app.logger.info(f"Tallly channel IDs = {tally_channel}")

# Age regex
age_prog = re.compile(r"(18|19|[2-9][0-9])") # 18, 19 or 20+
minor_prog = re.compile(r"(?: |^)\b(1[0-7]|[0-9])\b") # 0-9 or 10-17
minor_prog_2 = re.compile(r"not 18") # 0-9 or 10-17

# Initialize db
if not os.path.exists(validations_db_file):
    con = sqlite3.connect(validations_db_file)
    cur = con.cursor()
    cur.execute('''
    CREATE TABLE validations (
        user int NOT NULL,
        leniency int NOT NULL,
        greeting int NOT NULL,
        PRIMARY KEY (user)
    );''')
    cur.execute('''
    CREATE TABLE kicks (
        user int NOT NULL,
        PRIMARY KEY (user)
    );''')
    cur.execute('''
    CREATE TABLE age_data (
        user int NOT NULL,
        age int NOT NULL,
        date TIMESTAMP,
        PRIMARY KEY (user)
    );''')
    con.commit()
    con.close()

def get_leniency(user):
    con = sqlite3.connect(validations_db_file)
    cur = con.cursor()
    res = cur.execute("SELECT * FROM validations WHERE user = :id", {"id": user}).fetchone()
    con.close()
    if res is None: return None
    return int(res[1])

def create_entry(user, greeting_id):
    con = sqlite3.connect(validations_db_file)
    cur = con.cursor()
    cur.execute("INSERT INTO validations VALUES (?, ?, ?)", [user, LENIENCY_COUNT, greeting_id])
    con.commit()
    con.close()

def decr_leniency(user):
    con = sqlite3.connect(validations_db_file)
    cur = con.cursor()
    cur.execute("UPDATE validations SET leniency=leniency - 1 WHERE user=:id", {"id": user})
    con.commit()
    con.close()

def delete_entry(user):
    try:
        con = sqlite3.connect(validations_db_file)
        cur = con.cursor()
        res = cur.execute("SELECT * FROM validations WHERE user = :id", {"id": user}).fetchone()
        cur.execute("DELETE FROM validations WHERE user=:id", {"id": user})
        con.commit()
        con.close()
        return int(res[2]) # Return greeting ID in case it should be deleted
    except:
        return None

def create_kick(user):
    con = sqlite3.connect(validations_db_file)
    cur = con.cursor()
    try:
        cur.execute("INSERT INTO kicks VALUES (?)", [user])
        con.commit()
    except sqlite3.IntegrityError:
        app.logger.warning(f"Duplicated user id {user} in kicks")
    con.close()

def is_kicked(user):
    try:
        con = sqlite3.connect(validations_db_file)
        cur = con.cursor()
        res = cur.execute("SELECT * FROM kicks WHERE user = :id", {"id": user}).fetchone()
        con.commit()
        con.close()
        return res is not None
    except:
        return False

def remove_kick(user):
    con = sqlite3.connect(validations_db_file)
    cur = con.cursor()
    try:
        cur.execute("DELETE FROM validations WHERE user=:id", {"id": user})
        con.commit()
    except:
        pass
    con.close()

def set_age(user, age, force=False):
    con = sqlite3.connect(validations_db_file)
    cur = con.cursor()
    try:
        cur.execute("INSERT INTO age_data VALUES (?, ?, ?)", [user, age, datetime.datetime.now()])
        con.commit()
    except sqlite3.IntegrityError:
        app.logger.warning(f"Duplicated user id {user} in age_data")
        if force:
            app.logger.debug(f"Updating {user} age in age_data -> {age}")
            cur.execute("UPDATE age_data SET age=:age, date=:date WHERE user=:id", {"id": user, "age": age, "date": datetime.datetime.now()})
            con.commit()
    con.close()

async def do_tally():
    if tally_channel is None: return
    try:
        await bot.get_channel(tally_channel).send(f"x")
    except:
        app.logger.error(f"Failed to tally!")

async def do_ban(channel, user, reason=REASON_MINOR):
    try:
        await channel.guild.ban(user, reason=reason.capitalize())
        await channel.send(f"User {user.mention} banned | {reason.capitalize()}")
        await do_tally()
    except discord.NotFound:
        app.logger.debug(f"User id {user} already left!")
    except:
        app.logger.error(f"Failed to ban user id {user}!")
        # await channel.send(f"Failed to ban user {user.mention} | {reason.capitalize()}")

async def do_kick(channel, user, reason=REASON_TIMEOUT):
    try:
        await channel.guild.kick(user, reason=reason.capitalize())
        await channel.send(f"User {user.mention} kicked | {reason.capitalize()}")
    except discord.NotFound:
        app.logger.debug(f"User id {user} already left!")
    except:
        app.logger.error(f"Failed to kick user id {user}!")
        # await channel.send(f"Failed to kick user {user.mention} | {reason.capitalize()}")

@bot.event
async def on_ready():
    app.logger.info(f"{bot.user} has connected to Discord")

@bot.event
async def on_message(msg: discord.Message):
    if msg.author.id == bot.user.id or len(msg.content) == 0: return
    app.logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} says \"{msg.content}\"")

    await handle_age(msg)

async def handle_age(msg: discord.Message):
    leniency = get_leniency(msg.author.id)
    if leniency is None or leniency < 0: return
    
    app.logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} is still on watchlist, parsing message")
    if is_valid_age(msg.content):
        age = get_age(msg.content)
        app.logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} said a valid age ({age})")
        
        delete_entry(msg.author.id)
        set_age(msg.author.id, age, force=True)

        await msg.channel.send(MSG_WELCOME.format(msg.author.mention))

    elif is_insta_ban(msg.content):
        age = get_ban_age(msg.content)
        app.logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} said a non-valid age ({age})")
        await kick_or_ban(msg.author, msg.channel, age=age, force_ban=True, force_update_age=True, reason=REASON_MINOR)

    elif leniency > 0:
        app.logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} said a non-valid message ({leniency} left)")
        decr_leniency(msg.author.id)

    else:
        app.logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} is out of messages")
        await kick_or_ban(msg.author, msg.channel, reason=REASON_TIMEOUT)

async def kick_or_ban(member, channel, age=-1, force_ban=False, force_update_age=False, reason=REASON_MINOR):
    if force_ban or is_kicked(member.id):
        app.logger.debug(f"[{channel.guild.name} / {channel}] Will ban user (force={force_ban})")
        await do_ban(channel, member, reason=reason)
        remove_kick(member.id)

    else:
        app.logger.debug(f"[{channel.guild.name} / {channel}] User was NOT previously kicked")
        await do_kick(channel, member, reason=reason)
        create_kick(member.id)

    greeting = delete_entry(member.id)
    await try_delete_greeting(greeting, channel)
    set_age(member.id, age, force=force_update_age)

async def try_delete_greeting(greeting, channel):
    if greeting is None: return

    try:
        channel = bot.get_channel(channel_ids[0])
        greeting_msg = await channel.fetch_message(greeting)
        await greeting_msg.delete()

    except discord.NotFound:
        app.logger.debug(f"[{channel.guild.name} / {channel}] Greeting {greeting} already deleted")

    except Exception as e:
        app.logger.warning(f"[{channel.guild.name} / {channel}] failed to delete greeting {greeting}")
        app.logger.debug(f"[{channel.guild.name} / {channel}] {e}")

def is_valid_age(msg: str):
    return age_prog.search(msg) is not None

def get_age(msg: str):
    return int(age_prog.search(msg).group())

def is_insta_ban(msg: str): # TODO add filters? racism, etc.
    return minor_prog.search(msg) is not None or minor_prog_2.search(msg) is not None

def get_ban_age(msg: str):
    return int(minor_prog.search(msg).group())

@bot.event
async def on_member_join(member: discord.Member):
    if member.id == bot.user.id: return
    channel = bot.get_channel(channel_ids[0])
    app.logger.debug(f"[{channel.guild.name} / {channel}] {member} just joined")

    greeting = await channel.send(MSG_GREETING.format(member.mention))
    create_entry(member.id, greeting.id)

    await asyncio.sleep(LENIENCY_TIME_S)

    # check
    leniency = get_leniency(member.id)
    if (leniency is not None): # user hasn't answered yet
        app.logger.debug(f"[{channel.guild.name} / {channel}] Leniency data found")
        age_role = None
        for role in member.roles: # check if user at least has one of the correct tags
            if role in _role_ids:
                age_role = role
                break

        if age_role is None:
            app.logger.debug(f"[{channel.guild.name} / {channel}] No age role")
            await kick_or_ban(member, channel, reason=REASON_TIMEOUT)
        else:
            app.logger.debug(f"[{channel.guild.name} / {channel}] Found age role: {age_role}")
            set_age(member.id, age_role, force=True) # since we don't know the exact age, save the role ID instead

    else:
        app.logger.debug(f"[{channel.guild.name} / {channel}] Leniency data NOT found")

    delete_entry(member.id)
    
    app.logger.debug(f"[{channel.guild.name} / {channel}] Exit on_member_join")

bot.run(TOKEN)
