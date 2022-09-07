import asyncio
import discord
import discord_slash
import logging
import os
import random
import requests
import string
import traceback

import age_handling
import db
import graphlytics
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
LENIENCY_REMINDER_TIME_S = 3 * 60 # time before sending a reminder (can be None)
LENIENCY_COUNT = 5 # messages before ban
LENIENCY_REMINDER = 3 # messages before asking again (can be None)

WARNING_VALIDITY_DAYS = 30
WARNINGS_BEFORE_BAN = 3

assert (LENIENCY_REMINDER_TIME_S is None) or (LENIENCY_REMINDER_TIME_S < LENIENCY_TIME_S), "Reminder time must be smaller than total time"
assert (LENIENCY_REMINDER is None) or (LENIENCY_REMINDER < LENIENCY_COUNT), "Reminder count must be smaller than total leniency"

MSG_NOT_ALLOWED = "You're not allowed to use this command :3"
MSG_RAID_MODE_ON = "{} just turned raid mode **ON**, brace for impact!"
MSG_RAID_MODE_OFF = "{} just turned raid mode **OFF**, we live to see another day!"
MSG_RAID_MODE_ON_ALREADY = "Raid mode is already on"
MSG_RAID_MODE_OFF_ALREADY = "Raid mode is already off"
MSG_CANT_DO_IT = "I can't do that to that user~ :3"
MSG_USER_ALREADY_MAXED = "That user is already at max tier!"
MSG_CONGRATULATIONS_PROMOTION = "Congratulations on your promotion to tier {}, {}!"

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
secretary_role_id = 1002385294152179743
friends_role_ids = [
    1002382914526400703, # Tier 1
    1002676012573794394, # Tier 2
    1002676963485417592 # Tier 3
]

admin_id = int(os.getenv('ADMIN_ID'))

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
age_handler = age_handling.age_handler(bot, sql, app.logger, channel_ids[0], tally_channel, _role_ids, LENIENCY_COUNT - LENIENCY_REMINDER)

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
        app.logger.error(f"[{msg.channel}] Error in hi_dad: {e}\n{traceback.format_exc()}")

async def _dm_log_error(msg):
    if admin_id is None: return
    try:
        admin_user = bot.get_user(admin_id)
        dm_chan = admin_user.dm_channel or await admin_user.create_dm()
        await dm_chan.send(content=f"Error thrown during operation:\n```\n{msg}\n```")
    except Exception as e:
        app.logger.error(f"Error while trying to log error: {e}\n{traceback.format_exc()}")

@bot.event
async def on_ready():
    app.logger.info(f"{bot.user} has connected to Discord")

@bot.event
async def on_message(msg: discord.Message):
    if msg.author.id == bot.user.id or len(msg.content) == 0: return
    # app.logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} says \"{msg.content}\"")

    try:
        await age_handler.handle_age(msg)
    except Exception as e:
        app.logger.error(f"[{msg.channel}] Error during on_message: {e}\n{traceback.format_exc()}")
        await _dm_log_error(f"[{msg.channel}] on_message\n{e}\n{traceback.format_exc()}")
        
    # await _hi_dad(msg)

