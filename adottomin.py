import asyncio
import discord
import discord_slash
import logging
import os
import random
import requests
import string

import age_handling
import db
import memes

from os.path import exists
from dotenv import load_dotenv
from flask import Flask
from discord.ext import commands
from discord_slash import SlashCommand, SlashContext

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
if TOKEN is None:
    print("DISCORD_TOKEN env var not set! Exiting")
    exit(1)

RAID_MODE_CTRL = "raid.txt"
RAID_MODE = False

LENIENCY_TIME_S = 5 * 60 # time to reply
LENIENCY_COUNT = 5 # messages before ban

MSG_NOT_ALLOWED = "You're not allowed to use this command :3"
MSG_RAID_MODE_ON = "{} just turned raid mode **ON**, brace for impact!"
MSG_RAID_MODE_OFF = "{} just turned raid mode **OFF**, we live to see another day!"
MSG_RAID_MODE_ON_ALREADY = "Raid mode is already on"
MSG_RAID_MODE_OFF_ALREADY = "Raid mode is already off"

AVATAR_CDN_URL = "https://cdn.discordapp.com/avatars/{}/{}.png"

bot_home = os.getenv("BOT_HOME") or os.getcwd()

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

def log_debug(ctx, msg):
    app.logger.debug(f"[{ctx.channel}] {msg}")

def log_info(ctx, msg):
    app.logger.info(f"[{ctx.channel}] {msg}")

def log_warn(ctx, msg):
    app.logger.warning(f"[{ctx.channel}] {msg}")

def log_error(ctx, msg):
    app.logger.error(f"[{ctx.channel}] {msg}")

app.logger.info(f"Channel ID = {channel_ids[0]}")
app.logger.info(f"Guild ID = {guild_ids[0]}")
app.logger.info(f"Role IDs = {role_ids}")
app.logger.info(f"Tallly channel IDs = {tally_channel}")

sql = db.database(LENIENCY_COUNT, app.logger)
age_handler = age_handling.age_handler(bot, sql, app.logger, channel_ids[0], tally_channel)

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

async def _hi_dad(msg):
    try:
        hi_dad = memes.hi_dad(msg.content)
        if hi_dad is None: return
        await msg.reply(content=hi_dad)
    except Exception as e:
        app.logger.error(f"[{msg.channel}] Error in hi_dad: {e}")

@bot.event
async def on_ready():
    app.logger.info(f"{bot.user} has connected to Discord")

@bot.event
async def on_message(msg: discord.Message):
    if msg.author.id == bot.user.id or len(msg.content) == 0: return
    # app.logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} says \"{msg.content}\"")

    await age_handler.handle_age(msg)
    await _hi_dad(msg)

@bot.event
async def on_member_join(member: discord.Member):
    if member.id == bot.user.id: return
    channel = bot.get_channel(channel_ids[0])
    app.logger.debug(f"[{channel.guild.name} / {channel}] {member} just joined")
    
    if RAID_MODE or is_raid_mode():
        app.logger.info(f"[{channel.guild.name} / {channel}] Raid mode ON: {member}")
        await age_handler.kick_or_ban(member, channel, reason=age_handling.REASON_RAID)
        return

    greeting = await channel.send(age_handling.MSG_GREETING.format(member.mention))
    sql.create_entry(member.id, greeting.id)

    await asyncio.sleep(LENIENCY_TIME_S)

    # check
    leniency = sql.get_leniency(member.id)
    if (leniency is not None): # user hasn't answered yet
        app.logger.debug(f"[{channel.guild.name} / {channel}] Leniency data found")
        age_role = None
        role_count = 0
        try:
            member = await bot.get_guild(guild_ids[0]).fetch_member(member.id) # fetch the user data again cuz of cached roles
            app.logger.debug(f"[{channel.guild.name} / {channel}] User roles => {member.roles}")
            for role in member.roles: # check if user at least has one of the correct tags
                if role.id in _role_ids:
                    if age_role is None:
                        age_role = role
                    role_count += 1

            if age_role is None:
                app.logger.debug(f"[{channel.guild.name} / {channel}] No age role")
                await age_handler.kick_or_ban(member, channel, reason=age_handling.REASON_TIMEOUT)
            elif role_count > 2:
                app.logger.debug(f"[{channel.guild.name} / {channel}] Too many roles")
                await age_handler.kick_or_ban(member, channel, reason=age_handling.REASON_SPAM)
            else:
                app.logger.debug(f"[{channel.guild.name} / {channel}] Found age role: {age_role}")
                sql.set_age(member.id, age_role.id, force=True) # since we don't know the exact age, save the role ID instead
        except discord.NotFound:
            app.logger.debug(f"[{channel.guild.name} / {channel}] {member} already quit")

    else:
        app.logger.debug(f"[{channel.guild.name} / {channel}] Leniency data NOT found")

    sql.delete_entry(member.id)
    
    app.logger.debug(f"[{channel.guild.name} / {channel}] Exit on_member_join")

