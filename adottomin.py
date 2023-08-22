import asyncio
import datetime
import sqlite3
from dateutil import tz
import discord
import os
import random
import re
import string
import traceback
import time
import typing
import urllib.parse

from regex import R

import advertisements
import age_handling
import botlogger
import bot_utils
import copypasta_utils
import db
import emojionly
import games
import ghostpings
import graphlytics
import kinks
import memes
import mistletoe
import moderation
import modnotes
import msg_handler_manager
import propervider as p
import shipper
import nohorny

from word_blocklist import blocklist

from flask import Flask
from dotenv import load_dotenv
from os.path import exists

load_dotenv()
TOKEN = p.pstr('DISCORD_TOKEN')

RAID_MODE_CTRL = "raid.txt"
RAID_MODE = False

LENIENCY_TIME_S = 5 * 60 # time to reply
LENIENCY_REMINDER_TIME_S = 3 * 60 # time before sending a reminder (can be None)
LENIENCY_COUNT = 5 # messages before ban
LENIENCY_REMINDER = 3 # messages before asking again (can be None)

WARNING_VALIDITY_DAYS = 30
WARNINGS_BEFORE_BAN = 3

REDO_ALL_PINS = False
REDO_ALL_ALIASES = False
REDO_ALL_ROLES = False

assert (LENIENCY_REMINDER_TIME_S is None) or (LENIENCY_REMINDER_TIME_S < LENIENCY_TIME_S), "Reminder time must be smaller than total time"
assert (LENIENCY_REMINDER is None) or (LENIENCY_REMINDER < LENIENCY_COUNT), "Reminder count must be smaller than total leniency"

MSG_NOT_ALLOWED = "You're not allowed to use this command :3"
MSG_RAID_MODE_ON = "{} just turned raid mode **ON**, brace for impact!"
MSG_RAID_MODE_OFF = "{} just turned raid mode **OFF**, we live to see another day!"
MSG_GATEKEEP_MODE_ON = "{} just turned gatekeep mode **ON**, finally some peace and quiet~"
MSG_GATEKEEP_MODE_OFF = "{} just turned gatekeep mode **OFF**, now be nice or i'll silence y'all again~"
MSG_RAID_MODE_ON_ALREADY = "Raid mode is already on"
MSG_RAID_MODE_OFF_ALREADY = "Raid mode is already off"
MSG_CANT_DO_IT = "I can't do that to that user~ :3"
MSG_USER_ALREADY_MAXED = "That user is already at max tier!"
MSG_USER_ALREADY_MOON = "That user is already a moon fur-iend!"
MSG_CONGRATULATIONS_PROMOTION = "Congratulations on your promotion to tier {}, {}!"

bot_home = os.getenv("BOT_HOME") or os.getcwd()

GUILD_ID = p.pstr('GUILD_ID')
GUILD_OBJ = discord.Object(id=GUILD_ID)

channel_ids = p.plist('CHANNEL_IDS')
role_ids = p.plist('AGE_ROLE_IDS')
tally_channel = p.pint('TALLY_CHANNEL_ID')
nohorny_channels = p.plist('NOHORNY_CHANNEL_IDS', required=False)
log_channel = p.pint('LOG_CHANNEL_ID')
ad_channel = p.pint('AD_CHANNEL_ID')
emojionly_channel = p.pint('EMOJI_CHANNEL_ID')
chats_home = os.getenv('CHATS_HOME')
purgeable_channels = p.plist('PURGEABLE_CHANNEL_IDS', required=False)
chatbot_service = os.getenv('CHATBOT_SERVICE')

queen_role_id = p.pint('QUEEN_ROLE_ID')
owner_role_id = p.pint('OWNER_ROLE_ID')
divine_role_id = p.pint('DIVINE_ROLE_ID')
secretary_role_id = p.pint('SECRETARY_ROLE_ID')
dogretary_role_id = p.pint('DOGRETARY_ROLE_ID')
nsfw_role_id = p.pint('NSFW_ROLE_ID')
jail_role_id = p.pint('JAIL_ROLE_ID')
minor_role_id = p.pint('MINOR_ROLE_ID', required=False)
friends_role_ids = p.plist('FRIENDS_ROLE_IDS')
moon_role_id = p.pint('MOON_ROLE_ID', required=False)
ad_poster_role_id = p.pint('AD_POSTER_ROLE_ID')

game_channel_ids = p.plist('GAME_CHANNEL_IDS')

pin_archive_channel_id = p.pint('PIN_ARCHIVE_CHANNEL_ID')
pin_archive_blocklist_ids = p.plist('PIN_ARCHIVE_BLOCKLIST_IDS')

admin_id = p.pint('ADMIN_ID')
_aux = os.getenv('POI_USER_IDS')
poi_user_ids = [int(id) for id in _aux.split('.') if id != ""]

pendelton_mode = False

ignore_roles_for_database = set([jail_role_id, minor_role_id, ad_poster_role_id])

usernames_blocked = [
    "pendelton",
    "pennington"
]

blocklist_prog = re.compile("|".join([f'\\b{word}\\b' for word in blocklist]), flags=re.IGNORECASE)

gatekeep_perms = {'send_messages': False}

ignore_prefixes = ('$')

advertisement_slowmode = datetime.timedelta(seconds=30)

file_ext_prog = re.compile(r".+\.([a-zA-Z0-9]+)$", flags=re.IGNORECASE)

logger = botlogger.get_logger("adottomin")

class BottoBot(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)

    async def setup_hook(self):
        self.tree.copy_global_to(guild=GUILD_OBJ)
        try:
            await self.tree.sync(guild=GUILD_OBJ)
        except Exception as e:
            logger.error(f"Failed to sync command tree : {e} | {traceback.format_exc()}")
            exit(1)

bot = BottoBot(intents=discord.Intents.all())

def log_debug(interaction: discord.Interaction, msg: str):
    logger.debug(f"[{interaction.channel}] {msg}")

def log_info(interaction: discord.Interaction, msg: str):
    logger.info(f"[{interaction.channel}] {msg}")

def log_warn(interaction: discord.Interaction, msg: str):
    logger.warning(f"[{interaction.channel}] {msg}")

def log_error(interaction: discord.Interaction, msg: str):
    logger.error(f"[{interaction.channel}] {msg}")

logger.info(f"Channel ID = {channel_ids[0]}")
logger.info(f"Guild ID = {GUILD_ID}")
logger.info(f"Role IDs = {role_ids}")
logger.info(f"Tallly channel IDs = {tally_channel}")

mhm = msg_handler_manager.HandlerManager(admin_id, bot)
sql = db.database(LENIENCY_COUNT)
utils = bot_utils.utils(bot, sql, mhm, [divine_role_id, secretary_role_id], chatbot_service)
mod = moderation.ModerationCore(bot, sql, utils, mhm, secretary_role_id)
age_handler = age_handling.age_handler(bot, sql, utils, mod, role_ids, LENIENCY_COUNT - LENIENCY_REMINDER)
ad_handler = advertisements.advert_handler(advertisement_slowmode, ad_channel, sql, utils)
emojionly_handler = emojionly.emojionly_handler(bot, sql, emojionly_channel)
nohorny_handler = nohorny.horny_handler(bot, utils, sql, nohorny_channels, jail_role_id)
mistletoe_handler = mistletoe.mistletoe_handler(mhm)

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
        logger.error(f"Error while trying to log error: {e}\n{traceback.format_exc()}")

def _get_message_for_age(ctx: discord.Interaction, age_data, mention):
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
    logger.info(f"{bot.user} has connected to Discord")
    main_channel = bot.get_channel(channel_ids[0])
    utils.inject_admin(bot.get_user(admin_id))
    utils.inject_pois([bot.get_user(id) for id in poi_user_ids])
    guild = await bot.fetch_guild(GUILD_ID)
    await utils.inject_guild(guild)
    await utils.on_utils_setup()
    age_handler.inject(main_channel, bot.get_channel(tally_channel), bot.get_channel(log_channel))
    ad_handler.inject_ad_channel(bot.get_channel(ad_channel))
    nohorny_handler.inject(main_channel)
    mod.inject(bot.get_channel(log_channel))

    if REDO_ALL_PINS:
        for channel in bot.get_all_channels():
            await on_guild_channel_pins_update(channel, None)

    all_roles = await guild.fetch_roles()
    for role in all_roles:
        # Ignore roles if the bot cannot assign (or if they are bot roles)
        if (role.is_integration()) or (role.name == "@everyone"):
            ignore_roles_for_database.add(role.id)
    logger.info(f"Updated list of ignored roles: {[guild.get_role(role) for role in ignore_roles_for_database]}")
        
    if REDO_ALL_ALIASES or REDO_ALL_ROLES:
        async for member in guild.fetch_members():
            if REDO_ALL_ALIASES:
                await _handle_new_alias(None, member)
            if REDO_ALL_ROLES:
                sql.redo_roles(member.id, set([role.id for role in member.roles]).difference(ignore_roles_for_database))

    logger.info(f"Finished on_ready setup")


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    def _validate_channel(vc: discord.VoiceState):
        # Do not track users in AFK channels, or users deafened (since they are not actively participating)
        return (not vc.afk) and (not vc.deaf) and (not vc.self_deaf)

    def _activity(vc: discord.VoiceState):
        if vc.self_video:
            return 'video'
        if vc.self_stream:
            return 'stream'
        return 'voice'
    
    if member.bot:
        return

    if after.channel and not before.channel: # User joined a voice channel
        logger.debug(f"{member} just joined VC {after.channel}")
        if not _validate_channel(after): 
            logger.debug(f"{member} just joined invalid VC (ignore)")
            return
        sql.register_join_vc(member.id, after.channel.id, _activity(after))
        return

    if before.channel and not after.channel: # User left a voice channel
        logger.debug(f"{member} just left VC {before.channel}")
        if not _validate_channel(before): 
            logger.debug(f"{member} just left invalid VC (ignore)")
            return
        sql.register_leave_vc(member.id, before.channel.id, _activity(before))
        return

    if after.channel and before.channel: # Other
        _valid_before = _validate_channel(before)
        _valid_after = _validate_channel(after)
        _act_before = _activity(before)
        _act_after = _activity(after)
        if after.channel.id != before.channel.id: # User changed voice channel
            logger.debug(f"{member} just left VC {before.channel} (valid={_valid_before}) and joined {after.channel} (valid={_valid_after})")

            if _valid_before:
                logger.debug(f"{member} previous VC {before.channel} is valid")
                sql.register_leave_vc(member.id, before.channel.id, _act_before)
            else:
                logger.debug(f"{member} previous VC {before.channel} is NOT valid")

            if _valid_after:
                logger.debug(f"{member} current VC {after.channel} is valid")
                sql.register_join_vc(member.id, after.channel.id, _act_after)
            else:
                logger.debug(f"{member} current VC {after.channel} is NOT valid")

            return

        if _valid_before and _valid_after: # Check if user activity changed
            if _act_before != _act_after:
                logger.debug(f"{member} just changed activity in VC {before.channel} ({_act_before}->{_act_after})")
                sql.register_leave_vc(member.id, before.channel.id, _act_before)
                sql.register_join_vc(member.id, after.channel.id, _act_after)
            else:
                logger.debug(f"{member} is still in VC {before.channel} but action does not warrant tracking")

        elif _valid_before and not _valid_after: # User exited a valid state
            logger.debug(f"{member} just exited valid state in VC {before.channel}")
            sql.register_leave_vc(member.id, before.channel.id, _act_before)

        elif not _valid_before and _valid_after: # User entered a valid state
            logger.debug(f"{member} just entered valid state in VC {after.channel}")
            sql.register_join_vc(member.id, after.channel.id, _act_after)

        else: # User is still in the same channel (un/muted, un/deafened, started/stopped streaming)
            logger.debug(f"{member} is still in VC {before.channel} but action does not warrant tracking")

    else:
        logger.debug(f"{member} changed VC state but both after and before are None")