@bot.event
async def on_member_join(member: discord.Member):
    try:
        if member.id == bot.user.id: return
        channel = bot.get_channel(channel_ids[0])
        app.logger.info(f"[{channel}] {member} just joined")
        
        if RAID_MODE or is_raid_mode():
            app.logger.info(f"[{channel}] Raid mode ON: {member}")
            await age_handler.kick_or_ban(member, channel, reason=age_handling.REASON_RAID)
            return

        greeting = await channel.send(age_handling.MSG_GREETING.format(member.mention))
        sql.create_entry(member.id, greeting.id)

        must_continue = True
        if (LENIENCY_REMINDER_TIME_S is not None):
            app.logger.debug(f"[{channel}] {member} Waiting to send reminder")
            await asyncio.sleep(LENIENCY_REMINDER_TIME_S)
            try:
                must_continue = await age_handler.do_age_check(channel, member, is_reminder=True)
                if not must_continue:
                    app.logger.debug(f"[{channel}] Early exit on_member_join")
                    return
                else:
                    app.logger.debug(f"[{channel}] {member} Sending reminder message")
                    await channel.send(age_handling.MSG_GREETING_REMINDER.format(member.mention))
            except Exception as e:
                app.logger.error(f"[{channel}] Error during on_member_join: {e}\n{traceback.format_exc()}")
                await _dm_log_error(f"[{channel}] [reminder] do_age_check\n{e}\n{traceback.format_exc()}")

        await asyncio.sleep(LENIENCY_TIME_S if LENIENCY_REMINDER_TIME_S is None else LENIENCY_TIME_S - LENIENCY_REMINDER_TIME_S)
        try:
            await age_handler.do_age_check(channel, member)
        except Exception as e:
            app.logger.error(f"[{channel}] Error during on_member_join: {e}\n{traceback.format_exc()}")
            await _dm_log_error(f"[{channel}] [final] do_age_check\n{e}\n{traceback.format_exc()}")
        
        app.logger.debug(f"[{channel}] Exit on_member_join")

    except Exception as e:
        app.logger.error(f"[{channel}] Error during on_member_join: {e}\n{traceback.format_exc()}")
        await _dm_log_error(f"[{channel}] on_member_join\n{e}\n{traceback.format_exc()}")
        app.logger.debug(f"[{channel}] Error exit on_member_join")

opts = [discord_slash.manage_commands.create_option(name="active", description="Whether to turn raid mode on or off", option_type=5, required=True)]
@slash.slash(name="raidmode", description="Turn raid mode on or off (auto kick or ban)", options=opts, guild_ids=guild_ids)
async def _raidmode(ctx: SlashContext, **kwargs):
    if not (divine_role_id in [role.id for role in ctx.author.roles]):
        log_debug(ctx, f"{ctx.author} cannot use raidmode")
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

    message = await ctx.send(content="I'll be right back with your meme~", hidden=False)

    av_url = AVATAR_CDN_URL.format(user.id, user.avatar)

    icon_name = "trash/" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=20)) + ".png"
    log_debug(ctx, f"icon_name={icon_name}")

    file = open(icon_name, "wb")
    file.write(requests.get(av_url).content)
    file.close()

    meme_name = meme_function(icon_name)
    log_debug(ctx, f"meme_name={meme_name}")
    meme_file = discord.File(meme_name, filename=f"{user.name}_{meme_code}.png")
    
    os.remove(icon_name)

    msg = "Enjoy your fresh meme~"
    if (user.id == ctx.author_id):
        msg = "Lmao did you really make it for yourself??"
    if (user.id == bot.user.id):
        msg = f"Awww thank you, {ctx.author.mention}~"

    await message.edit(content=msg, file=meme_file)

    os.remove(meme_name)

opts = [discord_slash.manage_commands.create_option(name="user", description="Who to use in the meme", option_type=6, required=True)]
@slash.slash(name="supremacy", description="Ask miguel", options=opts, guild_ids=guild_ids)
async def _supremacy(ctx: SlashContext, **kwargs):
    user = kwargs["user"]
    log_info(ctx, f"{ctx.author} requested {user} supremacy")
    log_debug(ctx, f"avatar={user.avatar}")

    message = await ctx.send(content="I'll be right back with your meme~", hidden=False)

    av_url = AVATAR_CDN_URL.format(user.id, user.avatar)

    icon_name = "trash/" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=20)) + ".png"
    log_debug(ctx, f"icon_name={icon_name}")

    file = open(icon_name, "wb")
    file.write(requests.get(av_url).content)
    file.close()

    meme_name = memes.generate_sup(user.display_name, icon_name)
    log_debug(ctx, f"meme_name={meme_name}")
    meme_file = discord.File(meme_name, filename=f"{user.name}_supremacy.png")
    
    os.remove(icon_name)

    msg = "Enjoy your fresh meme~"
    if (user.id == ctx.author_id):
        msg = "Lmao did you really make it for yourself??"
    if (user.id == bot.user.id):
        msg = f"Awww thank you, {ctx.author.mention}~"

    await message.edit(content=msg, file=meme_file)

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

    if pct == 69:
        emote = ":sunglasses:"
    elif pct < 33:
        emote = ":broken_heart:"
    elif pct < 66:
        emote = ":heart:"
    elif pct < 100:
        emote = ":two_hearts:"
    else:
        emote = ":revolving_hearts:"

    await ctx.send(content=f"The ship compatibility between {ctx.author.mention} and {user.mention} today is {emote} {pct}%{nice} :3", hidden=False)

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

    message = await ctx.send(content=content, hidden=False)

    meme_name = memes.no_horny
    meme_file = discord.File(meme_name, filename=meme_name)
    embed = discord.Embed()
    embed.set_image(url=f"attachment://{meme_name}")

    await message.edit(file=meme_file)

