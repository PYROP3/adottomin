import discord
import msg_handler_manager
import re
import traceback
import typing
import enum

import bot_utils
import botlogger
import db
import propervider as p

from datetime import datetime, timedelta
from discord.ext import commands

class ParamParseException(Exception):
    pass

class ActionParams:
    def __init__(self, verb: str, verb_past: str, embed_color: discord.Colour):
        self.verb = verb
        self.verb_past = verb_past
        self.embed_color = embed_color
    
    def extract_params(self, msg: typing.List[str]):
        return {'reason_notif': ' '.join(msg)}
    
class TimedActionParams(ActionParams):
    def extract_params(self, msg: typing.List[str]):
        td = bot_utils.extract_timedelta(msg[0])
        if not td:
            raise ParamParseException("You must provide a time value, dummy!")
        return {'reason_notif': ' '.join(msg[1:]), 'until': td}

class actions(enum.Enum):
    Ban  =      ActionParams("ban",  "banned", discord.Color.red())
    Kick =      ActionParams("kick", "kicked", discord.Color.yellow())
    Mute = TimedActionParams("mute", "muted",  discord.Color.blue())

VALID_MOD_COMMANDS = {act.value.verb: act for act in actions}
USER_PROG = re.compile(r"<@([0-9]+)>|([0-9]+)")
MOD_COMMANDS_PREFIX = '.'

class ModerationCore:
    def __init__(self, bot: commands.Bot, database: db.database, utils: bot_utils.utils, mhm: msg_handler_manager.HandlerManager, mod_role_id: int):
        self.database = database
        self.bot = bot
        self.utils = utils
        self.mod_role_id = set([mod_role_id])
        mhm.register_static(self.handle_mod_message)

        self.logger = botlogger.get_logger(__name__)

    def inject(self, log_channel: discord.TextChannel):
        self.log_channel = log_channel

    async def generate_log_embed(self, action: actions, user: discord.Member, reason: str, duration: typing.Optional[timedelta] = None):
        embed = discord.Embed(
            colour=action.value.embed_color,
            timestamp=datetime.now()
        )
        embed.add_field(name="User", value=user.mention, inline=True)
        embed.add_field(name="Moderator", value=self.bot.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason or "<not given>", inline=True)
        if duration:
            embed.add_field(name="Duration", value=str(duration), inline=True)
        embed.set_footer(text=f'ID: {user.id}')
        embed.set_author(name=f"{action.value.verb.capitalize()} | {user.name}", icon_url=user.avatar and user.avatar.url)
        return embed

    async def core_ban(self, user: discord.Member, repliable: typing.Union[discord.Interaction, discord.TextChannel], reason_notif: typing.Optional[str] = None, reason_log: typing.Optional[str] = None):
        return await self._do_generic(actions.Ban, user, repliable, reason_notif=reason_notif, reason_log=reason_log)

    async def core_kick(self, user: discord.Member, repliable: typing.Union[discord.Interaction, discord.TextChannel], reason_notif: typing.Optional[str] = None, reason_log: typing.Optional[str] = None):
        return await self._do_generic(actions.Kick, user, repliable, reason_notif=reason_notif, reason_log=reason_log)

    async def core_mute(self, user: discord.Member, until: typing.Optional[typing.Union[timedelta, datetime]], repliable: typing.Union[discord.Interaction, discord.TextChannel], reason_notif: typing.Optional[str] = None, reason_log: typing.Optional[str] = None):
        return await self._do_generic(actions.Mute, user, repliable, reason_notif=reason_notif, reason_log=reason_log, until=until)
    
    async def handle_mod_message(self, msg: discord.Message):
        await self.utils._enforce_not_dms(msg)
        await self.utils._enforce_has_role(msg, self.mod_role_id)
        content = msg.content.split(' ')
        if len(content) < 2: return
        if content[0][0] != MOD_COMMANDS_PREFIX: return
        cmd = content[0][1:].lower()
        self.logger.debug(f"cmd={cmd}")
        if cmd not in VALID_MOD_COMMANDS: return
        action = VALID_MOD_COMMANDS[cmd]
        target = USER_PROG.match(content[1])
        if not target:
            await msg.reply(content=f"Pls try again with a real user this time :c")
            return
        
        try:
            target = await msg.guild.fetch_member(int(target.groups()[0]))
        except discord.errors.NotFound:
            await msg.reply(content=f"I couldn't find a user with that ID :c")
            return
        
        try:
            params = action.value.extract_params(content[2:])
        except ParamParseException as e:
            await msg.reply(content=str(e))
            return
        
        self.database.register_command(msg.author.id, cmd, msg.channel.id, args=' '.join(content[1:]))
        await self._do_generic(action, target, msg, **params)
    
    async def _do_reply(self, repliable: typing.Union[discord.Interaction, discord.Message, discord.TextChannel], content=str, ephemeral: bool=False):
        if isinstance(repliable, discord.Interaction):
            await self.utils.safe_send(repliable, content=content, ephemeral=ephemeral)
        elif isinstance(repliable, discord.Message):
            await repliable.reply(content=content)
        else:
            await repliable.send(content=content)
    
    async def _do_generic(self, action: actions, user: discord.Member, repliable: typing.Union[discord.Interaction, discord.TextChannel], reason_notif: typing.Optional[str] = None, reason_log: typing.Optional[str] = None, **extras):
        reason_log = reason_log or reason_notif
        extras.update(reason=reason_log)
        self.logger.debug(f"_do_generic {action} for {user}: {reason_notif} ({extras})")
        try:
            if action == actions.Ban: await user.ban(reason=reason_log)
            elif action == actions.Kick: await user.kick(reason=reason_log)
            elif action == actions.Mute: await user.timeout(extras['until'], reason=reason_log)
            # await {
            #     actions.Ban: user.ban,
            #     actions.Kick: user.kick,
            #     actions.Mute: user.timeout
            # }[action](**extras)
            reply_content = f"{user.mention} was {action.value.verb_past}"
            duration = None
            if 'until' in extras:
                duration = extras['until']
                reply_content += f" for {str(duration)}"
            if reason_notif:
                reply_content += f" cuz {reason_notif}"
            await self._do_reply(repliable, reply_content)
            await self.log_channel.send(embed=await self.generate_log_embed(action, user, reason_log, duration=duration))
            return True
        except discord.NotFound:
            self.logger.debug(f"User id {user} already left!")
            await self._do_reply(repliable, f"{user.mention} isn't here anymore, dummy~")
        except Exception as e:
            self.logger.error(f"Error while trying to log error: {e}\n{traceback.format_exc()}")
            self.logger.error(f"Failed to {action.value.verb} user id {user}!")
            await self._do_reply(repliable, f"I couldn't {action.value.verb} {user.mention} for some reason...")
        return False