async def _handle_nsfw_added(before: discord.Member, after: discord.Member):
    if (nsfw_role_id in utils.role_ids(before)) or (nsfw_role_id not in utils.role_ids(after)): return
    if not utils.just_joined(before.id): 
        logger.info(f"{after} added nsfw role and is a previous user")
        return
    user_age_roles = set([role.id for role in after.roles]).intersection(set(role_ids))
    if user_age_roles != set(): 
        logger.info(f"{after} added nsfw role and has age tags: {user_age_roles}")
        return
    nsfw_role = discord.utils.get(after.guild.roles, name="NSFW")
    logger.info(f"{after} added nsfw role but is still being verified")
    await after.remove_roles(*[nsfw_role], reason="Not verified", atomic=False)
    notif = after.guild.get_channel(channel_ids[0])
    await notif.send(content=f"Straight for the NSFW and didn't even tell me your age, {after.mention}?~")
    # await utils.send_poi_dms(f"{after.mention} just got told off for going straight for NSFW~")

async def _handle_minor_role_added(before: discord.Member, after: discord.Member):
    if not minor_role_id: return
    if (minor_role_id in utils.role_ids(before)) or (minor_role_id not in utils.role_ids(after)): return
    minor_role = discord.utils.get(after.guild.roles, id=minor_role_id)
    notif = after.guild.get_channel(channel_ids[0])
    if not utils.just_joined(before.id): 
        logger.info(f"{after} added minor role and is a previous user")
        await notif.send(content=f"Careful there {after.mention}, remember to refuse if anyone offers you candy~")
        await after.remove_roles(*[minor_role], reason="Age bait role", atomic=False)
        return
    
    logger.info(f"{after} added minor role but is still being verified")
    await notif.send(content=f"{after.mention} caught the bait~")
    await age_handler.kick_or_ban(after, age=minor_role_id, force_update_age=True, reason="Chose minor age role", force_ban=True)

async def _handle_user_role_database(before: discord.Member, after: discord.Member):
    if before.bot: return

    after_roles = set([role.id for role in after.roles])
    before_roles = set([role.id for role in before.roles])

    added_roles = after_roles.difference(before_roles, ignore_roles_for_database)
    removed_roles = before_roles.difference(after_roles, ignore_roles_for_database)
    logger.debug(f"Added {added_roles} for {after}")
    logger.debug(f"Removed {removed_roles} for {after}")

    if added_roles:
        sql.add_roles(after.id, added_roles)
    if removed_roles:
        sql.remove_role(after.id, removed_roles)

async def _handle_new_alias(before: typing.Optional[discord.Member], after: discord.Member):
    if before is not None and after.display_name == before.display_name:
        # logger.debug(f"{after} did not change alias")
        return
    old_aliases = utils.get_unique_aliases(after)
    if after.display_name in old_aliases: 
        logger.info(f"{after} added known alias {after.display_name}")
        return
    logger.info(f"{after} adding new alias {after.display_name}")
    sql.create_alias(after.id, after.display_name)

member_update_handlers = [
    _handle_nsfw_added,
    _handle_minor_role_added,
    _handle_new_alias,
    _handle_user_role_database,
    lambda before, after: nohorny_handler.handle_horny_role_toggle(
        before,
        after,
        lambda: mhm.create_dyn_lock(nohorny_handler.handle_horny, before.id),
        lambda: mhm.remove_dyn_lock(nohorny_handler.handle_horny, before.id)),
    nohorny_handler.handle_member_remove_horny
]

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    for handler in member_update_handlers:
        try:
            await handler(before, after)
        except Exception as e:
            logger.error(f"Error during on_member_update: {e}\n{traceback.format_exc()}")
            await _dm_log_error(f"on_member_update\n{e}\n{traceback.format_exc()}")

reaction_blocklist = []
reaction_user_blocklist = []#[954175797495746621]

@bot.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.Member):
    emoji = reaction.emoji if type(reaction.emoji) == str else reaction.emoji.name
    if emoji in reaction_blocklist or user.id in reaction_user_blocklist:
        logger.info(f"Reaction blocklisted, removing")
        await reaction.remove(user)

mhm.register_static_list([
    utils.handle_invite_link,
    utils.handle_dm,
    utils.handle_dm_cmd,
    utils.handle_failed_command,
    # utils.handle_binary, # has not been needed in a while
    utils.handle_puppeteering,
    emojionly_handler.handle_emoji_chat
])

mhm.register_dynamic(age_handler.handle_age)
mhm.register_dynamic(nohorny_handler.handle_horny)
mhm.register_dynamic(utils.handle_cork_board_post)

message_edit_handlers = [
    emojionly_handler.handle_emoji_chat_edit
]

async def execute_handlers(msg: discord.Message, handlers: typing.List[typing.Callable]):
    for handle in handlers:
        try:
            # logger.debug(f"Running handler {handle.__name__}")
            await handle(msg)
        except bot_utils.HandlerIgnoreException:
            pass
        except Exception as e:
            logger.error(f"[{msg.channel}] Error during {handle.__qualname__}: {e}\n{traceback.format_exc()}")
            await _dm_log_error(f"[{msg.channel}] on_message::{handle.__qualname__}\n{e}\n{traceback.format_exc()}")
            
async def execute_edit_handlers(before: discord.Message, after: discord.Message, handlers: typing.List[typing.Callable]):
    for handle in handlers:
        try:
            # logger.debug(f"Running handler {handle.__name__}")
            await handle(before, after)
        except bot_utils.HandlerException:
            pass
        except Exception as e:
            logger.error(f"[{after.channel}] Error during {handle.__qualname__}: {e}\n{traceback.format_exc()}")
            await _dm_log_error(f"[{after.channel}] on_message::{handle.__qualname__}\n{e}\n{traceback.format_exc()}")

@bot.event
async def on_message(msg: discord.Message):
    # if len(msg.content) == 0: return
    # logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} says \"{msg.content}\"")

    blocklist_match = blocklist_prog.search(msg.content.lower())
    if blocklist_match is not None:
        logger.info(f"[{msg.channel}] {msg.author} used blocked word: {blocklist_match.group(0)}")
        try:
            await msg.delete()
        except discord.errors.Forbidden:
            secrole = msg.guild.get_role(secretary_role_id)
            logger.error(f"[{msg.channel}] Forbidden from deleting msg {msg.id}")
            if secrole is not None:
                await msg.reply(content=f"Hey {secrole.mention}! This message has a blocked word but I can't delete it...")
            else:
                logger.error(f"[{msg.channel}] Secretary role is None!")
        warn = await msg.channel.send(content=f"Hey {msg.author.mention}, I'd think twice before posting that if I were you~")
        try:
            await warn.delete(delay=5.)
        except discord.errors.Forbidden:
            logger.error(f"[{msg.channel}] Forbidden from deleting blocked word warning")
        return

    await execute_handlers(msg, [utils.handle_offline_mentions])

    if msg.author.id == bot.user.id: return

    await mhm.on_message(msg)
        
    if not msg.author.bot:
        if msg.content.startswith(ignore_prefixes):
            return
        try:
            sql.register_message(msg.author.id, msg.id, msg.channel.id)
        except Exception as e:
            logger.error(f"[{msg.channel}] Error during register_message: {e}\n{traceback.format_exc()}")
            await _dm_log_error(f"[{msg.channel}] on_message::register_message\n{e}\n{traceback.format_exc()}")

@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    # Reuse code
    msg = after

    blocklist_match = blocklist_prog.search(msg.content.lower())
    if blocklist_match is not None:
        logger.info(f"[{msg.channel}] {msg.author} used blocked word: {blocklist_match.group(0)}")
        try:
            await msg.delete()
        except discord.errors.Forbidden:
            secrole = msg.guild.get_role(secretary_role_id)
            logger.error(f"[{msg.channel}] Forbidden from deleting msg {msg.id}")
            if secrole is not None:
                await msg.reply(content=f"Hey {secrole.mention}! This message has a blocked word but I can't delete it...")
            else:
                logger.error(f"[{msg.channel}] Secretary role is None!")
        warn = await msg.channel.send(content=f"Hey {msg.author.mention}, I'd think twice before posting that if I were you~")
        try:
            await warn.delete(delay=5.)
        except discord.errors.Forbidden:
            logger.error(f"[{msg.channel}] Forbidden from deleting blocked word warning")
        return

    if msg.author.id == bot.user.id: return

    await execute_edit_handlers(before, after, message_edit_handlers)

