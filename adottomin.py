import asyncio
import datetime
import sqlite3
import discord
import logging
import os
import random
import re
import traceback
import types
import typing

from regex import R

import age_handling
import botlogger
import bot_utils
import copypasta_utils
import db
import graphlytics
import kinks
import memes

from word_blocklist import blocklist

from flask import Flask
from dotenv import load_dotenv
from os.path import exists

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

REDO_ALL_PINS = False
REDO_ALL_ALIASES = False

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

GUILD_ID = os.getenv('GUILD_ID')
if GUILD_ID is None:
    print("GUILD_ID env var not set! Exiting")
    exit(1)
GUILD_OBJ = discord.Object(id=GUILD_ID)

_ids = os.getenv('CHANNEL_IDS') or ""
_channel_ids = [int(id) for id in _ids.split('.') if id != ""]
channel_ids = _channel_ids if len(_channel_ids) else None
_ids = os.getenv('AGE_ROLE_IDS') or ""
_role_ids = [int(id) for id in _ids.split('.') if id != ""]
role_ids = _role_ids if len(_role_ids) else []
tally_channel = int(os.getenv('TALLY_CHANNEL_ID'))
chats_home = os.getenv('CHATS_HOME')
chatbot_service = os.getenv('CHATBOT_SERVICE')

usernames_blocked = [
    "pendelton",
    "pennington"
]

blocklist_prog = re.compile("|".join(blocklist), flags=re.IGNORECASE)

queen_role_id = 1002077481156743259
owner_role_id = 1014556813821214780
divine_role_id = 1021892234829906043
secretary_role_id = 1002385294152179743
friends_role_ids = [
    1002382914526400703, # Tier 1
    1002676012573794394, # Tier 2
    1002676963485417592 # Tier 3
]
nsfw_role_id = 1010670864758493215

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

pin_archive_channel_id = 1029200990798368868
pin_archive_blocklist_ids = [
    1006965262244925650,
    1005356623650377740,
    1005363538560307211,
    1004948805956948128,
    1003626066113466389,
    1009950736567771177
]

admin_id = int(os.getenv('ADMIN_ID'))

pendelton_mode = False

class BottoBot(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)

    async def setup_hook(self):
        self.tree.copy_global_to(guild=GUILD_OBJ)
        await self.tree.sync(guild=GUILD_OBJ)

bot = BottoBot(intents=discord.Intents.all())
logger = botlogger.get_logger("adottomin")

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

sql = db.database(LENIENCY_COUNT)
age_handler = age_handling.age_handler(bot, sql, channel_ids[0], tally_channel, _role_ids, LENIENCY_COUNT - LENIENCY_REMINDER)
utils = bot_utils.utils(bot, sql, [divine_role_id, secretary_role_id], chatbot_service)

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
    utils.inject_admin(bot.get_user(admin_id))
    guild = await bot.fetch_guild(GUILD_ID)
    utils.inject_guild(guild)

    if REDO_ALL_PINS:
        for channel in bot.get_all_channels():
            await on_guild_channel_pins_update(channel, None)
        
    if REDO_ALL_ALIASES:
        async for member in guild.fetch_members():
            await _handle_new_alias(None, member)

    logger.info(f"Finished on_ready setup")

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    # logger.info(f"{after} has updated profile")

    try:
        await _handle_nsfw_added(before, after)
    except Exception as e:
        logger.error(f"Error during on_member_update::_handle_nsfw_added: {e}\n{traceback.format_exc()}")
        await _dm_log_error(f"on_member_update::_handle_nsfw_added\n{e}\n{traceback.format_exc()}")

    try:
        await _handle_new_alias(before, after)
    except Exception as e:
        logger.error(f"Error during on_member_update::_handle_new_alias: {e}\n{traceback.format_exc()}")
        await _dm_log_error(f"on_member_update::_handle_new_alias\n{e}\n{traceback.format_exc()}")

    # logger.debug(f"Finished on_member_update")