opts = [discord_slash.manage_commands.create_option(name="range", description="Max days to fetch", option_type=4, required=False)]
@slash.slash(name="report", description="Get analytics data for new users", options=opts, guild_ids=guild_ids)
async def _report(ctx: SlashContext, **kwargs):
    log_info(ctx, f"{ctx.author} requested report")
    if (ctx.author_id != admin_id) and not (divine_role_id in [role.id for role in ctx.author.roles]):
        log_debug(ctx, f"{ctx.author} cannot get report")
        await ctx.send(content=MSG_NOT_ALLOWED, hidden=True)
        return

    message = await ctx.send(content=f"One sec~", hidden=False)

    report_name = graphlytics.generate_new_user_graph(app.logger, kwargs["range"] if "range" in kwargs else None)
    log_debug(ctx, f"report_name={report_name}")
    report_file = discord.File(report_name, filename=f"user_report.png")

    await message.edit(content=f"Here you go~", file=report_file)

    os.remove(report_name)

opts = [discord_slash.manage_commands.create_option(name="user", description="User to warn", option_type=6, required=True)]
opts += [discord_slash.manage_commands.create_option(name="reason", description="Why are they being warned", option_type=3, required=False)]
@slash.slash(name="strike", description="Warn a user for bad behavior, auto bans if there are too many strikes", options=opts, guild_ids=guild_ids)
async def _strike(ctx: SlashContext, **kwargs):
    user = kwargs["user"]
    reason = kwargs["reason"] if "reason" in kwargs else ""
    _author_roles = [role.id for role in ctx.author.roles]
    log_info(ctx, f"{ctx.author} requested strike for {user}: '{reason}'")
    if (ctx.author_id != admin_id) and not (divine_role_id in _author_roles or secretary_role_id in _author_roles):
        log_debug(ctx, f"{ctx.author} cannot warn people")
        await ctx.send(content=MSG_NOT_ALLOWED, hidden=True)
        return

    _user_roles = [role.id for role in user.roles]
    if (divine_role_id in _user_roles or secretary_role_id in _user_roles):
        log_debug(ctx, f"{user} cannot be warned")
        await ctx.send(content=MSG_CANT_DO_IT, hidden=True)
        return

    active_strikes = sql.create_warning(user.id, ctx.author_id, reason, WARNING_VALIDITY_DAYS)

    if active_strikes < WARNINGS_BEFORE_BAN:
        log_info(ctx, f"{user} now has {active_strikes} active strikes")
        msg = f"{user.mention} is being warned by {ctx.author.mention}! That's {active_strikes} strikes so far~"
        if len(reason) > 0:
            msg += f" Reason: {reason}"
        await ctx.send(content=msg, hidden=False)
    else:
        log_info(ctx, f"{user} now has {active_strikes} active strikes, and will be banned")
        msg = f"{user.mention} is being warned by {ctx.author.mention}! That's {active_strikes} strikes, and so you must go~"
        if len(reason) > 0:
            msg += f" Reason: {reason}"
        await ctx.send(content=msg, hidden=False)
        await age_handler.do_ban(ctx.channel, user, reason=age_handling.REASON_WARNINGS, tally=False)