@bot.event
async def on_member_join(member: discord.Member):
    channel = bot.get_channel(channel_ids[0])
    logger.info(f"[{channel}] {member} just joined")
    try:
        if member.bot:
            logger.info(f"[{channel}] {member} is a bot, ignoring")
            return

        if member.id == bot.user.id: return

        sql.register_joiner(member.id)
        
        if RAID_MODE or is_raid_mode():
            logger.info(f"[{channel}] Raid mode ON: {member}")
            await age_handler.kick_or_ban(member, reason=age_handling.REASON_RAID)
            return

        autoblock = sql.is_autoblocked(member.id)
        if autoblock is not None:
            mod, reason, date = autoblock
            logger.info(f"[{channel}] {member} is PRE-blocked: {date}/{mod}: {reason}")
            await age_handler.kick_or_ban(member, reason=reason, force_ban=True)
            return

        for name in usernames_blocked:
            if name in member.name.lower():
                logger.info(f"[{channel}] {member} is name-blocked: annoying")
                await age_handler.kick_or_ban(member, reason="annoying", force_ban=True)
                return

        greeting = await channel.send(age_handling.MSG_GREETING.format(member.mention))
        sql.create_entry(member.id, greeting.id)
        mhm.create_dyn_lock(age_handler.handle_age, member.id)

        if pendelton_mode:
            await greeting.reply(content=f"{member.mention} If someone asked you to say \"Pendelton\", or any other password, kindly ignore them!\nAnd, if you still can, tell them to suck an egg ^^")

        try:
            old_aliases = utils.get_unique_aliases(member)
            if len(old_aliases) > 0: # Returning user
                if member.display_name not in old_aliases: # New display name
                    exclusive_aliases = [f" Or should I say, {alias}?" for alias in old_aliases if alias != member.display_name]
                else: # Same display name
                    exclusive_aliases = ""
                await greeting.reply(content=f"Btw {member.mention} haven't I seen you before?{''.join(exclusive_aliases)}")
        except Exception as e:
            logger.error(f"[{channel}] Error during on_member_join::get_unique_aliases: {e}\n{traceback.format_exc()}")
            await _dm_log_error(f"[{channel}] [reminder] get_unique_aliases\n{e}\n{traceback.format_exc()}")

        try:
            await _handle_new_alias(None, member)
        except Exception as e:
            logger.error(f"[{channel}] Error during on_member_join::_handle_new_alias: {e}\n{traceback.format_exc()}")
            await _dm_log_error(f"[{channel}] [reminder] _handle_new_alias\n{e}\n{traceback.format_exc()}")

        try:
            await member.add_roles(member.guild.get_role(friends_role_ids[0]), reason='Just joined (ty Botto)!')
        except Exception as e:
            logger.error(f"[{channel}] Error during on_member_join::add_roles: {e}\n{traceback.format_exc()}")
            await _dm_log_error(f"[{channel}] [reminder] add_roles\n{e}\n{traceback.format_exc()}")

        must_continue = True
        if (LENIENCY_REMINDER_TIME_S is not None):
            logger.debug(f"[{channel}] {member} Waiting to send reminder")
            await asyncio.sleep(LENIENCY_REMINDER_TIME_S)
            try:
                must_continue = await age_handler.do_age_check(channel, member, is_reminder=True)
                if not must_continue:
                    logger.debug(f"[{channel}] Early exit on_member_join")
                    mhm.remove_dyn_lock(age_handler.handle_age, member.id)
                    return
                else:
                    logger.debug(f"[{channel}] {member} Sending reminder message")
                    await channel.send(age_handling.MSG_GREETING_REMINDER.format(member.mention))
            except Exception as e:
                logger.error(f"[{channel}] Error during on_member_join: {e}\n{traceback.format_exc()}")
                await _dm_log_error(f"[{channel}] [reminder] do_age_check\n{e}\n{traceback.format_exc()}")

        await asyncio.sleep(LENIENCY_TIME_S if LENIENCY_REMINDER_TIME_S is None else LENIENCY_TIME_S - LENIENCY_REMINDER_TIME_S)
        try:
            await age_handler.do_age_check(channel, member)
        except Exception as e:
            logger.error(f"[{channel}] Error during on_member_join: {e}\n{traceback.format_exc()}")
            await _dm_log_error(f"[{channel}] [final] do_age_check\n{e}\n{traceback.format_exc()}")
        
        logger.debug(f"[{channel}] Exit on_member_join")
        mhm.remove_dyn_lock(age_handler.handle_age, member.id)

    except Exception as e:
        logger.error(f"[{channel}] Error during on_member_join: {e}\n{traceback.format_exc()}")
        await _dm_log_error(f"[{channel}] on_member_join\n{e}\n{traceback.format_exc()}")
        logger.debug(f"[{channel}] Error exit on_member_join")

@bot.event
async def on_member_remove(member: discord.Member):
    logger.info(f"{member} exit the guild")

    # Remove advertisement (if it exists)
    await ad_handler.try_remove_advertisement(member.id)
    
    sql.register_leaver(member.id)

    for channel_id in purgeable_channels:
        await utils.purge_user_from_channel(bot.get_channel(channel_id), member.id, "User left the server")

@bot.event
async def on_guild_channel_pins_update(channel: typing.Union[discord.abc.GuildChannel, discord.Thread], last_pin: typing.Optional[datetime.datetime]):
    if channel.id in pin_archive_blocklist_ids:
        logger.debug(f"Ignoring pin update in {channel}")
        return

    try:
        try:
            all_pins = await channel.pins()
        except AttributeError:
            logger.debug(f"{channel} does not have pins")
            return

        # updated = False
        
        pin_channel = await bot.fetch_channel(pin_archive_channel_id)
        if pin_channel is None:
            logger.error(f"Pin channel {pin_archive_channel_id} does not exist")
            await channel.send("I couldn't find the pin archive channels... :c")
            return

        for pin in all_pins:
            try:
                if sql.is_pinned(pin.id):
                    return
                
                logger.info(f"Pinning message {pin.id} from channel {channel}")
                pinEmbed, pinAttachmentFile = await utils.core_message_as_embed(pin, add_jump=True)
                archived = await pin_channel.send(file=pinAttachmentFile, embed=pinEmbed)

                sql.register_pin(pin.id, archived.id)

                # if pinAttachmentFile:
                #     os.remove("trash/" + icon_name)
            except Exception as e:
                logger.error(f"Exception while trying to handle pin {pin.id}: {e}\n{traceback.format_exc()}")

    except Exception as e:
        logger.error(f"Exception while trying to handle pin updates: {e}\n{traceback.format_exc()}")

@bot.tree.command(description='Turn raid mode on or off (auto kick or ban)')
@discord.app_commands.describe(enable='Whether to turn raid mode on or off')
@discord.app_commands.choices(enable=[discord.app_commands.Choice(name="on", value="on"), discord.app_commands.Choice(name="off", value="off")])
async def raidmode(interaction: discord.Interaction, enable: discord.app_commands.Choice[str]):
    await utils.safe_defer(interaction)

    if enable.value == "on":
        if set_raid_mode():
            log_info(interaction, f"{interaction.user} enabled raidmode")
            await utils.safe_send(interaction, content=MSG_RAID_MODE_ON.format(interaction.user.mention), is_followup=True, send_anyway=True)
        else:
            log_debug(interaction, f"{interaction.user} enabled raidmode (already enabled)")
            await utils.safe_send(interaction, content=MSG_RAID_MODE_ON_ALREADY, is_followup=True, send_anyway=True)
    else:
        if unset_raid_mode():
            log_info(interaction, f"{interaction.user} disabled raidmode")
            await utils.safe_send(interaction, content=MSG_RAID_MODE_OFF.format(interaction.user.mention), is_followup=True, send_anyway=True)
        else:
            log_debug(interaction, f"{interaction.user} disabled raidmode (already disabled)")
            await utils.safe_send(interaction, content=MSG_RAID_MODE_OFF_ALREADY, is_followup=True, send_anyway=True)

    log_debug(interaction, f"raidmode state => {is_raid_mode()}")

@bot.tree.command(description='Turn gatekeep mode on or off (prevent t1 from using chats)')
@discord.app_commands.describe(enable='Whether to turn gatekeep mode on or off')
@discord.app_commands.choices(enable=[discord.app_commands.Choice(name="on", value="on"), discord.app_commands.Choice(name="off", value="off")])
async def gatekeep(interaction: discord.Interaction, enable: discord.app_commands.Choice[str]):
    await utils.safe_defer(interaction)

    if enable.value == "on":
        log_info(interaction, f"{interaction.user} enabled gatekeep")

        t1 = interaction.guild.get_role(friends_role_ids[0])
        newperms = discord.permissions.Permissions(permissions=t1.permissions.value)
        newperms.update(
            send_messages=False, 
            send_messages_in_threads=False, 
            create_public_threads=False,
            embed_links=False,
            attach_files=False,
            add_reactions=False,
            use_external_emojis=False,
            use_external_stickers=False,
            use_application_commands=False
        )
        
        # log_debug(interaction, f"t1={t1.id} ({t1})")
        # log_debug(interaction, f"old_perms={t1.permissions}")
        # log_debug(interaction, f"newperms={newperms}")
        try:
            await t1.edit(permissions=newperms)
            await utils.safe_send(interaction, content=MSG_GATEKEEP_MODE_ON.format(interaction.user.mention), is_followup=True, send_anyway=True)
        except discord.errors.Forbidden:
            await utils.safe_send(interaction, content="Forbidden error on editing role...", is_followup=True, send_anyway=True)
    else:
        log_info(interaction, f"{interaction.user} disabled gatekeep")

        t1 = interaction.guild.get_role(friends_role_ids[0])
        newperms = discord.permissions.Permissions(permissions=t1.permissions.value)
        newperms.update(
            send_messages=True, 
            send_messages_in_threads=True, 
            create_public_threads=True,
            embed_links=True,
            attach_files=True,
            add_reactions=True,
            use_external_emojis=True,
            use_external_stickers=True,
            use_application_commands=True
        )
        # log_debug(interaction, f"t1={t1.id} ({t1})")
        # log_debug(interaction, f"old_perms={t1.permissions}")
        # log_debug(interaction, f"newperms={newperms}")
        try:
            await t1.edit(permissions=newperms)
            await utils.safe_send(interaction, content=MSG_GATEKEEP_MODE_OFF.format(interaction.user.mention), is_followup=True, send_anyway=True)
        except discord.errors.Forbidden:
            await utils.safe_send(interaction, content="Forbidden error on editing role...", is_followup=True, send_anyway=True)

async def _meme(interaction: discord.Interaction, meme_code: str, user: typing.Optional[discord.Member]=None, text: str=None, msg=""):
    if not await utils.safe_defer(interaction): return

    log_info(interaction, f"{interaction.user} requested {meme_code}")

    _icon = await utils.get_icon_default(user)
    _author_icon = await utils.get_user_icon(interaction.user)
    _text = text or utils.get_text(user)
    log_debug(interaction, f"icon={_icon}, text={_text}")

    meme_name = memes.create_meme(meme_code, author_icon=_author_icon, icon=_icon, text=_text)
    log_debug(interaction, f"meme_name={meme_name}")

    if meme_name is None:
        await utils.safe_send(interaction, content="Oops, there was an error~", is_followup=True)
        return 

    meme_file = discord.File(meme_name, filename=f"{interaction.user.id}_{meme_code}.png")

    if len(msg) == 0:
        try:
            if (user.id == interaction.user.id):
                msg = "Lmao did you really make it for yourself??"
            if (user.id == bot.user.id):
                msg = f"Awww thank you, {interaction.user.mention}~"
        except:
            pass

    await utils.safe_send(interaction, content=msg, file=meme_file, is_followup=True, send_anyway=True)
    
    if _icon is not None:
        os.remove(_icon)

    if _author_icon is not None:
        os.remove(_author_icon)

    meme_file.close()
    os.remove(meme_name)

def make_user_meme_cmd(name, description, meme_code):
    @bot.tree.command(name=name, description=description)
    @discord.app_commands.describe(user="Who to use in the meme")
    async def _cmd(interaction: discord.Interaction, user: discord.Member):
        await _meme(interaction, meme_code, user=user)

