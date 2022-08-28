import asyncio
import datetime
import discord
from discord.member import Member
import discord_slash
import logging
import os
from os.path import exists
import sys
from discord import flags
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
from discord.ext import commands
from discord_slash import SlashCommand, SlashContext
import sqlite3
import re
import random
import string
import requests

import memes

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
if TOKEN is None:
    print("DISCORD_TOKEN env var not set! Exiting")
    exit(1)

RAID_MODE_CTRL = "raid.txt"
RAID_MODE = False

LENIENCY_TIME_S = 5 * 60 # time to reply
LENIENCY_COUNT = 5 # messages before ban

REASON_MINOR = "minor"
REASON_TIMEOUT = "did not say age"
REASON_RAID = "raid"
MSG_GREETING = "Hello {}! May I ask your age, pls?"
MSG_WELCOME = "Thank you {}! Welcome to the server! Tags are in <#1005395967429836851> if you want ^^"
MSG_WELCOME_NO_TAGS = "Thank you {}! Welcome to the server!"
MSG_NOT_ALLOWED = "You're not allowed to use this command :3"
MSG_RAID_MODE_ON = "[TEST ONLY, PLEASE IGNORE] {} just turned raid mode on, brace for impact!"
MSG_RAID_MODE_OFF = "[TEST ONLY, PLEASE IGNORE] {} just turned raid mode off, we live to see another day!"
MSG_RAID_MODE_ON_ALREADY = "Raid mode is already on"
MSG_RAID_MODE_OFF_ALREADY = "Raid mode is already off"

AVATAR_CDN_URL = "https://cdn.discordapp.com/avatars/{}/{}.png"

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

divine_role_id = 1008695237281058898

bot = commands.Bot(command_prefix="/", self_bot=True, intents=discord.Intents.all())
slash = SlashCommand(bot, sync_commands=True)
app = Flask(__name__)
app.logger.root.setLevel(logging.getLevelName(os.getenv('LOG_LEVEL') or 'DEBUG'))
# app.logger.addHandler(logging.StreamHandler(sys.stdout))

app.logger.info(f"Channel ID = {channel_ids[0]}")
app.logger.info(f"Guild ID = {guild_ids[0]}")
app.logger.info(f"Role IDs = {role_ids}")
app.logger.info(f"Tallly channel IDs = {tally_channel}")

# Age regex
age_prog = re.compile(r"(18|19|[2-9][0-9])") # 18, 19 or 20+
minor_prog = re.compile(r"(?: |^)\b(1[0-7])\b") # 0-9 or 10-17
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
        cur.execute("DELETE FROM kicks WHERE user=:id", {"id": user})
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

def is_raid_mode():
    return exists(RAID_MODE_CTRL)

def set_raid_mode():
    if is_raid_mode(): return False
    open(RAID_MODE_CTRL, "w").close()
    return True

def unset_raid_mode():
    if not is_raid_mode(): return False
    os.remove(RAID_MODE_CTRL)
    return True

async def do_tally():
    if tally_channel is None: return
    try:
        await bot.get_channel(tally_channel).send(f"x")
    except Exception as e:
        app.logger.error(f"Failed to tally! {e}")

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
    # app.logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} says \"{msg.content}\"")

    await handle_age(msg)