async def _handle_nsfw_added(before: discord.Member, after: discord.Member):
    if (nsfw_role_id in utils.role_ids(before)) or (nsfw_role_id not in utils.role_ids(after)): return
    if not utils.just_joined(before.id): 
        logger.info(f"{after} added nsfw role and is a previous user")
        return
    user_age_roles = set([role.id for role in after.roles]).intersection(set(role_ids))
    if user_age_roles != set(): 
        logger.info(f"{after} added nsfw role and has age tags: {user_age_roles}")
        return
    # nsfw_role = [role for role in after.roles if role.id == nsfw_role_id]
    nsfw_role = discord.utils.get(after.guild.roles, name="NSFW")
    logger.info(f"{after} added nsfw role but is still being verified")
    await after.remove_roles(*[nsfw_role], reason="Not verified", atomic=False)
    notif = after.guild.get_channel(channel_ids[0])
    await notif.send(content=f"Straight for the NSFW and didn't even tell me your age, {after.mention}?~")

async def _handle_new_alias(before: typing.Optional[discord.Member], after: discord.Member):
    if before is not None and after.display_name == before.display_name:
        logger.debug(f"{after} did not change alias")
        return
    old_aliases = utils.get_unique_aliases(after)
    if after.display_name in old_aliases: 
        logger.info(f"{after} added known alias {after.display_name}")
        return
    logger.info(f"{after} adding new alias {after.display_name}")
    sql.create_alias(after.id, after.display_name)

reaction_blocklist = []
reaction_user_blocklist = []

@bot.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.Member):
    logger.info(f"Added reaction {reaction}")
    emoji = reaction.emoji if type(reaction.emoji) == str else reaction.emoji.name
    # logger.debug(f"Added emoji = {emoji}")
    if emoji in reaction_blocklist or user.id in reaction_user_blocklist:
        logger.info(f"Reaction blocklisted, removing")
        reaction.remove(user)

bot_message_handlers = [
    utils.handle_offline_mentions
]
user_message_handlers = [
    age_handler.handle_age,
    utils.handle_invite_link,
    utils.handle_dm,
    utils.handle_dm_cmd,
    utils.handle_chat_dm,
    utils.handle_failed_command,
    utils.handle_attachments,
    utils.handle_binary
]

async def execute_handlers(msg, handlers):
    for handle in handlers:
        try:
            # logger.debug(f"Running handler {handle.__name__}")
            await handle(msg)
        except bot_utils.HandlerException:
            pass
        except Exception as e:
            logger.error(f"[{msg.channel}] Error during {handle.__qualname__}: {e}\n{traceback.format_exc()}")
            await _dm_log_error(f"[{msg.channel}] on_message::{handle.__qualname__}\n{e}\n{traceback.format_exc()}")

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

    await execute_handlers(msg, bot_message_handlers)

    if msg.author.id == bot.user.id: return

    await execute_handlers(msg, user_message_handlers)
        
    if not msg.author.bot:
        try:
            sql.register_message(msg.author.id, msg.id, msg.channel.id)
        except Exception as e:
            logger.error(f"[{msg.channel}] Error during register_message: {e}\n{traceback.format_exc()}")
            await _dm_log_error(f"[{msg.channel}] on_message::register_message\n{e}\n{traceback.format_exc()}")
    else:
        logger.debug(f"[{msg.channel}] User ID: {msg.author.id} is a bot, not registering")

@bot.event
async def on_member_join(member: discord.Member):
    channel = bot.get_channel(channel_ids[0])
    logger.info(f"[{channel}] {member} just joined")
    try:
        if member.bot:
            logger.info(f"[{channel}] {member} is a bot, ignoring")
            return

        if member.id == bot.user.id: return
        
        if RAID_MODE or is_raid_mode():
            logger.info(f"[{channel}] Raid mode ON: {member}")
            await age_handler.kick_or_ban(member, channel, reason=age_handling.REASON_RAID)
            return

        autoblock = sql.is_autoblocked(member.id)
        if autoblock is not None:
            mod, reason, date = autoblock
            logger.info(f"[{channel}] {member} is PRE-blocked: {date}/{mod}: {reason}")
            await age_handler.kick_or_ban(member, channel, reason=reason, force_ban=True)
            return

        for name in usernames_blocked:
            if name in member.name.lower():
                logger.info(f"[{channel}] {member} is name-blocked: annoying")
                await age_handler.kick_or_ban(member, channel, reason="annoying", force_ban=True)
                return

        greeting = await channel.send(age_handling.MSG_GREETING.format(member.mention))
        sql.create_entry(member.id, greeting.id)

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

    except Exception as e:
        logger.error(f"[{channel}] Error during on_member_join: {e}\n{traceback.format_exc()}")
        await _dm_log_error(f"[{channel}] on_member_join\n{e}\n{traceback.format_exc()}")
        logger.debug(f"[{channel}] Error exit on_member_join")