user_meme_cmds = {
    'supremacy': ('supremacy', 'Do you believe?'),
    'deeznuts': ('deeznuts', 'Awww'),
    'pills': ('pills', 'You need those pills'),
    'bromeme': ('bromeme', 'Bro'),
    'mig': ('fivemins', 'Please'),
    'sally': ('sally', 'Your loss'),
    'walt': ('walt', 'Put it away'),
    'simpcard': ('simpcard', 'Officially recognized'),
    'peace': ('peace', 'Good for you'),
    'silence': ('silence', 'Bzzoooommmm!')
}

for cmd in user_meme_cmds:
    code, description = user_meme_cmds[cmd]
    make_user_meme_cmd(cmd, description, code)

@bot.tree.command(description='Traditional Maslow\'s hierarchy')
@discord.app_commands.describe(contents='What to say in the meme')
async def needs(interaction: discord.Interaction, contents: str):
    await _meme(interaction, "needs", text=contents)

@bot.tree.command(description='Get a custom bingo sheet!')
async def mybingo(
    interaction: discord.Interaction,
    element_1: str,    element_2: str,    element_3: str,    element_4: str,    element_5: str,
    element_6: str,    element_7: str,    element_8: str,    element_9: str,    element_10: str,
    element_11: str,   element_12: str,                      element_13: str,   element_14: str,
    element_15: str,   element_16: str,   element_17: str,   element_18: str,   element_19: str,
    element_20: str,   element_21: str,   element_22: str,   element_23: str,   element_24: str
):
    _args = [element_1, element_2, element_3, element_4, element_5, element_6, element_7, element_8, element_9, element_10, element_11, element_12, element_13, element_14, element_15, element_16, element_17, element_18, element_19, element_20, element_21, element_22, element_23, element_24]
    await _meme(interaction, "custom_bingo", text=[interaction.user.display_name] + _args, msg="Enjoy your custom bingo~")

@bot.tree.command(description='Get pinged!')
async def randomcitizen(interaction: discord.Interaction):
    guild = interaction.guild
    if guild is None: 
        await utils.safe_send(interaction, content=f"That command only works in a server!", ephemeral=True)
        return
    member = random.choice([member for member in guild.members if not member.bot])
    await _meme(interaction, "random_citizen", msg=f"Get pinged, {member.mention}~")

@bot.tree.command(description='Get many pinged!')
async def randomcitizens(interaction: discord.Interaction, amount: int):
    log_info(interaction, f"{interaction.user} requested {amount} randomcitizens")
    guild = interaction.guild
    if guild is None: 
        await utils.safe_send(interaction, content=f"That command only works in a server!", ephemeral=True)
        return
    if amount <= 0:
        await utils.safe_send(interaction, content=f"Try choosing a _natural_ number, silly~", ephemeral=True)
        return
    if amount > 10:
        await utils.safe_send(interaction, content=f"Oh geez, that's a lot of people! Maybe try a lil less~?", ephemeral=True)
        return
    members = random.choices([member for member in guild.members if not member.bot], k=amount)
    member_mentions = " and ".join([", ".join([member.mention for member in members[:-1]])] + [members[-1].mention]) if amount > 1 else members[0].mention
    await _meme(interaction, "random_citizen", msg=f"Get pinged, {member_mentions}~")

@bot.tree.command(description='Get a random fortune!')
async def fortune(interaction: discord.Interaction):
    fortune = memes.generate_fortune()
    random.seed(hash(memes.prepared_content(str(interaction.user.id))))
    total_nums = list(range(100))
    random.shuffle(total_nums)
    numbers = [f'`{total_nums[i]:02}`' for i in range(6)]
    msg = f"> {fortune}\nYour lucky numbers today: {', '.join(numbers)}"
    await utils.safe_send(interaction, content=msg, send_anyway=True)

@bot.tree.command(description='Ship yourself with someone!')
@discord.app_commands.describe(user='Who to ship you with')
async def shipme(interaction: discord.Interaction, user: discord.Member):
    log_info(interaction, f"{interaction.user} requested ship with {user}")
    if (user.id == interaction.user.id):
        await utils.safe_send(interaction, content=f"No selfcest, {interaction.user.mention}!")
        return

    if (user.id == bot.user.id):
        await utils.safe_send(interaction, content=f"I'm not shipping myself with you, {interaction.user.mention}~")
        return

    if (sql.is_noship(user.id)):
        await utils.safe_send(interaction, content=f"{user} requested not to be shipped~", ephemeral=True)
        return

    smaller = min(int(user.id), int(interaction.user.id))
    bigger = max(int(user.id), int(interaction.user.id))
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

    await utils.safe_send(interaction, content=f"The ship compatibility between {interaction.user.mention} and {user.mention} today is {emote} {pct}%{nice} :3", send_anyway=True)

@bot.tree.command(description='Ship yourself with people!')
@discord.app_commands.describe(user1='Who to ship you with', user2='Who else to ship you with')
async def shipus(interaction: discord.Interaction, user1: discord.Member, user2: discord.Member):
    log_info(interaction, f"{interaction.user} requested ship with {user1} and {user2}")
    if (user1.id == interaction.user.id or user2.id == interaction.user.id):
        await utils.safe_send(interaction, content=f"No selfcest, {interaction.user.mention}!")
        return

    if (user1.id == user2.id):
        await utils.safe_send(interaction, content=f"Try two different people, {interaction.user.mention}!")
        return

    if (user1.id == bot.user.id or user2.id == bot.user.id):
        await utils.safe_send(interaction, content=f"I'm not shipping myself with you, {interaction.user.mention}~")
        return

    if (sql.is_noship(user1.id)):
        await utils.safe_send(interaction, content=f"{user1} requested not to be shipped~", ephemeral=True)
        return

    if (sql.is_noship(user2.id)):
        await utils.safe_send(interaction, content=f"{user2} requested not to be shipped~", ephemeral=True)
        return

    ids = sorted([int(user1.id), int(user2.id), int(interaction.user.id)])
    pct, nice = memes.percent_from("ship/" + "/".join([str(id) for id in ids]))

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

    await utils.safe_send(interaction, content=f"The ship compatibility between {interaction.user.mention}, {user1.mention} and {user2.mention} today is {emote} {pct}%{nice} :3", send_anyway=True)

@bot.tree.command(description='Rate your gae!')
@discord.app_commands.describe(user='Who to rate (if empty, rates you)')
async def gayrate(interaction: discord.Interaction, user: typing.Optional[discord.Member]):
    user = user or interaction.user
    log_info(interaction, f"{interaction.user} requested gayrate for {user}")
    if (user.id == bot.user.id):
        await utils.safe_send(interaction, content=f"Wouldn't you like to know, {interaction.user.mention}~?")
        return

    pct, nice = memes.percent_from(f"gay/{int(user.id)}")

    await utils.safe_send(interaction, content=f"{user.mention} is :rainbow_flag: {pct}% gay today!{nice} :3", send_anyway=True)

@bot.tree.command(description='Rate your horny!')
@discord.app_commands.describe(user='Who to rate (if empty, rates you)')
async def hornyrate(interaction: discord.Interaction, user: typing.Optional[discord.Member]):
    user = user or interaction.user
    log_info(interaction, f"{interaction.user} requested hornyrate for {user}")
    if (user.id == bot.user.id):
        await utils.safe_send(interaction, content=f"Wouldn't you like to know, {interaction.user.mention}~?")
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

    await utils.safe_send(interaction, content=f"{user.mention} is {emote} {pct}% horny today!{nice} :3", send_anyway=True)

@bot.tree.command(description='Rate your gender!')
@discord.app_commands.describe(user='Who to rate (if empty, rates you)')
async def genderrate(interaction: discord.Interaction, user: typing.Optional[discord.Member]):
    user = user or interaction.user
    log_info(interaction, f"{interaction.user} requested genderrate for {user}")
    if (user.id == bot.user.id):
        await utils.safe_send(interaction, content=f"I'm **always** :100: gender, {interaction.user.mention}~")
        return

    pct, nice = memes.percent_from(f"gender/{int(user.id)}")
    if pct == 69:
        emote = ":sunglasses:"
    elif pct < 33:
        emote = ":confused:"
    elif pct < 66:
        emote = ":slight_smile:"
    else:
        emote = ":yum:"

    await utils.safe_send(interaction, content=f"{user.mention} is {emote} {pct}% gender today!{nice} :3", send_anyway=True)

@bot.tree.command(description='Explain it like you\'re a boomer')
@discord.app_commands.describe(expression='What to search')
async def boomersplain(interaction: discord.Interaction, expression: str):
    log_info(interaction, f"{interaction.user} requested definition for {expression}")

    def_data = memes.get_formatted_definition(expression)

    embed = discord.Embed(
        title=f"**{expression}**",
        colour=random.choice(bot_utils.EMBED_COLORS),
        timestamp=datetime.datetime.now()
    )
    
    if def_data:
        word_txt, meaning_txt, example_txt = def_data

        embed.title=f"**{word_txt}**"

        if meaning_txt is not None and len(meaning_txt) > 0:
            embed.add_field(name="Definition", value=meaning_txt, inline=False)

        if example_txt is not None and len(example_txt) > 0:
            embed.add_field(name="Usage", value=f"_{example_txt}_", inline=False)
    else:
        embed.add_field(name="Hmmm...", value=f"I couldn't find anything about that... Are you sure that's a real thing?", inline=False)
    
    # try:
    #     icon_url = interaction.user.avatar.url
    # except:
    #     icon_url = None

    # embed.set_author(name=f'Requested by {interaction.user.display_name}', icon_url=icon_url)
    await utils.safe_send(interaction, embed=embed, send_anyway=True)

@bot.tree.command(description='No horny in main!')
@discord.app_commands.describe(user='Who to mention (optional)')
async def horny(interaction: discord.Interaction, user: typing.Optional[discord.Member]):
    log_info(interaction, f"{interaction.user} requested No Horny for {user}")

    if interaction.channel.nsfw:
        log_debug(interaction, f"{interaction.channel} is marked as nsfw")
        await utils.safe_send(interaction, content=f"People are allowed to be horny here!", ephemeral=True)
        return

    if not await utils.safe_defer(interaction): return

    content = "No horny in main{}!".format(f", {user.mention}" if user is not None else "")

    meme_name = memes.no_horny
    meme_file = discord.File(meme_name, filename=meme_name)
    embed = discord.Embed()
    embed.set_image(url=f"attachment://{meme_name}")

    await utils.safe_send(interaction, content=content, file=meme_file, is_followup=True)

