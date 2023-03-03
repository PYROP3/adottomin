import discord
import asyncio
import typing

import botlogger
import bot_utils
import db

from discord.ext import commands
#emoji_prog = re.compile(r"^((<a?:[^:]+:[0-9]+>)|(:[^: ]+:)|([ \n]))+$")

logger = botlogger.get_logger(__name__)

class horny_handler:
    def __init__(self, bot: commands.Bot, utils: bot_utils.utils, sql: db.database, nohorny_chats: list[int], horny_role: int):
        self.utils = utils
        self.sql = sql
        self.bot = bot
        self.emojichat = None
        self.horny_role_id = set([horny_role])
        self.nohorny_chats = nohorny_chats
        self.main_chat = None

    def inject(self, main_chat: discord.TextChannel):
        self.main_chat=main_chat
        
    async def handle_horny(self, msg: discord.Message):
        try:
            await self.utils._enforce_has_role(msg, self.horny_role_id)
        except asyncio.TimeoutError:
            logger.debug(f"handle_horny._enforce_has_role raised asyncio.TimeoutError")
            return

        if msg.channel.id not in self.nohorny_chats:
            return
        
        await msg.delete()
        await msg.channel.send(content=f"Silence, horny~", delete_after=3)

    async def handle_member_remove_horny(self, before: discord.Member, after: discord.Member):
        # We're only interested if `before` has jail role AND `after` does not
        if self.horny_role_id.intersection([role.id for role in before.roles]) == set():
            # No intersection, means user didn't have the role
            return

        if self.horny_role_id.intersection([role.id for role in after.roles]) != set():
            # No intersection, means user still has the role
            return
        
        is_jailed, _ = self.sql.jail_is_currently_jailed(after.id)
        if not is_jailed:
            # if user is not jailed (by the database), removal is allowed
            # logger.debug(f"handle_member_remove_horny sentence already over")
            return

        # logger.debug(f"handle_member_remove_horny forced removal: re-adding")
        jail_role = self.main_chat.guild.get_role(next(iter(self.horny_role_id)))
        await after.add_roles(jail_role, reason=f'user tried to force remove jail role')
        await self.main_chat.send(content=f"Did you really think you were gonna get off the hook so easily, {after.mention}~?", delete_after=3)

    async def handle_horny_role_toggle(self, before: discord.Member, after: discord.Member, on_receive: typing.Callable, on_lose: typing.Callable):
        has_before = len(self.horny_role_id.intersection([role.id for role in before.roles])) == 1
        has_after = len(self.horny_role_id.intersection([role.id for role in after.roles])) == 1

        if has_before and not has_after:
            on_lose()
            return
        
        if has_after and not has_before:
            on_receive()
            