@bot.event
async def on_guild_channel_pins_update(channel: typing.Union[discord.abc.GuildChannel, discord.Thread], last_pin: typing.Optional[datetime.datetime]):
    logger.debug(f"Received pin update in {channel}")
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
                    logger.debug(f"Message {pin.id} is already pinned, skipping...")
                    return

                pinEmbed = discord.Embed(
                    description=pin.content if len(pin.content) > 0 else None,
                    colour=random.choice(bot_utils.EMBED_COLORS)
                )

                attachments = pin.attachments
                if len(attachments) >= 1:
                    pinEmbed.set_image(url=attachments[0].url)

                pinEmbed.add_field(name="Jump", value=pin.jump_url, inline=False)
                
                pinEmbed.set_footer(text=f'Sent in: {pin.channel.name} - at: {pin.created_at}')
                
                try:
                    creator = await channel.guild.fetch_member(pin.author.id)
                    icon_url = creator.avatar.url
                except Exception as e:
                    logger.warning(f"Exception while trying to handle pin {pin.id} thumbnail: {e}\n{traceback.format_exc()}")
                    icon_url = None

                pinEmbed.set_author(name=f'Sent by {pin.author}', icon_url=icon_url)
                archived = await pin_channel.send(embed=pinEmbed)

                sql.register_pin(pin.id, archived.id)
            except Exception as e:
                logger.error(f"Exception while trying to handle pin {pin.id}: {e}\n{traceback.format_exc()}")
            # updated = True

        # if updated:
        #     await pin.channel.send(f"Your pinned message is in {pin_channel.mention}~")

    except Exception as e:
        logger.error(f"Exception while trying to handle pin updates: {e}\n{traceback.format_exc()}")

@bot.tree.command(description='Turn raid mode on or off (auto kick or ban)')
@discord.app_commands.describe(enable='Whether to turn raid mode on or off')
@discord.app_commands.choices(enable=[discord.app_commands.Choice(name="on", value="on"), discord.app_commands.Choice(name="off", value="off")])
async def raidmode(interaction: discord.Interaction, enable: discord.app_commands.Choice[str]):
    if not await utils.ensure_divine(interaction): return

    if enable.value == "on":
        if set_raid_mode():
            log_info(interaction, f"{interaction.user} enabled raidmode")
            await utils.safe_send(interaction, content=MSG_RAID_MODE_ON.format(interaction.user.mention), send_anyway=True)
        else:
            log_debug(interaction, f"{interaction.user} enabled raidmode (already enabled)")
            await utils.safe_send(interaction, content=MSG_RAID_MODE_ON_ALREADY, ephemeral=True)
    else:
        if unset_raid_mode():
            log_info(interaction, f"{interaction.user} disabled raidmode")
            await utils.safe_send(interaction, content=MSG_RAID_MODE_OFF.format(interaction.user.mention), send_anyway=True)
        else:
            log_debug(interaction, f"{interaction.user} disabled raidmode (already disabled)")
            await utils.safe_send(interaction, content=MSG_RAID_MODE_OFF_ALREADY, ephemeral=True)

async def _meme(interaction: discord.Interaction, meme_code: str, user: typing.Optional[discord.Member]=None, text: str=None, msg=""):
    await interaction.response.defer()

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
    'peace': ('peace', 'Good for you')
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