@bot.tree.command(description='Warn a user for bad behavior, auto bans if there are too many strikes')
@discord.app_commands.describe(user='User to warn', reason='Why are they being warned')
async def strike(interaction: discord.Interaction, user: discord.Member, reason: str):
    log_info(interaction, f"{interaction.user} requested strike for {user}: '{reason}'")

    if set(utils.role_ids(user)).intersection(set([divine_role_id, secretary_role_id])) != set():
        log_debug(interaction, f"{user} cannot be warned")
        await utils.safe_send(interaction, content=MSG_CANT_DO_IT, ephemeral=True)
        return

    active_strikes = sql.create_warning(user.id, interaction.user.id, reason, WARNING_VALIDITY_DAYS)

    if not utils._dm_user(f"Hey {user}! You're being warned cuz {reason}, and now you have {active_strikes} strikes~", user):
        log_warn(interaction, f"Failed to DM {user.id} regarding strike {active_strikes}")

    if active_strikes < WARNINGS_BEFORE_BAN:
        log_info(interaction, f"{user} now has {active_strikes} active strikes")
        msg = f"{user.mention} is being warned by {interaction.user.mention}! That's {active_strikes} strikes so far~"
        if len(reason) > 0:
            msg += f" Reason: {reason}"
        await utils.safe_send(interaction, content=msg)
    else:
        log_info(interaction, f"{user} now has {active_strikes} active strikes, and will be banned")
        msg = f"{user.mention} is being warned by {interaction.user.mention}! That's {active_strikes} strikes, and so you must go~"
        if len(reason) > 0:
            msg += f" Reason: {reason}"
        await utils.safe_send(interaction, content=msg)
        await age_handler.do_ban(user, reason=age_handling.REASON_WARNINGS, tally=False)

@bot.tree.command(description='Check the user\'s previous strikes')
@discord.app_commands.describe(user='User to check', all='Get all strikes (only gets active strikes by default)')
async def getstrikes(interaction: discord.Interaction, user: discord.Member, all: typing.Optional[bool]=False):
    log_info(interaction, f"{interaction.user} requested strikes for {user}")

    strikes = sql.get_warnings(user.id, None if all else WARNING_VALIDITY_DAYS)

    if (len(strikes) > 0):
        msg = f":warning: Here are {user.mention}'s strikes~\n```\n"
        for moderator, reason, date in strikes:
            mod = bot.get_user(moderator)
            msg += f"{date} by {mod.mention}: {reason}\n"
        msg += "```"
    else:
        msg = f":angel: {user.mention} doesn't have any"
        if not all:
            msg += " active"
        msg += f" strikes~"

    await utils.safe_send(interaction, content=msg)

@bot.tree.command(description='Promote a user to the next tier')
@discord.app_commands.describe(user='User to promote')
async def promote(interaction: discord.Interaction, user: discord.Member):
    log_info(interaction, f"{interaction.user} requested promotion for {user}")
    if not await utils.ensure_secretary(interaction): return

    _user_roles = [role.id for role in user.roles]
    if friends_role_ids[2] in _user_roles:
        log_debug(interaction, f"{user} already at max tier")
        await utils.safe_send(interaction, content=MSG_USER_ALREADY_MAXED, ephemeral=True)
        return

    if friends_role_ids[1] in _user_roles:
        if not await utils._ensure_roles(interaction, divine_role_id, dogretary_role_id): return
        msg = f"{user.mention} Congraitiualtionon tier3"
        new_role_id = friends_role_ids[2]
        
    else:
        log_debug(interaction, f"{user} will be promoted to tier 2")
        msg = MSG_CONGRATULATIONS_PROMOTION.format(2, user.mention)
        new_role_id = friends_role_ids[1]
        
    try:
        # member = interaction.guild.get_member(user.id)
        new_role = interaction.guild.get_role(new_role_id)
        # await member.add_roles(new_role, reason=f"{interaction.user} said so")
        await user.add_roles(new_role, reason=f"{interaction.user} said so")
        await utils.safe_send(interaction, content=msg, send_anyway=True)
    except discord.HTTPException as e:
        log_error(interaction, f"Failed to give role {new_role} to {user}")
        log_debug(interaction, e)
        await utils.safe_send(interaction, content="I still can't give promotions and it's probably Angie's fault~", ephemeral=True)

@bot.tree.command(description='Promote a user to moon tier')
@discord.app_commands.describe(user='User to promote')
async def promoonte(interaction: discord.Interaction, user: discord.Member):
    log_info(interaction, f"{interaction.user} requested promotion for {user}")

    _user_roles = [role.id for role in user.roles]
    if moon_role_id in _user_roles:
        log_debug(interaction, f"{user} already a moon furiend")
        await utils.safe_send(interaction, content=MSG_USER_ALREADY_MOON, ephemeral=True)
        return
        
    try:
        member = interaction.guild.get_member(user.id)
        new_role = interaction.guild.get_role(moon_role_id)
        await member.add_roles(new_role, reason=f"{interaction.user} said so")
        await utils.safe_send(interaction, content=f"{user.mention} corbobulation in lunar", send_anyway=True)
    except discord.HTTPException as e:
        log_error(interaction, f"Failed to give role {new_role} to {user}")
        log_debug(interaction, e)
        await utils.safe_send(interaction, content="I still can't give promotions and it's probably Angie's fault~", ephemeral=True)

@bot.tree.command(description='Check a user\'s reported age')
@discord.app_commands.describe(user='User to check')
async def age(interaction: discord.Interaction, user: discord.Member):
    if not await utils.safe_defer(interaction, ephemeral=True): return

    log_info(interaction, f"{interaction.user} requested age for {user}")
        
    age_data = sql.get_age(user.id)
    mention = user.mention

    msg = _get_message_for_age(interaction, age_data, mention)

    log_debug(interaction, f"{msg}")
    await utils.safe_send(interaction, content=msg, ephemeral=True, is_followup=True)

@bot.tree.command(description='Check a user\'s reported age (search by id)')
@discord.app_commands.describe(user_id='User ID to check')
async def agealt(interaction: discord.Interaction, user_id: str):
    if not await utils.safe_defer(interaction, ephemeral=True): return
    
    log_info(interaction, f"{interaction.user} requested age for ID {user_id}")

    try:
        user_id = int(user_id)
    except ValueError:
        log_debug(interaction, f"{interaction.user} {user_id} casting failed")
        await utils.safe_send(interaction, content="That is not a valid ID", ephemeral=True, is_followup=True)
        return
        
    user = bot.get_user(user_id)
    age_data = sql.get_age(user_id)
    mention = f"{user_id}" if user is None else f"{user.mention}"

    msg = _get_message_for_age(interaction, age_data, mention)

    log_debug(interaction, f"{msg}")
    await utils.safe_send(interaction, content=msg, ephemeral=True, is_followup=True)

@bot.tree.command(description='Generate a copy pasta')
@discord.app_commands.describe(pasta='Copy pasta', name='Who your pasta is about', pronouns='Which pronouns to use')
@discord.app_commands.choices(
    pasta=[discord.app_commands.Choice(name=p, value=p) for p in copypasta_utils.AVAILABLE_PASTAS],
    pronouns=[discord.app_commands.Choice(name=p, value=p) for p in copypasta_utils.PRON_OPTS]
)
async def pasta(interaction: discord.Interaction, pasta: discord.app_commands.Choice[str], name: str, pronouns: discord.app_commands.Choice[str]):
    _pasta = pasta.value
    _pronouns = pronouns.value
    log_info(interaction, f"{interaction.user} requested copypasta: {_pasta} for {name} ({_pronouns})")

    if "botto" in name.lower():
        await utils.safe_send(interaction, content=f"I'm not gonna write myself into your copypasta, {interaction.user.mention}~")
        return

    try:
        msg = f"{interaction.user.mention} says: \"" + copypasta_utils.fill_copypasta(_pasta, name, _pronouns) + "\""
    except KeyError:
        msg = "Hmm I can't fill that pasta with the data you provided..."

    await utils.safe_send(interaction, content=msg)

@bot.tree.command(description='Start simping for someone!')
@discord.app_commands.describe(user='Who you wanna simp for')
async def simp(interaction: discord.Interaction, user: discord.Member):
    log_info(interaction, f"{interaction.user} starting to simp: {user}")
    if user.id == interaction.user.id:
        await utils.safe_send(interaction, content="You can't simp for yourself~", ephemeral=True)
        return

    res = sql.start_simping(interaction.user.id, user.id)
    
    if res:
        msg = f"{interaction.user.mention} is simping for {user.mention}~"
        hidden = False
    else:
        msg = f"You're already simping for {user.mention}"
        hidden = True
    await utils.safe_send(interaction, content=msg, ephemeral=hidden, send_anyway=True)

@bot.tree.command(description='Stop simping for someone!')
@discord.app_commands.describe(user='Who you wanna stop simping for')
async def nosimp(interaction: discord.Interaction, user: discord.Member):
    log_info(interaction, f"{interaction.user} stopping to simp: {user}")
    if user.id == interaction.user.id:
        await utils.safe_send(interaction, content="You can't simp for yourself~", ephemeral=True)
        return

    res = sql.stop_simping(interaction.user.id, user.id)
    if res:
        msg = f"{interaction.user.mention} is not simping for {user.mention} anymore~"
        hidden = False
    else:
        msg = f"You're not simping for {user.mention}"
        hidden = True
    await utils.safe_send(interaction, content=msg, ephemeral=hidden)

@bot.tree.command(description='Validate your simp\'s affection')
@discord.app_commands.describe(user='Which simp you want to validate')
async def validatesimp(interaction: discord.Interaction, user: discord.Member):
    log_info(interaction, f"{interaction.user} validating simp: {user}")
    if user.id == interaction.user.id:
        await utils.safe_send(interaction, content="You can't simp for yourself~", ephemeral=True)
        return

    exists, success = sql.star_simping(user.id, interaction.user.id)
    if not exists:
        msg = f"{user.mention} is not simping for you"
        hidden = True
    elif not success:
        msg = f"{user.mention} is already validated"
        hidden = True
    else:
        msg = f"{interaction.user.mention} is validating {user.mention}'s simping~"
        hidden = False
    await utils.safe_send(interaction, content=msg, ephemeral=hidden)

@bot.tree.command(description='Invalidate your simp\'s affection')
@discord.app_commands.describe(user='Which simp you want to invalidate')
async def invalidatesimp(interaction: discord.Interaction, user: discord.Member):
    log_info(interaction, f"{interaction.user} invalidating simp: {user}")
    if user.id == interaction.user.id:
        await utils.safe_send(interaction, content="You can't simp for yourself~", ephemeral=True)
        return

    exists, success = sql.unstar_simping(user.id, interaction.user.id)
    if not exists:
        msg = f"{user.mention} is not simping for you"
        hidden = True
    elif not success:
        msg = f"{user.mention} isn't validated"
        hidden = True
    else:
        msg = f"{interaction.user.mention} is not validating {user.mention}'s simping anymore~"
        hidden = False
    await utils.safe_send(interaction, content=msg, ephemeral=hidden)
    
@bot.tree.command(description='Know who\'s simping for someone!')
async def simps(interaction: discord.Interaction, user: discord.Member):
    log_info(interaction, f"{interaction.user} checking simps: {user}")
    
    simps = sql.get_simps(user.id)
    
    if simps is None or len(simps) == 0:
        meme_name = memes.no_simps
        meme_file = discord.File(meme_name, filename=meme_name)
        # embed = discord.Embed()
        # embed.set_image(url=f"attachment://{meme_name}")
        await utils.safe_send(interaction, file=meme_file, content=f"No simps, {user.mention}?")
        return

    msg = f"Here are {user.mention}'s simps~\n> "
    msg += ", ".join([f"{':star:' if id[1] == 1 else ''}<@{id[0]}>" for id in simps])
    await utils.safe_send(interaction, content=msg, allowed_mentions=discord.AllowedMentions(users=[user]))

