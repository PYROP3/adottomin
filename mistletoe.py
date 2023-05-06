import asyncio
import discord

import botlogger
import msg_handler_manager

logger = botlogger.get_logger(__name__)

class mistletoe_handler:
    def __init__(self, mhm: msg_handler_manager.HandlerManager):
        self.pending_mistletoes = {}
        self.awaiting_users = {}
        self.mhm = mhm
        mhm.register_dynamic(self.handle_mistletoe_msg)

    def try_new_mistletoe(self, channel: int, users: int):
        logger.debug(f"try_new_mistletoe: {channel} ({users})")
        will_create = channel not in self.pending_mistletoes

        if will_create:
            self.mhm.create_dyn_lock(self.handle_mistletoe_msg, channel)
            self.awaiting_users[channel] = users
            self.pending_mistletoes[channel] = []

        return will_create

    def clear_mistletoe(self, channel: int):
        logger.debug(f"clear_mistletoe: {channel}")
        self.mhm.remove_dyn_lock(self.handle_mistletoe_msg, channel)
        del(self.pending_mistletoes[channel])
        del(self.awaiting_users[channel])

    async def handle_mistletoe_msg(self, msg: discord.Message):
        if msg.channel.id not in self.pending_mistletoes:
            return
        
        if len(self.pending_mistletoes[msg.channel.id]) >= self.awaiting_users[msg.channel.id]:
            logger.warning(f"handle_mistletoe_msg mistletoe for {msg.channel} already fulfilled")
            self.clear_mistletoe(msg.channel.id)
            return

        if msg.author.id in self.pending_mistletoes[msg.channel.id]:
            logger.debug(f"handle_mistletoe_msg author {msg.author} already in {msg.channel} list")
            return
        
        logger.debug(f"handle_mistletoe_msg add author {msg.author} to {msg.channel} list")
        self.pending_mistletoes[msg.channel.id] += [msg.author.id]

        if len(self.pending_mistletoes[msg.channel.id]) >= self.awaiting_users[msg.channel.id]:
            logger.debug(f"handle_mistletoe_msg got required {self.awaiting_users[msg.channel.id]} users")
            users = self.pending_mistletoes[msg.channel.id]
            users_str = ", ".join([f'<@{user}>' for user in users[:-1]])
            await msg.channel.send(content=f"Now {users_str} and <@{users[-1]}> gotta kiss under the mistletoe~!")
            self.clear_mistletoe(msg.channel.id)