async def handle_age(msg: discord.Message):
    leniency = get_leniency(msg.author.id)
    if leniency is None or leniency < 0: return
    
    app.logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} is still on watchlist, parsing message")

    if is_insta_ban(msg.content):
        age = get_ban_age(msg.content)
        app.logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} said a non-valid age ({age})")
        await kick_or_ban(msg.author, msg.channel, age=age, force_ban=True, force_update_age=True, reason=REASON_MINOR)

    elif is_valid_age(msg.content):
        age = get_age(msg.content)
        app.logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} said a valid age ({age})")
        
        delete_entry(msg.author.id)
        set_age(msg.author.id, age, force=True)

        await msg.channel.send(MSG_WELCOME.format(msg.author.mention))

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
    
    if RAID_MODE or is_raid_mode():
        app.logger.info(f"[{channel.guild.name} / {channel}] Raid mode ON: {member}")
        await kick_or_ban(member, channel, reason=REASON_RAID)
        return

    greeting = await channel.send(MSG_GREETING.format(member.mention))
    create_entry(member.id, greeting.id)

    await asyncio.sleep(LENIENCY_TIME_S)

    # check
    leniency = get_leniency(member.id)
    if (leniency is not None): # user hasn't answered yet
        app.logger.debug(f"[{channel.guild.name} / {channel}] Leniency data found")
        age_role = None
        try:
            member = await bot.get_guild(guild_ids[0]).fetch_member(member.id) # fetch the user data again cuz of cached roles
            app.logger.debug(f"[{channel.guild.name} / {channel}] User roles => {member.roles}")
            for role in member.roles: # check if user at least has one of the correct tags
                if role.id in _role_ids:
                    age_role = role
                    break

            if age_role is None:
                app.logger.debug(f"[{channel.guild.name} / {channel}] No age role")
                await kick_or_ban(member, channel, reason=REASON_TIMEOUT)
            else:
                app.logger.debug(f"[{channel.guild.name} / {channel}] Found age role: {age_role}")
                set_age(member.id, age_role.id, force=True) # since we don't know the exact age, save the role ID instead
        except discord.NotFound:
            app.logger.debug(f"[{channel.guild.name} / {channel}] {member} already quit")

    else:
        app.logger.debug(f"[{channel.guild.name} / {channel}] Leniency data NOT found")

    delete_entry(member.id)
    
    app.logger.debug(f"[{channel.guild.name} / {channel}] Exit on_member_join")

opts = [discord_slash.manage_commands.create_option(name="active", description="Whether to turn raid mode on or off", option_type=5, required=True)]
@slash.slash(name="raidmode", description="Turn raid mode on or off (auto kick or ban)", options=opts, guild_ids=guild_ids)
async def _raidmode(ctx: SlashContext, **kwargs):
    if not (divine_role_id in [role.id for role in ctx.author.roles]):
        app.logger.debug(f"[{ctx.channel.guild.name} / {ctx.channel}] {ctx.member} cannot use raidmode")
        await ctx.send(content=MSG_NOT_ALLOWED, hidden=True)
        return

    args = [kwargs[k] for k in kwargs if kwargs[k] is not None]
    turn_on = args[0]
    if turn_on:
        if set_raid_mode():
            app.logger.info(f"[{ctx.channel.guild.name} / {ctx.channel}] {ctx.author} enabled raidmode")
            await ctx.send(content=MSG_RAID_MODE_ON.format(ctx.author.mention), hidden=False)
        else:
            app.logger.debug(f"[{ctx.channel.guild.name} / {ctx.channel}] {ctx.author} enabled raidmode (already enabled)")
            await ctx.send(content=MSG_RAID_MODE_ON_ALREADY, hidden=True)
    else:
        if unset_raid_mode():
            app.logger.info(f"[{ctx.channel.guild.name} / {ctx.channel}] {ctx.author} disabled raidmode")
            await ctx.send(content=MSG_RAID_MODE_OFF.format(ctx.author.mention), hidden=False)
        else:
            app.logger.debug(f"[{ctx.channel.guild.name} / {ctx.channel}] {ctx.author} disabled raidmode (already disabled)")
            await ctx.send(content=MSG_RAID_MODE_OFF_ALREADY, hidden=True)