@bot.tree.command(description='Get a random fortune!')
async def fortune(interaction: discord.Interaction):
    fortune = memes.generate_fortune()
    random.seed(hash(memes.prepared_content(str(interaction.user.id))))
    numbers = [f'`{random.choice(range(100)):02}`' for _ in range(6)]
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

@bot.tree.command(description='Explain it like you\'re a boomer')
@discord.app_commands.describe(expression='What to search')
async def boomersplain(interaction: discord.Interaction, expression: str):
    log_info(interaction, f"{interaction.user} requested definition for {expression}")

    word_txt, meaning_txt, example_txt = memes.get_formatted_definition(expression)
    
    embed = discord.Embed(
        title=f"**{word_txt}**",
        colour=random.choice(bot_utils.EMBED_COLORS)
    )

    if meaning_txt is not None and len(meaning_txt) > 0:
        embed.add_field(name="Definition", value=meaning_txt, inline=False)

    if example_txt is not None and len(example_txt) > 0:
        embed.add_field(name="Usage", value=f"_{example_txt}_", inline=False)
    
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

    await interaction.response.defer()

    content = "No horny in main{}!".format(f", {user.mention}" if user is not None else "")

    meme_name = memes.no_horny
    meme_file = discord.File(meme_name, filename=meme_name)
    embed = discord.Embed()
    embed.set_image(url=f"attachment://{meme_name}")

    await utils.safe_send(interaction, content=content, file=meme_file, is_followup=True)

@bot.tree.command(description='Get analytics data for new users')
@discord.app_commands.describe(range='Max days to fetch')
async def report(interaction: discord.Interaction, range: typing.Optional[int] = 7):
    await interaction.response.defer()

    log_info(interaction, f"{interaction.user} requested report")
    if not await utils.ensure_divine(interaction): return

    report_name = graphlytics.generate_new_user_graph(range)
    log_debug(interaction, f"report_name={report_name}")
    report_file = discord.File(report_name, filename=f"user_report.png")

    await utils.safe_send(interaction, content=f"Here you go~", file=report_file, is_followup=True)

    os.remove(report_name)

@bot.tree.command(description='Warn a user for bad behavior, auto bans if there are too many strikes')
@discord.app_commands.describe(user='User to warn', reason='Why are they being warned')
async def strike(interaction: discord.Interaction, user: discord.Member, reason: str):
    log_info(interaction, f"{interaction.user} requested strike for {user}: '{reason}'")
    if not await utils.ensure_secretary(interaction): return

    if set(utils.role_ids(user)).intersection(set([divine_role_id, secretary_role_id])) != set():
        log_debug(interaction, f"{user} cannot be warned")
        await utils.safe_send(interaction, content=MSG_CANT_DO_IT, ephemeral=True)
        return

    active_strikes = sql.create_warning(user.id, interaction.user.id, reason, WARNING_VALIDITY_DAYS)

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
        channel = bot.get_channel(channel_ids[0])
        await age_handler.do_ban(channel, user, reason=age_handling.REASON_WARNINGS, tally=False)

@bot.tree.command(description='Check the user\'s previous strikes')
@discord.app_commands.describe(user='User to check', all='Get all strikes (only gets active strikes by default)')
async def getstrikes(interaction: discord.Interaction, user: discord.Member, all: typing.Optional[bool]=False):
    log_info(interaction, f"{interaction.user} requested strikes for {user}")
    if not await utils.ensure_secretary(interaction): return

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
        log_debug(interaction, f"{user} will NOT be promoted to tier 3")
        await utils.safe_send(interaction, content="Khris said no promotions to t3~", ephemeral=True)
        return
        # msg = MSG_CONGRATULATIONS_PROMOTION.format(3, user.mention)
        # new_role_id = friends_role_ids[2]
        
    else:
        log_debug(interaction, f"{user} will be promoted to tier 2")
        msg = MSG_CONGRATULATIONS_PROMOTION.format(2, user.mention)
        new_role_id = friends_role_ids[1]
        
    try:
        member = interaction.guild.get_member(user.id)
        new_role = interaction.guild.get_role(new_role_id)
        await member.add_roles(new_role, reason=f"{interaction.user} said so")
        await utils.safe_send(interaction, content=msg, send_anyway=True)
    except discord.HTTPException as e:
        log_error(interaction, f"Failed to give role {new_role} to {user}")
        log_debug(interaction, e)
        await utils.safe_send(interaction, content="I still can't give promotions and it's probably Khris' fault~", ephemeral=True)