opts = [discord_slash.manage_commands.create_option(name="user", description="User to check", option_type=6, required=True)]
opts += [discord_slash.manage_commands.create_option(name="all", description="Get all strikes (only gets active strikes by default)", option_type=5, required=False)]
@slash.slash(name="getStrikes", description="Check the user's previous strikes", options=opts, guild_ids=guild_ids)
async def _get_strikes(ctx: SlashContext, **kwargs):
    user = kwargs["user"]
    get_all = "all" in kwargs and kwargs["all"]
    log_info(ctx, f"{ctx.author} requested strikes for {user}")
    if (ctx.author_id != admin_id) and not (divine_role_id in [role.id for role in ctx.author.roles]):
        log_debug(ctx, f"{ctx.author} cannot get strikes")
        await ctx.send(content=MSG_NOT_ALLOWED, hidden=True)
        return

    strikes = sql.get_warnings(user.id, None if get_all else WARNING_VALIDITY_DAYS)

    if (len(strikes) > 0):
        msg = f":warning: Here are {user.mention}'s strikes~\n```\n"
        for moderator, reason, date in strikes:
            mod = bot.get_user(moderator)
            msg += f"{date} by {mod.mention}: {reason}\n"
        msg += "```"
    else:
        msg = f":angel: {user.mention} doesn't have any"
        if not get_all:
            msg += " active"
        msg += f" strikes~"

    await ctx.send(content=msg, hidden=False)

opts = [discord_slash.manage_commands.create_option(name="user", description="User to promote", option_type=6, required=True)]
@slash.slash(name="promote", description="Promote a user to the next tier", options=opts, guild_ids=guild_ids)
async def _promote(ctx: SlashContext, **kwargs):
    user = kwargs["user"]
    reason = kwargs["reason"] if "reason" in kwargs else ""
    _author_roles = [role.id for role in ctx.author.roles]
    log_info(ctx, f"{ctx.author} requested promotion for {user}")
    if (ctx.author_id != admin_id) and not (divine_role_id in _author_roles or secretary_role_id in _author_roles):
        log_debug(ctx, f"{ctx.author} cannot promote people")
        await ctx.send(content=MSG_NOT_ALLOWED, hidden=True)
        return

    _user_roles = [role.id for role in user.roles]
    if friends_role_ids[2] in _user_roles:
        log_debug(ctx, f"{user} already at max tier")
        await ctx.send(content=MSG_USER_ALREADY_MAXED, hidden=True)
        return

    if friends_role_ids[1] in _user_roles:
        log_debug(ctx, f"{user} will NOT be promoted to tier 3")
        await ctx.send(content="Khris said no promotions to t3~", hidden=True)
        return
        # msg = MSG_CONGRATULATIONS_PROMOTION.format(3, user.mention)
        # new_role_id = friends_role_ids[2]
        
    else:
        log_debug(ctx, f"{user} will be promoted to tier 2")
        msg = MSG_CONGRATULATIONS_PROMOTION.format(2, user.mention)
        new_role_id = friends_role_ids[1]
        
    try:
        member = ctx.guild.get_member(user.id)
        new_role = ctx.guild.get_role(new_role_id)
        await member.add_roles(new_role, reason=f"{ctx.author} said so")
        await ctx.send(content=msg, hidden=False)
    except discord.HTTPException as e:
        log_error(ctx, f"Failed to give role {new_role} to {user}")
        log_debug(ctx, e)
        await ctx.send(content="I still can't give promotions and it's probably Khris' fault~", hidden=True)

opts = [discord_slash.manage_commands.create_option(name="user", description="User to check", option_type=6, required=True)]
@slash.slash(name="age", description="Check a user's reported age", options=opts, guild_ids=guild_ids)
async def _age(ctx: SlashContext, **kwargs):
    user = kwargs["user"]
    _author_roles = [role.id for role in ctx.author.roles]
    log_info(ctx, f"{ctx.author} requested age for {user}")
    if (ctx.author_id != admin_id) and not (divine_role_id in _author_roles or secretary_role_id in _author_roles):
        log_debug(ctx, f"{ctx.author} cannot check ages")
        await ctx.send(content=MSG_NOT_ALLOWED, hidden=True)
        return
        
    age_data = sql.get_age(user.id)
    if age_data is None:
        msg = f"{user.mention} joined before the glorious Botto revolution"
    elif age_data < 5:
        msg = f"{user.mention}'s age is unknown"
    elif age_data < 1000:
        msg = f"{user.mention} said they were {age_data} years old"
    else:
        _tag = ctx.guild.get_role(age_data)
        if _tag is None:
            msg = f"{user.mention} has an unknown tag ({age_data})"
        else:
            msg = f"{user.mention} selected the {_tag} role"

    log_debug(ctx, f"{msg}")
    await ctx.send(content=msg, hidden=True)

bot.run(TOKEN)