opts = [discord_slash.manage_commands.create_option(name="user", description="Who to use in the meme", option_type=6, required=True)]
@slash.slash(name="supremacy", description="Ask miguel", options=opts, guild_ids=guild_ids)
async def _supremacy(ctx: SlashContext, **kwargs):
    user = kwargs["user"]
    app.logger.info(f"[{ctx.channel.guild.name} / {ctx.channel}] {ctx.author} requested {user} supremacy")
    app.logger.debug(f"[{ctx.channel.guild.name} / {ctx.channel}] avatar={user.avatar}")

    av_url = AVATAR_CDN_URL.format(user.id, user.avatar)

    icon_name = "trash/" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=20)) + ".png"
    app.logger.debug(f"[{ctx.channel.guild.name} / {ctx.channel}] icon_name={icon_name}")

    file = open(icon_name, "wb")
    file.write(requests.get(av_url).content)
    file.close()

    meme_name = memes.generate_sup(user.display_name(), icon_name)
    app.logger.debug(f"[{ctx.channel.guild.name} / {ctx.channel}] meme_name={meme_name}")
    meme_file = discord.File(meme_name, filename=f"{user.name}_supremacy.png")
    embed = discord.Embed()
    embed.set_image(url=f"attachment://{meme_name}")
    
    os.remove(icon_name)

    msg = "Enjoy your fresh meme"
    if (user.id == ctx.author_id):
        msg = "Lmao did you really make it for yourself??"
    await ctx.send(content=msg, file=meme_file, embed=embed, hidden=False)

    os.remove(meme_name)

opts = [discord_slash.manage_commands.create_option(name="user", description="Who to use in the meme", option_type=6, required=True)]
@slash.slash(name="deeznuts", description="Ask miguel", options=opts, guild_ids=guild_ids)
async def _deeznuts(ctx: SlashContext, **kwargs):
    user = kwargs["user"]
    app.logger.info(f"[{ctx.channel.guild.name} / {ctx.channel}] {ctx.author} requested {user} deeznuts")
    app.logger.debug(f"[{ctx.channel.guild.name} / {ctx.channel}] avatar={user.avatar}")

    av_url = AVATAR_CDN_URL.format(user.id, user.avatar)

    icon_name = "trash/" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=20)) + ".png"
    app.logger.debug(f"[{ctx.channel.guild.name} / {ctx.channel}] icon_name={icon_name}")

    file = open(icon_name, "wb")
    file.write(requests.get(av_url).content)
    file.close()

    meme_name = memes.generate_nuts(icon_name)
    app.logger.debug(f"[{ctx.channel.guild.name} / {ctx.channel}] meme_name={meme_name}")
    meme_file = discord.File(meme_name, filename=f"{user.name}_supremacy.png")
    embed = discord.Embed()
    embed.set_image(url=f"attachment://{meme_name}")
    
    os.remove(icon_name)

    msg = "Enjoy your fresh meme"
    if (user.id == ctx.author_id):
        msg = "Lmao did you really make it for yourself??"
    await ctx.send(content=msg, file=meme_file, embed=embed, hidden=False)

    os.remove(meme_name)

opts = [discord_slash.manage_commands.create_option(name="user", description="Who to use in the meme", option_type=6, required=True)]
@slash.slash(name="pills", description="Ask miguel", options=opts, guild_ids=guild_ids)
async def _pills(ctx: SlashContext, **kwargs):
    user = kwargs["user"]
    app.logger.info(f"[{ctx.channel.guild.name} / {ctx.channel}] {ctx.author} requested {user} deeznuts")
    app.logger.debug(f"[{ctx.channel.guild.name} / {ctx.channel}] avatar={user.avatar}")

    av_url = AVATAR_CDN_URL.format(user.id, user.avatar)

    icon_name = "trash/" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=20)) + ".png"
    app.logger.debug(f"[{ctx.channel.guild.name} / {ctx.channel}] icon_name={icon_name}")

    file = open(icon_name, "wb")
    file.write(requests.get(av_url).content)
    file.close()

    meme_name = memes.generate_pills(icon_name)
    app.logger.debug(f"[{ctx.channel.guild.name} / {ctx.channel}] meme_name={meme_name}")
    meme_file = discord.File(meme_name, filename=f"{user.name}_supremacy.png")
    embed = discord.Embed()
    embed.set_image(url=f"attachment://{meme_name}")
    
    os.remove(icon_name)

    msg = "Enjoy your fresh meme"
    if (user.id == ctx.author_id):
        msg = "Lmao did you really make it for yourself??"
    await ctx.send(content=msg, file=meme_file, embed=embed, hidden=False)

    os.remove(meme_name)

bot.run(TOKEN)