@bot.tree.command(description='Check a user\'s reported age')
@discord.app_commands.describe(user='User to check')
async def age(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.defer(ephemeral=True)

    log_info(interaction, f"{interaction.user} requested age for {user}")
    if not await utils.ensure_secretary(interaction): return
        
    age_data = sql.get_age(user.id)
    mention = user.mention

    msg = _get_message_for_age(interaction, age_data, mention)

    log_debug(interaction, f"{msg}")
    await utils.safe_send(interaction, content=msg, ephemeral=True, is_followup=True)

@bot.tree.command(description='Check a user\'s reported age (search by id)')
@discord.app_commands.describe(user_id='User ID to check')
async def agealt(interaction: discord.Interaction, user_id: str):
    await interaction.response.defer(ephemeral=True)
    
    log_info(interaction, f"{interaction.user} requested age for ID {user_id}")
    if not await utils.ensure_secretary(interaction): return

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

@bot.tree.command(description='Update settings on whether to notify you about pings while you\'re offline')
@discord.app_commands.describe(enable='Enable (on) or disable (off) notifications')
@discord.app_commands.choices(enable=[discord.app_commands.Choice(name="on", value="on"), discord.app_commands.Choice(name="off", value="off")])
async def offlinepings(interaction: discord.Interaction, enable: discord.app_commands.Choice[str]):
    log_info(interaction, f"{interaction.user} requested offlinepings: {enable.value}")

    if enable.value == "on":
        sql.remove_from_offline_ping_blocklist(interaction.user.id)
        await utils.safe_send(interaction, content="Okay, I'll let you know if you're pinged~", ephemeral=True)
    else:
        sql.add_to_offline_ping_blocklist(interaction.user.id)
        await utils.safe_send(interaction, content="Okay, I won't send you notifications if you're pinged~", ephemeral=True)

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
        await utils.safe_send(interaction, content=f"Awww... {user.mention} doesn't have any simps yet")
        return

    msg = f"Here are {user.mention}'s simps~\n> "
    msg += ", ".join([f"{':star:' if id[1] == 1 else ''}<@{id[0]}>" for id in simps])
    await utils.safe_send(interaction, content=msg)

# opts = [discord_slash.manage_commands.create_option(name="range", description="Max days to fetch", option_type=4, required=False)]
# opts += [discord_slash.manage_commands.create_option(name="user", description="User to search (will get messages from all users by default)", option_type=6, required=False)]
@bot.tree.command(description='Get analytics data for user activity')
@discord.app_commands.describe(user='Who you want to query', ignore_games='Ignore messages sent in game channels (default is true)', range='How many days from the current date (default is 14)')
async def activity(interaction: discord.Interaction, user: discord.Member, ignore_games: bool=True, range: int=14):
    await interaction.response.defer(ephemeral=True)

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
    await interaction.response.defer()

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

@bot.tree.command(description='Perform a SQL query')
@discord.app_commands.describe(file='File to connect', query='SQL query')
@discord.app_commands.choices(file=[discord.app_commands.Choice(name=b, value=b) for b in db.sql_files])
async def rawsql(interaction: discord.Interaction, file: discord.app_commands.Choice[str], query: str):
    await interaction.response.defer(ephemeral=True)
    
    log_info(interaction, f"{interaction.user} requested sql query for {file}")
    if not await utils.ensure_admin(interaction): return

    try:
        data = sql.raw_sql(file.value, query)
    except sqlite3.DatabaseError as e:
        log_debug(interaction, f"{interaction.user} query [{query}] failed : {e}")
        await utils.safe_send(interaction, content=f"Failed to execute query [{query}]:\n```\n{traceback.format_exc()}\n```", ephemeral=True, is_followup=True)
        return
    except Exception as e:
        log_debug(interaction, f"{interaction.user} query [{query}] failed : {e}")
        await _dm_log_error(f"[{interaction.channel}] _rawsql\n{e}\n{traceback.format_exc()}")
        await utils.safe_send(interaction, content="Failed to execute query", ephemeral=True, is_followup=True)
        return
        
    if data is None:
        msg = "Your query returned None"
    else:
        msg = f"Here are the results for your query:\n```\n{query}\n\n"
        msg += "\n".join(" | ".join([str(idx + 1)] + [str(item) for item in line]) for idx, line in enumerate(data))
        msg += "\n```"
        if len(msg) > 2000:
            aux = "```\nTRUNC"
            msg = msg[:2000-len(aux)-1] + aux
    await utils.safe_send(interaction, content=msg, ephemeral=True, is_followup=True)

@bot.tree.command(description='Get the daily top 10 rankings')
@discord.app_commands.describe(date='When to fetch data')
async def dailytopten(interaction: discord.Interaction, date: typing.Optional[str]):
    await interaction.response.defer(ephemeral=True)
    
    _date = date or (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    _pdate = datetime.datetime.strptime(_date, "%Y-%m-%d")
    log_info(interaction, f"{interaction.user} requested daily top 10 for {_date}")
    if not await utils.ensure_queen(interaction): return

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
        
    if data is None:
        msg = "Your query returned None"
    else:
        msg = f"Top 10 users for {utils.to_date(_pdate)}!\n"
        msg += "\n".join(" | ".join([utils.to_podium(idx + 1), "\\" + utils.to_mention(line[0]), str(line[1])]) for idx, line in enumerate(data))
        msg += "\n"
        if len(msg) > 2000:
            aux = "\nTRUNC"
            msg = msg[:2000-len(aux)-1] + aux
    await utils.safe_send(interaction, content=msg, ephemeral=True, is_followup=True)

@bot.tree.command(description='Pre-block a user before they\'ve even joined')
@discord.app_commands.describe(user='User ID to block', reason='Reason for block')
async def autoblock(interaction: discord.Interaction, user: str, reason: str):
    await interaction.response.defer(ephemeral=True)

    mod = interaction.user
    _author_roles = [role.id for role in interaction.user.roles]
    log_info(interaction, f"{interaction.user} requested age for {user}")
    if not await utils.ensure_secretary(interaction): return

    try:
        user_id = int(user)
    except:
        log_debug(interaction, f"{user} is not a valid ID")
        await utils.safe_send(interaction, content=f"{user} is not a valid ID", ephemeral=True, is_followup=True)
        return
        
    data = sql.try_autoblock(user_id, mod.id, reason)
    if data is None:
        msg = f"I'll ban them if they ever set foot here, {interaction.user.mention}~"
    else:
        prev_mod_id, prev_reason, date = data
        prev_mod = bot.get_user(prev_mod_id)
        msg = f"That user has already been pre-blocked by {prev_mod.mention} on {date}: {prev_reason}"
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
    msg = f"These are {user.mention}'s known aliases~\n> "
    msg += ", ".join([utils.markdown_surround(alias, "`") for alias in aliases])
    await utils.safe_send(interaction, content=msg, ephemeral=True)

@bot.tree.command(description='Contribute to the server\'s world (heat) map')
@discord.app_commands.describe(country='Where you\'re from')
async def locate(interaction: discord.Interaction, country: str):
    validated_country = utils.validate_country(country)

    if validated_country is None:
        await utils.safe_send(interaction, content=f"I don't know that country... Can you try again, please?", ephemeral=True)

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
    await interaction.response.defer()

    log_info(interaction, f"{interaction.user} requested worldmap")
    if not await utils.ensure_secretary(interaction): return

    report_name = graphlytics.generate_world_heatmap()
    log_debug(interaction, f"report_name={report_name}")
    report_file = discord.File(report_name, filename=f"user_report.png")

    amount = sql.count_worldmap()

    await utils.safe_send(interaction, content=f"Here you go!\nAnd if you haven't already, you can add yourself to the map with `/locate` :heart:\nWe have `{amount}` registered friends~", file=report_file, is_followup=True, send_anyway=True)

    os.remove(report_name)

# TODO parameterize color scheme (graphlytics.cmaps)
@bot.tree.command(description='How many users contributed to the server heatmap (contribute with /locate)')
async def worldmapcount(interaction: discord.Interaction):
    await interaction.response.defer()

    log_info(interaction, f"{interaction.user} requested worldmapcount")
    
    data = sql.count_worldmap()

    await utils.safe_send(interaction, content=f"There are {utils.n_em(data)} registered users!\nAnd if you haven't already, you can add yourself to the map with `/locate` :heart:", is_followup=True, send_anyway=True)

@bot.tree.command(description='Join NNN 2022! Please be aware you can only join/wager ONCE!')
@discord.app_commands.describe(wager='Are you willing to wager one of your roles?')
async def joinnnn(interaction: discord.Interaction, wager: typing.Optional[bool]):
    log_info(interaction, f"{interaction.user} is joining NNN 2022")

    joined = sql.nnn_join(interaction.user.id, wager or False)

    if joined:
        content = f"Thank you for signing up for NNN 2022, {interaction.user.mention}! GLHF~"
    else:
        log_info(interaction, f"{interaction.user} already joined NNN 2022")
        content = f"You've already signed up for NNN 2022, {interaction.user.mention}~"

    await utils.safe_send(interaction, content=content, send_anyway=True)

@bot.tree.command(description='Admit defeat in NNN 2022! Please be aware you cannot take this back!!!')
async def failnnn(interaction: discord.Interaction):
    log_info(interaction, f"{interaction.user} is joining NNN 2022")

    if datetime.datetime.now().month != 11:
        await utils.safe_send(interaction, content=f"You can't fail NNN if it's not november yet, silly~", ephemeral=True)
        return

    data = sql.nnn_status(interaction.user.id)
    log_debug(interaction, f"Got status = {data}")
    if data is None:
        await utils.safe_send(interaction, content=f"You didn't sign up yet, {interaction.user.mention}! You can do that with `/joinnnn`~", send_anyway=True)
        return

    failed = sql.nnn_fail(interaction.user.id)

    if failed:
        content = f"Aww there's always next year, {interaction.user.mention}! Thanks for participating and GG no RE~"
    else:
        log_info(interaction, f"{interaction.user} already failed NNN 2022")
        content = f"You've already failed NNN 2022, {interaction.user.mention}, try again next year~"

    await utils.safe_send(interaction, content=content, send_anyway=True)

@bot.tree.command(description='Check the numbers on NNN 20222')
async def countnnn(interaction: discord.Interaction):
    log_info(interaction, f"{interaction.user} is checking NNN 2022")

    joined, failed = sql.nnn_count()

    content = f"So far, `{joined}` users have joined, and `{failed}` have failed NNN 2022~"

    await utils.safe_send(interaction, content=content, send_anyway=True)

@bot.tree.command(description='Nut counter!')
async def nut(interaction: discord.Interaction):
    log_info(interaction, f"{interaction.user} is adding a nut")

    total = sql.add_nut(interaction.user.id)

    # content = f"{utils.n_em(total)} :chestnut: :peanuts: :coconut:"
    random.seed(interaction.user.id)
    nut_emojis = [":chestnut:", ":peanuts:", ":coconut:"]
    content = " ".join([random.choice(nut_emojis) for _ in range(total)])

    await utils.safe_send(interaction, content=content, send_anyway=True)

bot.tree.add_command(kinks.get_kink_cmds(sql, utils))
bot.tree.add_command(kinks.Kinklist(sql, utils))

@bot.tree.command(description='Find explanations for specific kinks')
async def kinktionary(interaction: discord.Interaction):
    log_info(interaction, f"{interaction.user} requested kinktionary")

    await utils.safe_send(interaction, view=kinks.Kinktionary(interaction), ephemeral=True)

bot.run(TOKEN)
