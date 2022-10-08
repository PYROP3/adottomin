import asyncio
import datetime
import sqlite3
import discord
import discord_slash
import logging
import os
import random
import traceback

import age_handling
import bot_utils
import copypasta_utils
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
chats_home = os.getenv('CHATS_HOME')

divine_role_id = 1008695237281058898
secretary_role_id = 1002385294152179743
friends_role_ids = [
    1002382914526400703, # Tier 1
    1002676012573794394, # Tier 2
    1002676963485417592 # Tier 3
]

game_channel_ids = [
    1006949968826863636,
    1006947536671617094,
    1006947561401241609,
    1006947572646162452,
    1006955372621336636,
    1006955386332532827,
    1012234333207146496,
    1012236248703836281,
    1006961455297470535,
    1006961469214163056,
    1006961483869077664
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
utils = bot_utils.utils(bot, sql, app.logger, [divine_role_id])

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

async def _dm_log_error(msg):
    if admin_id is None: return
    try:
        admin_user = bot.get_user(admin_id)
        dm_chan = admin_user.dm_channel or await admin_user.create_dm()
        await dm_chan.send(content=f"Error thrown during operation:\n```\n{msg}\n```")
    except Exception as e:
        app.logger.error(f"Error while trying to log error: {e}\n{traceback.format_exc()}")

def _get_message_for_age(ctx: SlashContext, age_data, mention):
    if age_data is None:
        return f"{mention} joined before the glorious Botto revolution"
    elif age_data < 5:
        return f"{mention}'s age is unknown"
    elif age_data < 1000:
        return f"{mention} said they were {age_data} years old"
    else:
        _tag = ctx.guild.get_role(age_data)
        if _tag is None:
            return f"{mention} has an unknown tag ({age_data})"
        else:
            return f"{mention} selected the {_tag} role"

@bot.event
async def on_ready():
    app.logger.info(f"{bot.user} has connected to Discord")
    utils.inject_admin(bot.get_user(admin_id))

bot_message_handlers = [
    utils.handle_offline_mentions
]
user_message_handlers = [
    age_handler.handle_age,
    utils.handle_dm,
    utils.handle_chat_dm
]

async def execute_handlers(msg, handlers):
    for handle in handlers:
        try:
            await handle(msg)
        except bot_utils.HandlerException:
            pass
        except Exception as e:
            app.logger.error(f"[{msg.channel}] Error during {handle.__qualname__}: {e}\n{traceback.format_exc()}")
            await _dm_log_error(f"[{msg.channel}] on_message::{handle.__qualname__}\n{e}\n{traceback.format_exc()}")

@bot.event
async def on_message(msg: discord.Message):
    if len(msg.content) == 0: return
    # app.logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} says \"{msg.content}\"")

    await execute_handlers(msg, bot_message_handlers)

    if msg.author.id == bot.user.id: return

    await execute_handlers(msg, user_message_handlers)
        
    if not msg.author.bot:
        try:
            sql.register_message(msg.author.id, msg.id, msg.channel.id)
        except Exception as e:
            app.logger.error(f"[{msg.channel}] Error during register_message: {e}\n{traceback.format_exc()}")
            await _dm_log_error(f"[{msg.channel}] on_message::register_message\n{e}\n{traceback.format_exc()}")
    else:
        app.logger.debug(f"[{msg.channel}] User ID: {msg.author.id} is a bot, not registering")

@bot.event
async def on_member_join(member: discord.Member):
    channel = bot.get_channel(channel_ids[0])
    app.logger.info(f"[{channel}] {member} just joined")
    try:
        if member.bot:
            app.logger.info(f"[{channel}] {member} is a bot, ignoring")
            return

        if member.id == bot.user.id: return
        
        if RAID_MODE or is_raid_mode():
            app.logger.info(f"[{channel}] Raid mode ON: {member}")
            await age_handler.kick_or_ban(member, channel, reason=age_handling.REASON_RAID)
            return

        autoblock = sql.is_autoblocked(member.id)
        if autoblock is not None:
            mod, reason, date = autoblock
            app.logger.info(f"[{channel}] {member} is PRE-blocked: {date}/{mod}: {reason}")
            await age_handler.kick_or_ban(member, channel, reason=reason, force_ban=True)
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

async def _meme(ctx: SlashContext, meme_code: str, text: str=None, msg="Enjoy your fresh meme~", **kwargs):
    await ctx.defer()

    log_info(ctx, f"{ctx.author} requested {meme_code}")

    _icon = await utils.get_icon_default(**kwargs)
    _author_icon = await utils.get_user_icon(ctx.author)
    _text = text or utils.get_text(**kwargs)
    log_debug(ctx, f"icon={_icon}, text={_text}")

    meme_name = memes.create_meme(meme_code, author_icon=_author_icon, icon=_icon, text=_text)
    log_debug(ctx, f"meme_name={meme_name}")

    if meme_name is None:
        await ctx.send(content="Oops, there was an error~")
        return 

    meme_file = discord.File(meme_name, filename=f"{ctx.author.name}_{meme_code}.png")
    
    if _icon is not None:
        os.remove(_icon)

    try:
        user = kwargs["user"]
        if (user.id == ctx.author_id):
            msg = "Lmao did you really make it for yourself??"
        if (user.id == bot.user.id):
            msg = f"Awww thank you, {ctx.author.mention}~"
    except:
        pass

    await ctx.send(content=msg, file=meme_file)

    os.remove(meme_name)

opts = [discord_slash.manage_commands.create_option(name="user", description="Who to use in the meme", option_type=6, required=True)]
@slash.slash(name="supremacy", description="Do you believe?", options=opts, guild_ids=guild_ids)
async def _supremacy(ctx: SlashContext, **kwargs):
    await _meme(ctx, "supremacy", **kwargs)

opts = [discord_slash.manage_commands.create_option(name="user", description="Who to use in the meme", option_type=6, required=True)]
@slash.slash(name="deeznuts", description="Awww", options=opts, guild_ids=guild_ids)
async def _deeznuts(ctx: SlashContext, **kwargs):
    await _meme(ctx, "deeznuts", **kwargs)

opts = [discord_slash.manage_commands.create_option(name="user", description="Who to use in the meme", option_type=6, required=True)]
@slash.slash(name="pills", description="You need those pills", options=opts, guild_ids=guild_ids)
async def _pills(ctx: SlashContext, **kwargs):
    await _meme(ctx, "pills", **kwargs)

opts = [discord_slash.manage_commands.create_option(name="user", description="Who to use in the meme", option_type=6, required=True)]
@slash.slash(name="bromeme", description="Bro", options=opts, guild_ids=guild_ids)
async def _bromeme(ctx: SlashContext, **kwargs):
    await _meme(ctx, "bromeme", **kwargs)

opts = [discord_slash.manage_commands.create_option(name="user", description="Who to use in the meme", option_type=6, required=True)]
@slash.slash(name="mig", description="Please", options=opts, guild_ids=guild_ids)
async def _mig(ctx: SlashContext, **kwargs):
    await _meme(ctx, "fivemins", **kwargs)

opts = [discord_slash.manage_commands.create_option(name="user", description="Who else to use in the meme", option_type=6, required=True)]
@slash.slash(name="sally", description="Your loss", options=opts, guild_ids=guild_ids)
async def _mig(ctx: SlashContext, **kwargs):
    await _meme(ctx, "sally", **kwargs)

opts = [discord_slash.manage_commands.create_option(name="contents", description="What to say in the meme", option_type=3, required=True)]
@slash.slash(name="needs", description="Traditional Maslow's hierarchy", options=opts, guild_ids=guild_ids)
async def _needs(ctx: SlashContext, **kwargs):
    await _meme(ctx, "needs", text=kwargs["contents"], **kwargs)

opts = [discord_slash.manage_commands.create_option(name=f"element_{i + 1}", description="What to put in your bingo", option_type=3, required=True) for i in range(24)]
@slash.slash(name="mybingo", description="Get a custom bingo sheet!", options=opts, guild_ids=guild_ids)
async def _mybingo(ctx: SlashContext, **kwargs):
    await _meme(ctx, "custom_bingo", text=[ctx.author.display_name] + [kwargs[f"element_{i + 1}"] for i in range(24)], msg="Enjoy your custom bingo~", **kwargs)

@slash.slash(name="randomcitizen", description="Get pinged!", options=[], guild_ids=guild_ids)
async def _randomcitizen(ctx: SlashContext, **kwargs):
    guild = ctx.guild
    if guild is None: 
        await ctx.send(content=f"That command only works in a server!", hidden=True)
        return
    member = random.choice(guild.members)
    await _meme(ctx, "random_citizen", msg=f"Get pinged, {member.mention}~", **kwargs)

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

opts = [discord_slash.manage_commands.create_option(name="expression", description="What to search", option_type=3, required=False)]
@slash.slash(name="boomersplain", description="Explain it like you're a boomer", options=opts, guild_ids=guild_ids)
async def _boomersplain(ctx: SlashContext, **kwargs):
    term = kwargs["expression"]
    log_info(ctx, f"{ctx.author} requested definition for {term}")

    formatted_definition = memes.get_formatted_definition(term)

    await ctx.send(content=formatted_definition, hidden=False)

opts = [discord_slash.manage_commands.create_option(name="user", description="Who to mention (optional)", option_type=6, required=False)]
@slash.slash(name="horny", description="No horny in main!", options=opts, guild_ids=guild_ids)
async def _horny(ctx: SlashContext, **kwargs):
    await ctx.defer()

    user = kwargs["user"] if "user" in kwargs else None
    log_info(ctx, f"{ctx.author} requested No Horny for {user}")

    content = "No horny in main{}!".format(f", {user.mention}" if user is not None else "")

    meme_name = memes.no_horny
    meme_file = discord.File(meme_name, filename=meme_name)
    embed = discord.Embed()
    embed.set_image(url=f"attachment://{meme_name}")

    await ctx.send(content=content, file=meme_file)

opts = [discord_slash.manage_commands.create_option(name="range", description="Max days to fetch", option_type=4, required=False)]
@slash.slash(name="report", description="Get analytics data for new users", options=opts, guild_ids=guild_ids)
async def _report(ctx: SlashContext, **kwargs):
    await ctx.defer()

    log_info(ctx, f"{ctx.author} requested report")
    if (ctx.author_id != admin_id) and not (divine_role_id in [role.id for role in ctx.author.roles]):
        log_debug(ctx, f"{ctx.author} cannot get report")
        await ctx.send(content=MSG_NOT_ALLOWED, hidden=True)
        return

    report_name = graphlytics.generate_new_user_graph(app.logger, kwargs["range"] if "range" in kwargs else None)
    log_debug(ctx, f"report_name={report_name}")
    report_file = discord.File(report_name, filename=f"user_report.png")

    await ctx.send(content=f"Here you go~", file=report_file)

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
    await ctx.defer(hidden=True)

    user = kwargs["user"]
    _author_roles = [role.id for role in ctx.author.roles]
    log_info(ctx, f"{ctx.author} requested age for {user}")
    if (ctx.author_id != admin_id) and not (divine_role_id in _author_roles or secretary_role_id in _author_roles):
        log_debug(ctx, f"{ctx.author} cannot check ages")
        await ctx.send(content=MSG_NOT_ALLOWED, hidden=True)
        return
        
    age_data = sql.get_age(user.id)
    mention = user.mention

    msg = _get_message_for_age(ctx, age_data, mention)

    log_debug(ctx, f"{msg}")
    await ctx.send(content=msg, hidden=True)

opts = [discord_slash.manage_commands.create_option(name="user_id", description="User ID to check", option_type=3, required=True)]
@slash.slash(name="agealt", description="Check a user's reported age (search by id)", options=opts, guild_ids=guild_ids)
async def _idage(ctx: SlashContext, **kwargs):
    await ctx.defer(hidden=True)
    
    _user_id = kwargs["user_id"]
    _author_roles = [role.id for role in ctx.author.roles]
    log_info(ctx, f"{ctx.author} requested age for ID {_user_id}")
    if (ctx.author_id != admin_id) and not (divine_role_id in _author_roles or secretary_role_id in _author_roles):
        log_debug(ctx, f"{ctx.author} cannot check ages")
        await ctx.send(content=MSG_NOT_ALLOWED, hidden=True)
        return

    try:
        user_id = int(_user_id)
    except ValueError:
        log_debug(ctx, f"{ctx.author} {_user_id} casting failed")
        await ctx.send(content="That is not a valid ID", hidden=True)
        return
        
    user = bot.get_user(user_id)
    age_data = sql.get_age(user_id)
    mention = f"{user_id}" if user is None else f"{user.mention}"

    msg = _get_message_for_age(ctx, age_data, mention)

    log_debug(ctx, f"{msg}")
    await ctx.send(content=msg, hidden=True)

opts = [discord_slash.manage_commands.create_option(name="pasta", description="Copy pasta", option_type=3, required=True, choices=copypasta_utils.AVAILABLE_PASTAS)]
opts += [discord_slash.manage_commands.create_option(name="name", description="Who your pasta is about", option_type=3, required=True)]
opts += [discord_slash.manage_commands.create_option(name="pronouns", description="Which pronouns to use", option_type=3, required=True, choices=copypasta_utils.PRON_OPTS)]
@slash.slash(name="pasta", description="Generate a copy pasta", options=opts, guild_ids=guild_ids)
async def _pasta(ctx: SlashContext, **kwargs):
    _pasta = kwargs["pasta"]
    _name = kwargs["name"]
    _pronouns = kwargs["pronouns"]
    log_info(ctx, f"{ctx.author} requested copypasta: {_pasta} for {_name} ({_pronouns})")

    if "botto" in _name.lower():
        await ctx.send(content=f"I'm not gonna write myself into your copypasta, {ctx.author.mention}~", hidden=False)
        return

    try:
        msg = f"{ctx.author.mention} says: \"" + copypasta_utils.fill_copypasta(_pasta, _name, _pronouns) + "\""
    except KeyError:
        msg = "Hmm I can't fill that pasta with the data you provided..."

    await ctx.send(content=msg, hidden=False)

opts = [discord_slash.manage_commands.create_option(name="enable", description="Enable (on) or disable (off) notifications", option_type=3, required=True, choices=["on", "off"])]
@slash.slash(name="offlinepings", description="Update settings on whether to notify you about pings while you're offline", options=opts, guild_ids=guild_ids)
async def _offlinepings(ctx: SlashContext, **kwargs):
    _state = kwargs["enable"]
    log_info(ctx, f"{ctx.author} requested offlinepings: {_state}")

    if _state == "on":
        sql.remove_from_offline_ping_blocklist(ctx.author_id)
        await ctx.send(content="Okay, I'll let you know if you're pinged~", hidden=True)
    else:
        sql.add_to_offline_ping_blocklist(ctx.author_id)
        await ctx.send(content="Okay, I won't send you notifications if you're pinged~", hidden=True)

opts = [discord_slash.manage_commands.create_option(name="range", description="Max days to fetch", option_type=4, required=False)]
opts += [discord_slash.manage_commands.create_option(name="user", description="User to search (will get messages from all users by default)", option_type=6, required=False)]
@slash.slash(name="activity", description="Get analytics data for useractivity", options=opts, guild_ids=guild_ids)
async def _activity(ctx: SlashContext, **kwargs):
    await ctx.defer()

    log_info(ctx, f"{ctx.author} requested activity")
    if (ctx.author_id != admin_id) and not (divine_role_id in [role.id for role in ctx.author.roles]):
        log_debug(ctx, f"{ctx.author} cannot get activity")
        await ctx.send(content=MSG_NOT_ALLOWED, hidden=True)
        return

    await ctx.send(content=f"This functionality is not available yet, try again later~")

opts = [discord_slash.manage_commands.create_option(name="which", description="Bingo sheet to retrieve (will get a random one by default)", option_type=3, required=False, choices=memes.get_bingos())]
@slash.slash(name="bingo", description="Get a clean bingo sheet!", options=opts, guild_ids=guild_ids)
async def _bingo(ctx: SlashContext, **kwargs):
    await ctx.defer()

    if "bingo" in kwargs:
        bingo_name = memes.bingo_filepath(kwargs["bingo"])
        log_info(ctx, f"{ctx.author} requested bingo: {bingo_name}")
    else:
        bingo_name = memes.bingo_filepath(random.choice(memes.get_bingos()))
        log_info(ctx, f"{ctx.author} requested random bingo: {bingo_name}")

    bingo_file = discord.File(bingo_name, filename=f"bingo.png")

    await ctx.send(content=f"Hope you get a bingo~", file=bingo_file)

@slash.slash(name="suicide", description="...", guild_ids=guild_ids)
async def _prevent(ctx: SlashContext, **kwargs):
    admin_user = bot.get_user(admin_id)
    dm_chan = admin_user.dm_channel or await admin_user.create_dm()
    await dm_chan.send(content=f"Please check on {ctx.author.mention} if possible")

    msg = f"Hey {ctx.author.display_name}! I hope you're doing okay, and you just tested this command for the memes!\n"
    msg += f"In any case, please remember you're never alone, alright? You've got lots of people both online and IRL who care about you and maybe you don't even realize it.\n"
    msg += f"Please please please reach out to someone you trust if you're feeling down. If you need, you can also google \"suicide prevention\" to get the hotline number for your country: https://www.google.com/search?q=suicide+prevention\n"
    msg += f"Suicide is never the answer, okay? It may seem like they way out in a place of desperation, but you will get through this rough patch... {admin_user.mention} & I believe in you, friend!"

    await ctx.send(content=msg, hidden=True)

opts = [discord_slash.manage_commands.create_option(name="file", description="File to connect", option_type=3, required=True, choices=db.sql_files)]
opts += [discord_slash.manage_commands.create_option(name="query", description="SQL query", option_type=3, required=True)]
@slash.slash(name="rawsql", description="Perform a SQL query", options=opts, guild_ids=guild_ids)
async def _rawsql(ctx: SlashContext, **kwargs):
    await ctx.defer(hidden=True)
    
    _file = kwargs["file"]
    _query = kwargs["query"]
    log_info(ctx, f"{ctx.author} requested sql query for {_file}")
    if (ctx.author_id != admin_id):
        log_debug(ctx, f"{ctx.author} cannot query db")
        await ctx.send(content=MSG_NOT_ALLOWED, hidden=True)
        return

    try:
        data = sql.raw_sql(_file, _query)
    except sqlite3.DatabaseError as e:
        log_debug(ctx, f"{ctx.author} query [{_query}] failed : {e}")
        await ctx.send(content=f"Failed to execute query [{_query}]:\n```\n{traceback.format_exc()}\n```", hidden=True)
        return
    except Exception as e:
        log_debug(ctx, f"{ctx.author} query [{_query}] failed : {e}")
        await _dm_log_error(f"[{ctx.channel}] _rawsql\n{e}\n{traceback.format_exc()}")
        await ctx.send(content="Failed to execute query", hidden=True)
        return
        
    if data is None:
        msg = "Your query returned None"
    else:
        msg = f"Here are the results for your query:\n```\n{_query}\n\n"
        msg += "\n".join(" | ".join([str(idx + 1)] + [str(item) for item in line]) for idx, line in enumerate(data))
        msg += "\n```"
        if len(msg) > 2000:
            aux = "```\nTRUNC"
            msg = msg[:2000-len(aux)-1] + aux
    await ctx.send(content=msg, hidden=True)

opts = [discord_slash.manage_commands.create_option(name="date", description="When to fetch data", option_type=3, required=False)]
opts += [discord_slash.manage_commands.create_option(name="hidden", description="Hide or show response", option_type=5, required=False)]
@slash.slash(name="dailytopten", description="Perform a SQL query", options=opts, guild_ids=guild_ids)
async def _rawsql(ctx: SlashContext, **kwargs):
    _hidden = kwargs["hidden"] if "hidden" in kwargs else True
    await ctx.defer(hidden=_hidden)
    
    _date = kwargs["date"] if "date" in kwargs else (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    _pdate = datetime.datetime.strptime(_date, "%Y-%m-%d")
    log_info(ctx, f"{ctx.author} requested daily top 10 for {_date}")
    if (ctx.author_id != admin_id):
        log_debug(ctx, f"{ctx.author} cannot query db")
        await ctx.send(content=MSG_NOT_ALLOWED, hidden=True)
        return

    try:
        data = sql.get_dailytopten(_date, game_channel_ids)
    except sqlite3.DatabaseError as e:
        log_debug(ctx, f"{ctx.author} query daily top ten failed : {e}")
        await ctx.send(content=f"Failed to execute query:\n```\n{traceback.format_exc()}\n```", hidden=True)
        return
    except Exception as e:
        log_debug(ctx, f"{ctx.author} query for daily top ten failed : {e}")
        await _dm_log_error(f"[{ctx.channel}] _rawsql\n{e}\n{traceback.format_exc()}")
        await ctx.send(content="Failed to execute query", hidden=True)
        return
        
    if data is None:
        msg = "Your query returned None"
        _hidden = True
    else:
        msg = f"Top 10 users for {utils.to_date(_pdate)}!\n"
        msg += "\n".join(" | ".join([utils.to_podium(idx + 1), utils.to_mention(line[0]), str(line[1])]) for idx, line in enumerate(data))
        msg += "\n"
        if len(msg) > 2000:
            aux = "\nTRUNC"
            msg = msg[:2000-len(aux)-1] + aux
    await ctx.send(content=msg, hidden=_hidden)

opts = [discord_slash.manage_commands.create_option(name="user", description="User ID to block", option_type=3, required=True)]
opts += [discord_slash.manage_commands.create_option(name="reason", description="Reason for block", option_type=3, required=True)]
@slash.slash(name="autoblock", description="Pre-block a user before they've even joined", options=opts, guild_ids=guild_ids)
async def _autoblock(ctx: SlashContext, **kwargs):
    await ctx.defer(hidden=True)

    user = kwargs["user"]
    reason = kwargs["reason"]
    mod = ctx.author
    _author_roles = [role.id for role in ctx.author.roles]
    log_info(ctx, f"{ctx.author} requested age for {user}")
    if (ctx.author_id != admin_id) and not (divine_role_id in _author_roles or secretary_role_id in _author_roles):
        log_debug(ctx, f"{ctx.author} cannot autoblock")
        await ctx.send(content=MSG_NOT_ALLOWED, hidden=True)
        return

    try:
        user_id = int(user)
    except:
        log_debug(ctx, f"{user} is not a valid ID")
        await ctx.send(content=f"{user} is not a valid ID", hidden=True)
        return
        
    data = sql.try_autoblock(user_id, mod.id, reason)
    if data is None:
        msg = f"I'll ban them if they ever set foot here, {ctx.author.mention}~"
    else:
        prev_mod_id, prev_reason, date = data
        prev_mod = bot.get_user(prev_mod_id)
        msg = f"That user has already been pre-blocked by {prev_mod.mention} on {date}: {prev_reason}"
    await ctx.send(content=msg, hidden=True)

bot.run(TOKEN)