# opts = [discord_slash.manage_commands.create_option(name="range", description="Max days to fetch", option_type=4, required=False)]
# opts += [discord_slash.manage_commands.create_option(name="user", description="User to search (will get messages from all users by default)", option_type=6, required=False)]
@bot.tree.command(description='Get analytics data for user activity')
@discord.app_commands.describe(user='Who you want to query', ignore_games='Ignore messages sent in game channels (default is true)', range='How many days from the current date (default is 14)')
async def activity(interaction: discord.Interaction, user: discord.Member, ignore_games: bool=True, range: int=14):
    if not await utils.safe_defer(interaction, ephemeral=True): return

    log_info(interaction, f"{interaction.user} requested activity for {user}: {ignore_games}, {range}")
    if not await utils.ensure_secretary(interaction): return

    try:
        data = sql.get_activity(user.id, game_channel_ids if ignore_games else [], range)
    except sqlite3.DatabaseError as e:
        log_debug(interaction, f"{interaction.user} query activity failed : {e}")
        await utils.safe_send(interaction, content=f"Failed to execute query:\n```\n{traceback.format_exc()}\n```", ephemeral=True, is_followup=True)
        return
    except Exception as e:
        log_debug(interaction, f"{interaction.user} query for activity failed : {e}")
        await _dm_log_error(f"[{interaction.channel}] _rawsql\n{e}\n{traceback.format_exc()}")
        await utils.safe_send(interaction, content="Failed to execute query", ephemeral=True, is_followup=True)
        return
        
    if data is None or len(data) == 0:
        msg = "Your query returned None"
    else:
        msg = f"Here is {user.mention}'s daily activity!\n"
        msg += "\n".join([f'{line[0]}: {line[1]} {utils.plural("message", line[1])}' for line in data])
        msg += "\n"
        if len(msg) > 2000:
            aux = "\nTRUNC"
            msg = msg[:2000-len(aux)-1] + aux
    await utils.safe_send(interaction, content=msg, ephemeral=True, is_followup=True)

@bot.tree.command(description='Get a clean bingo sheet!')
@discord.app_commands.describe(which='Bingo sheet to retrieve (will get a random one by default)')
@discord.app_commands.choices(which=[discord.app_commands.Choice(name=b, value=b) for b in memes.get_bingos()])
async def bingo(interaction: discord.Interaction, which: typing.Optional[discord.app_commands.Choice[str]]):
    if not await utils.safe_defer(interaction): return

    if which is not None:
        bingo_name = memes.bingo_filepath(which.value)
        log_info(interaction, f"{interaction.user} requested bingo: {bingo_name}")
    else:
        bingo_name = memes.bingo_filepath(random.choice(memes.get_bingos()))
        log_info(interaction, f"{interaction.user} requested random bingo: {bingo_name}")

    bingo_file = discord.File(bingo_name, filename=f"bingo.png")

    await utils.safe_send(interaction, content=f"Hope you get a bingo~", file=bingo_file, is_followup=True)

@bot.tree.command(description='...')
async def suicide(interaction: discord.Interaction):
    admin_user = bot.get_user(admin_id)
    dm_chan = admin_user.dm_channel or await admin_user.create_dm()
    await dm_chan.send(content=f"Please check on {interaction.user.mention} if possible")

    msg = f"Hey {interaction.user.display_name}! I hope you're doing okay, and you just tested this command for the memes!\n"
    msg += f"In any case, please remember you're never alone, alright? You've got lots of people both online and IRL who care about you and maybe you don't even realize it.\n"
    msg += f"Please please please reach out to someone you trust if you're feeling down. If you need, you can also google \"suicide prevention\" to get the hotline number for your country: https://www.google.com/search?q=suicide+prevention\n"
    msg += f"Suicide is never the answer, okay? It may seem like they way out in a place of desperation, but you will get through this rough patch... {admin_user.mention} & I believe in you, friend!"

    await utils.safe_send(interaction, content=msg, ephemeral=True)

@bot.tree.command(description='Debug command')
async def vcopensessions(interaction: discord.Interaction):
    if not await utils.safe_defer(interaction, ephemeral=True): return
    
    log_info(interaction, f"{interaction.user} requested sql query for vcopensessions")

    try:
        data = sql.get_opensessions()
    except sqlite3.DatabaseError as e:
        log_debug(interaction, f"{interaction.user} query [vcopensessions] failed : {e}")
        await utils.safe_send(interaction, content=f"Failed to execute query [vcopensessions]:\n```\n{traceback.format_exc()}\n```", ephemeral=True, is_followup=True)
        return
    except Exception as e:
        log_debug(interaction, f"{interaction.user} query [vcopensessions] failed : {e}")
        await _dm_log_error(f"[{interaction.channel}] vcopensessions\n{e}\n{traceback.format_exc()}")
        await utils.safe_send(interaction, content="Failed to execute query", ephemeral=True, is_followup=True)
        return
        
    if data is None:
        msg = "Your query returned None"
    else:
        msg = f"Here are the results for your query:\n```\n"
        msg += "\n".join(" | ".join([str(idx + 1)] + [str(item) for item in line]) for idx, line in enumerate(data))
        msg += "\n```"
        if len(msg) > 2000:
            aux = "```\nTRUNC"
            msg = msg[:2000-len(aux)-1] + aux
    await utils.safe_send(interaction, content=msg, ephemeral=True, is_followup=True)