opts = [discord_slash.manage_commands.create_option(name="active", description="Whether to turn raid mode on or off", option_type=5, required=True)]
@slash.slash(name="raidmode", description="Turn raid mode on or off (auto kick or ban)", options=opts, guild_ids=guild_ids)
async def _raidmode(ctx: SlashContext, **kwargs):
    if not (divine_role_id in [role.id for role in ctx.author.roles]):
        log_debug(ctx, f"{ctx.member} cannot use raidmode")
        await ctx.send(content=MSG_NOT_ALLOWED, hidden=True)
        return

    args = [kwargs[k] for k in kwargs if kwargs[k] is not None]
    turn_on = args[0]
    if turn_on:
        if set_raid_mode():
            log_info(ctx, f"{ctx.author} enabled raidmode")
            await ctx.send(content=MSG_RAID_MODE_ON.format(ctx.author.mention), hidden=False)
        else:
            log_debug(ctx, f"{ctx.author} enabled raidmode (already enabled)")
            await ctx.send(content=MSG_RAID_MODE_ON_ALREADY, hidden=True)
    else:
        if unset_raid_mode():
            log_info(ctx, f"{ctx.author} disabled raidmode")
            await ctx.send(content=MSG_RAID_MODE_OFF.format(ctx.author.mention), hidden=False)
        else:
            log_debug(ctx, f"{ctx.author} disabled raidmode (already disabled)")
            await ctx.send(content=MSG_RAID_MODE_OFF_ALREADY, hidden=True)

async def _meme(ctx: SlashContext, meme_function, meme_code, **kwargs):
    user = kwargs["user"]
    log_info(ctx, f"{ctx.author} requested {user} {meme_code}")
    log_debug(ctx, f"avatar={user.avatar}")

    av_url = AVATAR_CDN_URL.format(user.id, user.avatar)

    icon_name = "trash/" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=20)) + ".png"
    log_debug(ctx, f"icon_name={icon_name}")

    file = open(icon_name, "wb")
    file.write(requests.get(av_url).content)
    file.close()

    meme_name = meme_function(icon_name)
    log_debug(ctx, f"meme_name={meme_name}")
    meme_file = discord.File(meme_name, filename=f"{user.name}_{meme_code}.png")
    embed = discord.Embed()
    embed.set_image(url=f"attachment://{meme_name}")
    
    os.remove(icon_name)

    msg = "Enjoy your fresh meme"
    if (user.id == ctx.author_id):
        msg = "Lmao did you really make it for yourself??"
    if (user.id == bot.user.id):
        msg = f"Awww thank you, {ctx.author.mention}~"
    await ctx.send(content=msg, file=meme_file, embed=embed, hidden=False)

    os.remove(meme_name)

opts = [discord_slash.manage_commands.create_option(name="user", description="Who to use in the meme", option_type=6, required=True)]
@slash.slash(name="supremacy", description="Ask miguel", options=opts, guild_ids=guild_ids)
async def _supremacy(ctx: SlashContext, **kwargs):
    user = kwargs["user"]
    log_info(ctx, f"{ctx.author} requested {user} supremacy")
    log_debug(ctx, f"avatar={user.avatar}")

    av_url = AVATAR_CDN_URL.format(user.id, user.avatar)

    icon_name = "trash/" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=20)) + ".png"
    log_debug(ctx, f"icon_name={icon_name}")

    file = open(icon_name, "wb")
    file.write(requests.get(av_url).content)
    file.close()

    meme_name = memes.generate_sup(user.display_name, icon_name)
    log_debug(ctx, f"meme_name={meme_name}")
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
    await _meme(ctx, memes.generate_nuts, "deeznuts", **kwargs)

