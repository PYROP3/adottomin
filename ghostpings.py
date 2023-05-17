import datetime
from typing import Any
import discord
import enum
import random
import traceback
import typing

from discord.interactions import Interaction

import botlogger
import db

logger = botlogger.get_logger(f"{__name__}")

async def _silent_reply(interaction: discord.Interaction):
    # print("silent reply")
    try:
        await interaction.response.send_message()
    except discord.errors.HTTPException:
        # print("HTTPException")
        pass # Silently ignore

class GhostpingsStatus(enum.Enum):
    Offline = (1<<0, '⚫')
    Busy    = (1<<1, '🔴')
    Away    = (1<<2, '🟡')
    Online  = (1<<3, '🟢')

_bitmask_conversion = {
    discord.Status.offline: GhostpingsStatus.Offline,
    discord.Status.invisible: GhostpingsStatus.Offline,
    discord.Status.dnd: GhostpingsStatus.Busy,
    discord.Status.idle: GhostpingsStatus.Away,
    discord.Status.online: GhostpingsStatus.Online
}

class GhostpingsStatusSelect(discord.ui.Select):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent = parent
        self.logger = botlogger.get_logger(f"{__name__}::GhostpingsStatusSelect")

    async def callback(self, interaction: discord.Interaction):
        self.logger.info(f"callback: {self.values} by {interaction.user}")
        # self.handler._cb_update_modnote(self.user_id, self.mod_id, self._content_text.value)
        # await interaction.response.send_message(content=f"Okay, I've written that down for <@{self.user_id}>!\nYou can check it out with /modnotes get <@{self.user_id}>~", ephemeral=True)
        new_bitmask = 0
        for opt in self.values:
            new_bitmask |= int(opt)
        
        await self.parent._callback(interaction, new_bitmask)

class GhostPingsSettingsView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, sql: db.database):
        super().__init__()
        self.logger = botlogger.get_logger(f"{__name__}::GhostPingsWindowModal")
        self.interaction = interaction
        self.sql = sql
        prev_bitmask = sql.get_ghost_ping_settings(interaction.user.id)
        self.opts = [discord.components.SelectOption(label=status.name, value=status.value[0], emoji=status.value[1], default=bool(prev_bitmask & status.value[0])) for status in GhostpingsStatus]
        self.select = GhostpingsStatusSelect(self, min_values=0, max_values=len(GhostpingsStatus), options=self.opts)
        self.add_item(self.select)

    # async def on_timeout(self) -> None:
    #     self.logger.debug(f"on_timeout: {self.interaction.user} / {self.select.values}")
    
    async def on_error(self, interaction: discord.Interaction, error: Exception, item) -> None:
        self.logger.error(f"on_error: {self.select.values} by {interaction.user}: {error}")

    async def _callback(self, interaction: discord.Interaction, bitmask: int):
        self.logger.info(f"_callback: set ghost pings as {bitmask} for {interaction.user}")
        self.sql.set_ghost_ping_settings(interaction.user.id, bitmask)
        if bitmask == 0:
            content = "Okay, I won't notify you about ghost pings! Feel free to change your preferences at any time~"
        else:
            content = "Alrighty, I updated your preferences! Feel free to change them at any time~"
        await interaction.response.send_message(content=content, ephemeral=True)

    def _on_free(self):
        pass
        # self.handler._cb_on_free(self.user_id)

def compute_user_bitmask(user: discord.Member, sql: db.database):
    current_bitmask = user.status in _bitmask_conversion and _bitmask_conversion[user.status].value[0] or GhostpingsStatus.Offline.value[0]
    allow_bitmask = sql.get_ghost_ping_settings(user.id)
    # logger.debug(f"Compare bitmask {current_bitmask} to {allow_bitmask} = {bool(current_bitmask & allow_bitmask)}")
    return bool(current_bitmask & allow_bitmask)

# MODALS DON'T WORK WITH SelectOption !!!
# class GhostPingsWindowModal(discord.ui.Modal, title="Ghost ping settings"):
#     def __init__(self, interaction: discord.Interaction, handler):
#         super().__init__(timeout=MODNOTE_EDIT_TIMEOUT_S)
#         self.logger = botlogger.get_logger(f"{__name__}::GhostPingsWindowModal")
#         self.interaction = interaction
#         self.handler = handler
#         self.opts = [discord.components.SelectOption(label=status.name, value=status.value[0], emoji=status.value[1]) for status in GhostpingsStatus]
#         self.add_item(discord.ui.Select(min_values=0, max_values=len(GhostpingsStatus), options=self.opts))

#     async def on_timeout(self) -> None:
#         self.logger.info(f"on_timeout: {self.opts}")
#         self._on_free()
    
#     async def on_error(self, interaction: discord.Interaction, error: Exception, /) -> None:
#         self.logger.info(f"on_error: {self.opts} by {interaction.user}")
#         self._on_free()
        
#     async def on_submit(self, interaction: discord.Interaction) -> None:
#         self.logger.info(f"on_submit: {self.opts} by {interaction.user}")
#         # self.handler._cb_update_modnote(self.user_id, self.mod_id, self._content_text.value)
#         # await interaction.response.send_message(content=f"Okay, I've written that down for <@{self.user_id}>!\nYou can check it out with /modnotes get <@{self.user_id}>~", ephemeral=True)
#         await interaction.response.send_message(content=f"Donion rings", ephemeral=True)
#         self._on_free()

#     def _on_free(self):
#         pass
#         # self.handler._cb_on_free(self.user_id)

@discord.app_commands.guild_only()
class Ghostpings(discord.app_commands.Group):
    def __init__(self, database: db.database, utils):
        super().__init__()
        self.database = database
        self.utils = utils

        self.logger = botlogger.get_logger(f"{__name__}::Ghostpings")
    
    @discord.app_commands.command(description='Edit your settings for ghost pings notifications')
    async def settings(self, interaction: discord.Interaction):
        self.logger.info(f"{interaction.user} requested ghostpings settings edit")

        await self.utils.safe_send(interaction, 
            content="Please choose in which status(es) Botto should be allowed to send you ghost ping notifications~", 
            view=GhostPingsSettingsView(interaction, self.database),
            ephemeral=True)