@bot.tree.command(description='Get the daily top 10 rankings')
@discord.app_commands.describe(date='When to fetch data ("yyyy-mm-dd")', phone='Format the output for copy/paste on a phone', vclimit='How many users to check for VC standings (default 3)')
async def dailytopten(interaction: discord.Interaction, date: typing.Optional[str], phone: typing.Optional[bool] = False, vclimit: typing.Optional[int] = 3):
    if not await utils.safe_defer(interaction, ephemeral=True): return
    
    _date = date or (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    _pdate = datetime.datetime.strptime(_date, "%Y-%m-%d")
    log_info(interaction, f"{interaction.user} requested daily top 10 for {_date}")

    try:
        data = sql.get_dailytopten(_date, game_channel_ids)
    except sqlite3.DatabaseError as e:
        log_debug(interaction, f"{interaction.user} query daily top ten failed : {e}")
        await utils.safe_send(interaction, content=f"Failed to execute query:\n```\n{traceback.format_exc()}\n```", ephemeral=True, is_followup=True)
        return
    except Exception as e:
        log_debug(interaction, f"{interaction.user} query for daily top ten failed : {e}")
        await _dm_log_error(f"[{interaction.channel}] _rawsql\n{e}\n{traceback.format_exc()}")
        await utils.safe_send(interaction, content="Failed to execute query", ephemeral=True, is_followup=True)
        return

    try:
        vcdata = sql.get_dailytopvc(_date, limit=vclimit)
    except sqlite3.DatabaseError as e:
        log_debug(interaction, f"{interaction.user} query daily top VC failed : {e}")
        await utils.safe_send(interaction, content=f"Failed to execute query:\n```\n{traceback.format_exc()}\n```", ephemeral=True, is_followup=True)
        return
    except Exception as e:
        log_debug(interaction, f"{interaction.user} query for daily top VC failed : {e}")
        await _dm_log_error(f"[{interaction.channel}] _rawsql\n{e}\n{traceback.format_exc()}")
        await utils.safe_send(interaction, content="Failed to execute query", ephemeral=True, is_followup=True)
        return
        
    if not data and not vcdata:
        msg = "Your query returned None"
    else:
        msg = ""
        if data:
            msg += f"Top 10 users for {utils.to_date(_pdate)}!\n"
            msg += "\n".join(" | ".join([utils.to_podium(idx + 1), ("" if phone else "\\") + utils.to_mention(line[0]), str(line[1])]) for idx, line in enumerate(data))
            msg += "\n"
        if vcdata:
            msg += f"Top {vclimit} VC users!\n"
            msg += "\n".join(" | ".join([utils.to_podium(idx + 1), ("" if phone else "\\") + utils.to_mention(line[0]), f"{utils.to_pretty_timedelta(line[1])}"]) for idx, line in enumerate(vcdata))
            msg += "\n"
        if len(msg) > 2000:
            aux = "\nTRUNC"
            msg = msg[:2000-len(aux)-1] + aux
    await utils.safe_send(interaction, content=msg, ephemeral=True, is_followup=True)

@bot.tree.command(description='Pop pop pop!')
async def bubblewrap(interaction: discord.Interaction):
    width, height = 10, 10
    msg = "\n".join(["||pop||" * width for _ in range(height)])
    await utils.safe_send(interaction, content=msg, ephemeral=True)

@bot.tree.command(description='We do a little bit of stalking')
@discord.app_commands.describe(user='User to search')
async def aliases(interaction: discord.Interaction, user: discord.Member):
    aliases = utils.get_unique_aliases(user)
    if len(aliases):
        msg = f"These are {user.mention}'s known aliases~\n> "
        msg += ", ".join([utils.markdown_surround(alias, "`") for alias in aliases])
    else:
        msg = f"I couldn't find {user.mention} in the database..."
    await utils.safe_send(interaction, content=msg, ephemeral=True)

@bot.tree.command(description='We do a little bit of stalking')
@discord.app_commands.describe(user_id='User ID to search')
async def aliasesalt(interaction: discord.Interaction, user_id: int):
    aliases = utils.get_unique_aliases_id(user_id)
    if len(aliases):
        msg = f"These are {utils.to_mention(str(user_id))}'s known aliases~\n> "
        msg += ", ".join([utils.markdown_surround(alias, "`") for alias in aliases])
    else:
        msg = f"I couldn't find {utils.to_mention(str(user_id))} in the database..."
    await utils.safe_send(interaction, content=msg, ephemeral=True)

@bot.tree.command(description='Contribute to the server\'s world (heat) map')
@discord.app_commands.describe(country='Where you\'re from')
async def locate(interaction: discord.Interaction, country: str):
    validated_country = utils.validate_country(country)

    if validated_country is None:
        await utils.safe_send(interaction, content=f"I don't know that country... Can you try again, please?", ephemeral=True)
        return

    updated = sql.insert_worldmap(interaction.user.id, validated_country)

    country_flag = utils.country_flag(country)

    if updated:
        msg = f":airplane::map: Okay, I moved you to {country_flag} {validated_country}/{country}~"
    else:
        msg = f":pushpin::map: Okay, I added you to {country_flag} {validated_country}/{country}~"

    await utils.safe_send(interaction, content=msg, ephemeral=True)

# TODO parameterize color scheme (graphlytics.cmaps)
@bot.tree.command(description='Get a heatmap with the users of the server (contribute with /locate)')
async def worldmap(interaction: discord.Interaction):
    if not await utils.safe_defer(interaction): return

    log_info(interaction, f"{interaction.user} requested worldmap")

    report_name = graphlytics.generate_world_heatmap()
    log_debug(interaction, f"report_name={report_name}")
    report_file = discord.File(report_name, filename=f"user_report.png")

    amount = sql.count_worldmap()

    await utils.safe_send(interaction, content=f"Here you go!\nAnd if you haven't already, you can add yourself to the map with `/locate` :heart:\nWe have `{amount}` registered friends~", file=report_file, is_followup=True, send_anyway=True)

    os.remove(report_name)

# TODO parameterize color scheme (graphlytics.cmaps)
@bot.tree.command(description='How many users contributed to the server heatmap (contribute with /locate)')
async def worldmapcount(interaction: discord.Interaction):
    if not await utils.safe_defer(interaction): return

    log_info(interaction, f"{interaction.user} requested worldmapcount")
    
    data = sql.count_worldmap()

    await utils.safe_send(interaction, content=f"There are {utils.n_em(data)} registered users!\nAnd if you haven't already, you can add yourself to the map with `/locate` :heart:", is_followup=True, send_anyway=True)

# @bot.tree.command(description='Join NNN 2022! Please be aware you can only join/wager ONCE!')
# @discord.app_commands.describe(wager='Are you willing to wager one of your roles?')
# async def joinnnn(interaction: discord.Interaction, wager: typing.Optional[bool]):
#     log_info(interaction, f"{interaction.user} is joining NNN 2022")

#     joined = sql.nnn_join(interaction.user.id, wager or False)

#     if joined:
#         content = f"Thank you for signing up for NNN 2022, {interaction.user.mention}! GLHF~"
#     else:
#         log_info(interaction, f"{interaction.user} already joined NNN 2022")
#         content = f"You've already signed up for NNN 2022, {interaction.user.mention}~"

#     await utils.safe_send(interaction, content=content, send_anyway=True)

# @bot.tree.command(description='Admit defeat in NNN 2022! Please be aware you cannot take this back!!!')
# async def failnnn(interaction: discord.Interaction):
#     log_info(interaction, f"{interaction.user} is joining NNN 2022")

#     if datetime.datetime.now().month != 11:
#         await utils.safe_send(interaction, content=f"You can't fail NNN if it's not november yet, silly~", ephemeral=True)
#         return

#     data = sql.nnn_status(interaction.user.id)
#     log_debug(interaction, f"Got status = {data}")
#     if data is None:
#         await utils.safe_send(interaction, content=f"You didn't sign up yet, {interaction.user.mention}! You can do that with `/joinnnn`~", send_anyway=True)
#         return

#     failed = sql.nnn_fail(interaction.user.id)

#     if failed:
#         content = f"Aww there's always next year, {interaction.user.mention}! Thanks for participating and GG no RE~"
#     else:
#         log_info(interaction, f"{interaction.user} already failed NNN 2022")
#         content = f"You've already failed NNN 2022, {interaction.user.mention}, try again next year~"

#     await utils.safe_send(interaction, content=content, send_anyway=True)

@bot.tree.command(description='Check the numbers on NNN 20222')
async def countnnn(interaction: discord.Interaction):
    log_info(interaction, f"{interaction.user} is checking NNN 2022")

    joined, failed = sql.nnn_count()

    content = f"`{joined}` users have joined, and `{failed}` have failed NNN 2022~"

    await utils.safe_send(interaction, content=content, send_anyway=True)

@bot.tree.command(description='Nut counter!')
async def nut(interaction: discord.Interaction):
    log_info(interaction, f"{interaction.user} is adding a nut")

    total = sql.add_nut(interaction.user.id)

    # content = f"{utils.n_em(total)} :chestnut: :peanuts: :coconut:"
    random.seed(interaction.user.id)
    nut_emojis = [":chestnut:", ":peanuts:", ":coconut:"]
    nuts = [random.choice(nut_emojis) for _ in range(total)]
    content = " ".join(nuts)

    if len(content) < 2000:
        await utils.safe_send(interaction, content=content, send_anyway=True)
    else:
        nut_counts = [(n, nuts.count(n)) for n in nut_emojis]
        content = "\n".join([f"{nut} x {utils.n_em(amount)}" for (nut, amount) in nut_counts])
        await utils.safe_send(interaction, content=content, send_anyway=True)

# Jail a user directly
@bot.tree.context_menu(name="Horny Jail")
async def hornyjail(interaction: discord.Interaction, user: discord.Member):
    duration = 5
    log_info(interaction, f"{interaction.user} is jailing {user} for {duration} minutes")

    await utils.core_hornyjail(interaction, user, duration, jail_role_id)

# Jail a user from their message
@bot.tree.context_menu(name="Horny Jail author")
async def hornyjail(interaction: discord.Interaction, message: discord.Message):
    duration = 5
    log_info(interaction, f"{interaction.user} is jailing {message.author} for {duration} minutes")

    await utils.core_hornyjail(interaction, message.author, duration, jail_role_id, message=message)

@bot.tree.command(description='Send someone to horny jail')
@discord.app_commands.describe(user='User to jail', message_id='Message to send to the appropriate channel', delete_original='Also delete the original message after posting it to the correct channel') #, duration='How long to jail them for, in minutes (default is 5)')
async def hornyjail(interaction: discord.Interaction, user: discord.Member, message_id: typing.Optional[int]=None, delete_original: typing.Optional[bool]=False): #, duration: typing.Optional[int]=5):
    duration = 5
    log_info(interaction, f"{interaction.user} is jailing {user} for {duration} minutes")
    try:
        message = await interaction.channel.fetch_message(message_id) if message_id else None
    except:
        message = None

    await utils.core_hornyjail(interaction, user, duration, jail_role_id, message=message, delete_original=delete_original)

@bot.tree.command(description='Send someone to horny prison')
@discord.app_commands.describe(user='User to jail')
async def hornyprison(interaction: discord.Interaction, user: discord.Member):
    duration = 3 * 60
    log_info(interaction, f"{interaction.user} is imprisoning {user} for {duration} minutes")
    if not await utils.ensure_queen(interaction): return

    await utils.core_hornyjail(interaction, user, duration, jail_role_id)

@bot.tree.command(description='Remove someone from horny jail')
@discord.app_commands.describe(user='User to unjail') #, duration='How long to jail them for, in minutes (default is 5)')
async def hornyunjail(interaction: discord.Interaction, user: discord.Member): #, duration: typing.Optional[int]=5):
    log_info(interaction, f"{interaction.user} is unjailing {user}")
    if not await utils.ensure_queen(interaction): return

    success = sql.jail_register_unjailing(user.id, interaction.user.id)

    if not success:
        await utils.safe_send(interaction, content=f"I don't think that user is in jail~", ephemeral=True)
        return
    
    jail_role = interaction.guild.get_role(jail_role_id)
    await user.remove_roles(jail_role, reason=f'{interaction.user} removed them from jail')
    await utils.safe_send(interaction, content=f"Fine {user.mention}, I guess you can come out now, but you better be on your best behavior~", send_anyway=True)

@bot.tree.command(description='When people can\'t be bothered to google stuff for themselves')
@discord.app_commands.describe(user='Who to ping', query='What they asked for')
async def lmgtfy(interaction: discord.Interaction, user: discord.Member, query: str):
    log_info(interaction, f"{interaction.user} is pinging {user} for query {query}")

    safe_query = "https://letmegooglethat.com/?q=" + urllib.parse.quote_plus(query)
    content = f"Here you go {user.mention}~\n{safe_query}"

    # logger.debug(f"Content = '{content}'")
    await utils.safe_send(interaction, content=content, send_anyway=True)

@bot.tree.command(description='Check when a user left and joined the guild')
@discord.app_commands.describe(user='Who to check')
async def joinhistory(interaction: discord.Interaction, user: discord.Member):
    log_info(interaction, f"{interaction.user} is fetching {user} history")

    await utils.core_joinhistory(interaction, user.id, sql, str(user))

@bot.tree.command(description='Check when a user left and joined the guild (search by ID)')
@discord.app_commands.describe(user='Who to check')
async def joinhistoryalt(interaction: discord.Interaction, user: str):
    log_info(interaction, f"{interaction.user} is fetching {user} history alt")

    try:
        userid = int(user)
    except:
        await utils.safe_send(interaction, content=f"Are you sure that's a valid ID?", ephemeral=True)
        return
    
    await utils.core_joinhistory(interaction, userid, sql, utils.to_mention(userid))

@bot.tree.command(description='Ask me not to ship you with others')
async def noship(interaction: discord.Interaction):
    log_info(interaction, f"{interaction.user} is requesting noship")

    sql.add_noship(interaction.user.id)
    
    await utils.safe_send(interaction, content=f"Okay, I won't ship you with other people! If you change your mind, you can undo it with `/yesship`", ephemeral=True)

@bot.tree.command(description='Allow me to ship you with others')
async def yesship(interaction: discord.Interaction):
    log_info(interaction, f"{interaction.user} is requesting yesship")

    sql.rm_noship(interaction.user.id)
    
    await utils.safe_send(interaction, content=f"Okay, I will ship you with other people! If you change your mind, you can undo it with `/noship`", ephemeral=True)

@bot.tree.command(description='Find a user\'s ID from their username')
@discord.app_commands.describe(user='Username to search')
async def searchid(interaction: discord.Interaction, user: str):
    log_info(interaction, f"{interaction.user} is searching for {user}'s ID")
    if "#" in user:
        user = user[:user.index("#")]

    data = sql.find_id_from_alias(user)
    if not data or len(data) == 0:
        content = f"I couldn't find anyone with that username, please try again with a different name"
    elif len(data) == 1:
        content = f"I found 1 user with that name: {data[0][0]} (<@{data[0][0]}>)"
    else:
        content = f"I found a few users with that name:\n"
        content += "\n".join([f"{line[0]} <@{line[0]}>: {line[1]}" for line in data])
    
    await utils.safe_send(interaction, content=content, ephemeral=True)

# @bot.tree.command(description='Get a discord timestamp that changes automatically')
# @discord.app_commands.describe(
#     timezone='Your timezone (like EST, GMT, UTC, BST..., defaults to UTC)', 
#     style='How you want your timestamp formatted',
#     hour='24-hour of timestamp (0-23, defaults to right now)',
#     minute='minute of timestamp (0-59, defaults to right now)',
#     second='second of timestamp (0-59, defaults to right now)',
#     year='year of timestamp (defaults to right now)',
#     month='month of timestamp (1-12, defaults to right now)',
#     day='day of timestamp (1-31, defaults to right now)')
# @discord.app_commands.choices(
#     style=[discord.app_commands.Choice(name=n, value=v) for n, v in [
#         ("Default (November 28, 2018 9:01 AM)", ""),
#         ("Short Time (9:01 AM)", ":t"),
#         ("Long Time (9:01:00 AM)", ":T"),
#         ("Short Date (11/28/2018)", ":d"),
#         ("Long Date (November 28, 2018)", ":D"),
#         ("Short Date/Time (November 28, 2018 9:01 AM)", ":f"),
#         ("Long Date/Time (Wednesday, November 28, 2018 9:01 AM)", ":F"),
#         ("Relative Time (3 years ago)", ":R")]])
# async def timestamp(
#     interaction: discord.Interaction, 
#     timezone: typing.Optional[str]="UTC", 
#     hour: typing.Optional[int]=None, 
#     minute: typing.Optional[int]=None, 
#     second: typing.Optional[int]=None, 
#     year: typing.Optional[int]=None, 
#     month: typing.Optional[int]=None, 
#     day: typing.Optional[int]=None, 
#     style: typing.Optional[discord.app_commands.Choice[str]]=""):
#     try:
#         t = datetime.datetime.now(tz=tz.gettz(timezone))
#     except:
#         await utils.safe_send(interaction, content=f"That doesn't look like a valid timezone~", ephemeral=True)
#         return

#     update = dict()
#     if hour:
#         update['hour'] = hour
#     if minute:
#         update['minute'] = minute
#     if second:
#         update['second'] = second
#     if year:
#         update['year'] = year
#     if month:
#         update['month'] = month
#     if day:
#         update['day'] = day
#     try:
#         t = t.replace(**update)
#     except:
#         await utils.safe_send(interaction, content=f"That doesn't look like a valid time, pls check your values~", ephemeral=True)
#         return

#     if type(style) != str:
#         style = style.value

#     ts = f"<t:{int(time.mktime(t.timetuple()))}{style}>"

#     await utils.safe_send(interaction, content=f"Here's your timestamp~\n```{ts}```And here's how it's going to look like: {ts}", ephemeral=True)

@bot.tree.command(description='Advertise your commissions')
async def advertise(interaction: discord.Interaction, attachment: typing.Optional[discord.Attachment] = None):
    log_info(interaction, f"{interaction.user} is requesting to create an AD: {attachment}")
    
    await ad_handler.create_advertisement(interaction, attachment=attachment)

@bot.tree.command(description='[MOD] Allow a user to post in cork-board')
async def allowad(interaction: discord.Interaction, user: discord.Member):
    log_info(interaction, f"{interaction.user} is requesting to allow an AD for {user}")
    
    if user.bot:
        await utils.safe_send(interaction, content=f"That user is a bot...", ephemeral=True)
        return
    
    if ad_poster_role_id in [role.id for role in user.roles]:
        await utils.safe_send(interaction, content=f"Seems like they already have the role, but I'll keep watching to remove it after they post it!", ephemeral=True)
        mhm.create_dyn_lock(utils.handle_cork_board_post, user.id)
        return

    ad_role = interaction.guild.get_role(ad_poster_role_id)

    try:
        await user.add_roles(ad_role, reason=f"{interaction.user} said so")
        await utils.safe_send(interaction, content=f"Good news, {user.mention}! You can make your post in <#{ad_channel}> now~\nJust make sure you follow the rules at the top, mkay?")
    except:
        await utils.safe_send(interaction, content=f"I couldn't give 'em the role, but I'll keep watching to remove it after they post it!", ephemeral=True)

    mhm.create_dyn_lock(utils.handle_cork_board_post, user.id)

@bot.tree.command(description='Remove an unwanted advertisement (e.g. spam)')
@discord.app_commands.describe(message='Message to remove (must be an ad)')
async def removeadvertisement(interaction: discord.Interaction, message: str):
    log_info(interaction, f"{interaction.user} is deleting ad {message} history alt")

    try:
        messageid = int(message)
    except:
        await utils.safe_send(interaction, content=f"Are you sure that's a valid ID?", ephemeral=True)
        return

    ad_info = sql.is_advertisement(messageid)
    if not ad_info:
        await utils.safe_send(interaction, content=f"That doesn't seem to be an ad...", ephemeral=True)
        return

    user = int(ad_info[0])
    success = await ad_handler.try_remove_advertisement(user)

    if success:
        await utils.safe_send(interaction, content=f"Ad zapped out of existence!", ephemeral=True)
    else:
        await utils.safe_send(interaction, content=f"Something went wrong... are you sure the message is still there?", ephemeral=True)

@bot.tree.command(description='Mute yourself, put your phone down and go get some eep!')
@discord.app_commands.describe(duration='Whether you want to eep (longer) or nap (shorter). The default is eep!')
@discord.app_commands.choices(duration=[discord.app_commands.Choice(name="eep", value=4), discord.app_commands.Choice(name="nap", value=1)])
async def sleepme(interaction: discord.Interaction, duration: discord.app_commands.Choice[int]=4):
    if isinstance(duration, int):
        duration = discord.app_commands.Choice(name="eep", value=4)

    log_info(interaction, f"{interaction.user} is sleeping themselves ({duration.name}/{duration.value}h)")

    content = {"eep": "Gn {}! Cya tomorrow~", "nap": "Have a nice nappies {}! Cya later~"}[duration.name]
    try:
        await interaction.user.timeout(datetime.timedelta(hours=duration.value), reason=f"sleepy sleepy gn ({duration.value}h)")

        await utils.safe_send(interaction, content=content.format(interaction.user.mention), allowed_mentions=discord.AllowedMentions.none(), send_anyway=True)
    except:
        log_warn(interaction, f"Failed to timeout {interaction.user}")
        await utils.safe_send(interaction, content=f"Hmm it looks like I can't help you, {interaction.user.mention}... :c", allowed_mentions=discord.AllowedMentions.none(), send_anyway=True)

@bot.tree.command(description='Zap!')
@discord.app_commands.describe(user='User to zap')
async def zap(interaction: discord.Interaction, user: discord.Member):
    if user.id == bot.user.id:
        await utils.safe_send(interaction, content="Why would you wanna zap me :c", ephemeral=True)
        return
    if user.bot:
        await utils.safe_send(interaction, content="Can't zap bots! No good!!!", ephemeral=True)
        return
    if user.id == interaction.user.id:
        await utils.safe_send(interaction, content="I won't indulge in your kinks~", ephemeral=True)
        return
    try:
        await utils._split_dm(f"_**zap!**_", user)
        await utils.safe_send(interaction, content="Zapped 'em good!", ephemeral=True)
    except Exception as e:
        logger.info(f"Error while trying to send DM to {user}: {e}\n{traceback.format_exc()}")
        await utils.safe_send(interaction, content="I think they've blocked me :c", ephemeral=True)

@bot.tree.command(description='Hold up a mistletoe~')
@discord.app_commands.describe(users='How many people to gather under the mistletoe (default is 2)')
async def mistletoe(interaction: discord.Interaction, users: typing.Optional[int]=2):
    log_info(interaction, f"{interaction.user} is requesting a mistletoe for {users}")

    if users < 2:
        await utils.safe_send(interaction, content="That's not enough people to kiss under the mistletoe, silly~", ephemeral=True)
        return

    if users > 10:
        await utils.safe_send(interaction, content="That's WAY too many people to kiss under the mistletoe, silly~", ephemeral=True)
        return
    
    created = mistletoe_handler.try_new_mistletoe(interaction.channel_id, users)
    if not created:
        await utils.safe_send(interaction, content="I'm still waiting on a mistletoe, silly~", ephemeral=True)
        return

    await _meme(interaction, "mistletoe", text=str(users), msg=f"Next {users} to talk have to kiss under the mistletoe~!")

@bot.tree.command(description='Purge a user\'s messages from the current channel')
@discord.app_commands.describe(user='Who to purge', userid='Who to purge (user id in case someone already left)', complete='Whether to purge all messages or only those with images (default)')
async def purgemessages(interaction: discord.Interaction, user: typing.Optional[discord.Member], userid: typing.Optional[str], complete: typing.Optional[bool]=False):
    log_info(interaction, f"{interaction.user} is requesting a purge of {interaction.channel} for {user}")

    if (not user and not userid) or (user and userid):
        await utils.safe_send(interaction, content="Please choose either user or userid", ephemeral=True)
        return
    
    try:
        userid = userid and int(userid) or user.id
    except:
        await utils.safe_send(interaction, content="That's not a valid user id...", ephemeral=True)
        return

    await utils.safe_send(interaction, content=f"Purge in progress for user <@{userid}>...", ephemeral=True)

    await utils.purge_user_from_channel(interaction.channel, userid, f"`/purgemessages complete:{complete}`", mod=interaction.user, complete=complete)

    # msg = await interaction.original_response()
    # await msg.edit(content=f"Purge of user <@{userid}> completed, boss!")
    await interaction.edit_original_response(content=f"Purge of user <@{userid}> completed, boss!")

@bot.tree.command(description='Ban a user')
@discord.app_commands.describe(user='Who to ban', reason='Reason for the ban')
async def ban(interaction: discord.Interaction, user: discord.Member, reason: typing.Optional[str]=None):
    await mod.core_ban(user, interaction, reason_notif=reason)

@bot.tree.command(description='Kick a user')
@discord.app_commands.describe(user='Who to kick', reason='Reason for the kick')
async def kick(interaction: discord.Interaction, user: discord.Member, reason: typing.Optional[str]=None):
    await mod.core_kick(user, interaction, reason_notif=reason)

@bot.tree.command(description='Mute a user')
@discord.app_commands.describe(user='Who to mute', duration='How long to mute (e.g. 5m, 2h)', reason='Reason for the mute')
async def mute(interaction: discord.Interaction, user: discord.Member, duration: str, reason: typing.Optional[str]=None):
    until = bot_utils.extract_timedelta(duration)
    if not until:
        await utils.safe_send(interaction, content="You must provide a valid time value, dummy! like 5m or 2h or whatever", ephemeral=True)
        return
    await mod.core_mute(user, until, interaction, reason_notif=reason)

bot.tree.add_command(kinks.get_kink_cmds(sql, utils))
bot.tree.add_command(kinks.Kinklist(sql, utils))
bot.tree.add_command(games.Game(utils, bot))
bot.tree.add_command(graphlytics.Analytics(utils))
bot.tree.add_command(shipper.Relationship(sql, utils))
bot.tree.add_command(modnotes.Modnotes(sql, utils))
bot.tree.add_command(ghostpings.Ghostpings(sql, utils))

@bot.tree.command(description='Find explanations for specific kinks')
async def kinktionary(interaction: discord.Interaction):
    log_info(interaction, f"{interaction.user} requested kinktionary")

    await utils.safe_send(interaction, view=kinks.Kinktionary(interaction), ephemeral=True)

def rec_walk(parent, super_cmd=""):
    for cmd in parent.walk_commands():
        if isinstance(cmd, discord.app_commands.Command):
            print(f"/{super_cmd}{cmd.name}: {cmd.description}")
            for p in cmd.parameters:
                print(f"    {p.name}: {p.description}")
            print("")
        else:
            rec_walk(cmd, super_cmd=f"{cmd.name} ")

# rec_walk(bot.tree)
# exit()

bot.run(TOKEN)