opts = [discord_slash.manage_commands.create_option(name="user", description="Who to use in the meme", option_type=6, required=True)]
@slash.slash(name="pills", description="Ask miguel", options=opts, guild_ids=guild_ids)
async def _pills(ctx: SlashContext, **kwargs):
    await _meme(ctx, memes.generate_pills, "pills", **kwargs)

opts = [discord_slash.manage_commands.create_option(name="user", description="Who to ship you with", option_type=6, required=True)]
@slash.slash(name="shipme", description="Ship yourself with someone!", options=opts, guild_ids=guild_ids)
async def _shipme(ctx: SlashContext, **kwargs):
    user = kwargs["user"]
    log_info(ctx, f"{ctx.author} requested ship with {user}")
    if (user.id == ctx.author_id):
        await ctx.send(content=f"No selfcest, {ctx.author.mention}!", hidden=False)
        return

    if (user.id == bot.user.id):
        await ctx.send(content=f"I'm not shipping myself with you, {ctx.author.mention}~", hidden=False)
        return

    smaller = min(int(user.id), int(ctx.author_id))
    bigger = max(int(user.id), int(ctx.author_id))
    pct, nice = memes.percent_from(f"ship/{smaller}/{bigger}")

    await ctx.send(content=f"The ship compatibility between {ctx.author.mention} and {user.mention} today is {pct}%{nice} :3", hidden=False)

opts = [discord_slash.manage_commands.create_option(name="user", description="Who to rate (if empty, rates you)", option_type=6, required=False)]
@slash.slash(name="gayrate", description="Rate your gae!", options=opts, guild_ids=guild_ids)
async def _gayrate(ctx: SlashContext, **kwargs):
    user = kwargs["user"] if "user" in kwargs else ctx.author
    log_info(ctx, f"{ctx.author} requested gayrate for {user}")
    if (user.id == bot.user.id):
        await ctx.send(content=f"Wouldn't you like to know, {ctx.author.mention}~?", hidden=False)
        return

    pct, nice = memes.percent_from(f"gay/{int(user.id)}")

    await ctx.send(content=f"{user.mention} is :rainbow_flag: {pct}% gay today!{nice} :3", hidden=False)

opts = [discord_slash.manage_commands.create_option(name="user", description="Who to rate (if empty, rates you)", option_type=6, required=False)]
@slash.slash(name="hornyrate", description="Rate your horny!", options=opts, guild_ids=guild_ids)
async def _hornyrate(ctx: SlashContext, **kwargs):
    user = kwargs["user"] if "user" in kwargs else ctx.author
    log_info(ctx, f"{ctx.author} requested hornyrate for {user}")
    if (user.id == bot.user.id):
        await ctx.send(content=f"Wouldn't you like to know, {ctx.author.mention}~?", hidden=False)
        return

    pct, nice = memes.percent_from(f"horny/{int(user.id)}")
    if pct == 69:
        emote = ":sunglasses:"
    elif pct < 33:
        emote = ":angel:"
    elif pct < 66:
        emote = ":slight_smile:"
    else:
        emote = ":smiling_imp:"

    await ctx.send(content=f"{user.mention} is {emote} {pct}% horny today!{nice} :3", hidden=False)

opts = [discord_slash.manage_commands.create_option(name="user", description="Who to mention (optional)", option_type=6, required=False)]
@slash.slash(name="horny", description="No horny in main!", options=opts, guild_ids=guild_ids)
async def _horny(ctx: SlashContext, **kwargs):
    user = kwargs["user"] if "user" in kwargs else None
    log_info(ctx, f"{ctx.author} requested No Horny for {user}")

    content = "No horny in main{}!".format(f", {user.mention}" if user is not None else "")

    meme_name = memes.no_horny
    meme_file = discord.File(meme_name, filename=meme_name)
    embed = discord.Embed()
    embed.set_image(url=f"attachment://{meme_name}")

    await ctx.send(content=content, file=meme_file, embed=embed, hidden=False)

bot.run(TOKEN)
