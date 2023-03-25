import datetime
import discord
import enum
import random
import traceback
import typing

import bot_utils
import botlogger
import db

MODNOTE_EDIT_TIMEOUT_S = 60

async def _silent_reply(interaction: discord.Interaction):
    # print("silent reply")
    try:
        await interaction.response.send_message()
    except discord.errors.HTTPException:
        # print("HTTPException")
        pass # Silently ignore

class DirectionalButton(discord.ui.Button):
    def __init__(self, offset: int, parent, **kwargs):
        super().__init__(**kwargs)
        self.offset = offset
        self.parent = parent
        self.logger = botlogger.get_logger(f"{__name__}::DirectionalButton")

    async def callback(self, interaction: discord.Interaction):
        self.logger.debug(f"{interaction.user}({interaction.user.id}) clicked on {self.offset}")
        await self.parent._on_button_callback(interaction, self.offset)
        await _silent_reply(interaction)

class NotesBrowseView(discord.ui.View):

    def __init__(self, interaction: discord.Interaction, user: discord.Member, revision: int, sql: db.database, utils: bot_utils.utils):
        super().__init__()
        self.logger = botlogger.get_logger(f"{__name__}::NotesBrowseView")
        self.interaction = interaction
        self.target_user = user
        self.current_revision = revision
        self.max_revision = revision
        self.sql = sql
        self.utils = utils

        self.creator = interaction.user

        self.previous_button = DirectionalButton(-1, self, emoji="⬅️")
        self.next_button     = DirectionalButton(+1, self, emoji="➡️")

        self._enable_disable_buttons()
        self.content_text = self._get_content()
        
        self.add_item(self.previous_button)
        self.add_item(self.next_button)

    def _enable_disable_buttons(self):
        self.previous_button.disabled = self.current_revision <= 1
        self.next_button.disabled     = self.current_revision >= self.max_revision

    def _get_content(self):
        raw_data = self.sql.get_modnote(self.target_user.id, self.current_revision)
        if not raw_data:
            return "No data found"
        actual_revision, content, mod_id, updated_at = raw_data
        return f"{content}\n\n> v{actual_revision} by <@{mod_id}> on {self.utils.timestamp(when=updated_at)}"
    
    async def _get_content_as_embed(self):
        raw_data = self.sql.get_modnote(self.target_user.id, self.current_revision)
        # TODO do we really need to handle non-existing data here?

        actual_revision, content, mod_id, updated_at = raw_data

        embed = discord.Embed(
            colour=random.choice(bot_utils.EMBED_COLORS),
            timestamp=datetime.datetime.now()
        )

        moderator = mod_id and await self.interaction.guild.fetch_member(mod_id)

        embed.set_author(name=f'{self.target_user}\'s mod notes', icon_url=self.target_user.avatar.url)
        embed.add_field(name="Content", value=content, inline=False)
        embed.set_footer(text=f"v{actual_revision} submitted by {moderator} on {updated_at.astimezone(datetime.timezone.utc)}")

        return embed
    
    async def _update_view(self):
        return await self.interaction.edit_original_response(embed=await self._get_content_as_embed(), view=self)
        # return await self.interaction.edit_original_response(content=self.content_text, view=self)

    async def _on_button_callback(self, interaction: discord.Interaction, direction: int):
        if direction < 0 and self.current_revision <= 1:
            self.logger.warning("Already on leftmost revision")
            await _silent_reply(interaction)
            await self._update_view()
            return
        
        if direction > 0 and self.current_revision >= self.max_revision:
            self.logger.warning("Already on rightmost revision")
            await _silent_reply(interaction)
            await self._update_view()
            return
        
        self.current_revision += direction

        self._enable_disable_buttons()
        self.content_text = self._get_content()

        await self._update_view()

class NotesWindowModal(discord.ui.Modal, title="User notes editor"):
    def __init__(self, interaction: discord.Interaction, handler, user: discord.Member, revision: int, content: str, moderator: discord.Member, updated_at: datetime.datetime):
        super().__init__(timeout=MODNOTE_EDIT_TIMEOUT_S)
        self.logger = botlogger.get_logger(f"{__name__}::NotesWindowModal")
        self.interaction = interaction
        self.handler = handler
        self.user_id = user.id
        self.mod_id = interaction.user.id
        if revision > 0:
            label = f"{user}'s info (v{revision+1})"
        else:
            label = f"{user}'s info (first revision)"
        self._content_text = discord.ui.TextInput(label=label, style=discord.TextStyle.paragraph, default=content, required=False)
        self.add_item(self._content_text)

    async def on_timeout(self) -> None:
        self.logger.info(f"on_timeout: {self._content_text.value}")
        self._on_free()
    
    async def on_error(self, interaction: discord.Interaction, error: Exception, /) -> None:
        self.logger.info(f"on_error: {self._content_text.value} by {interaction.user}")
        self._on_free()
        
    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.logger.info(f"on_submit: {self._content_text.value} by {interaction.user}")
        self.handler._cb_update_modnote(self.user_id, self.mod_id, self._content_text.value)
        await interaction.response.send_message(content=f"Okay, I've written that down for <@{self.user_id}>!\nYou can check it out with /modnotes get <@{self.user_id}>~", ephemeral=True)
        self._on_free()

    def _on_free(self):
        self.handler._cb_on_free(self.user_id)

class modnotes_handler:
    def __init__(self, sql: db.database, utils: bot_utils.utils):
        self.sql = sql
        self.utils = utils
        self.locks = {}

        self.logger = botlogger.get_logger(f"{__name__}::modnotes_handler")
    
    def _cb_on_free(self, user: int):
        self.logger.debug(f"Free lock {user}")
        del(self.locks[user])

    async def edit_modnote(self, interaction: discord.Interaction, user: discord.Member):
        if user.id in self.locks:
            return await interaction.response.send_message(content=f"<@{self.locks[user.id]}> is already editing notes for {user}, please try again in a few minutes~", ephemeral=True)
        
        self.locks[user.id] = interaction.user.id
        
        latest_revision, content, mod_id, updated_at = self.sql.get_modnote(user.id) or (0, '', None, None)

        moderator = mod_id and await interaction.guild.fetch_member(mod_id)
        
        window = NotesWindowModal(interaction, self, user, latest_revision, content, moderator, updated_at)
        return await interaction.response.send_modal(window)
    
    def _cb_update_modnote(self, user: int, mod: int, content: str):
        self.sql.create_or_update_modnote(user, mod, content)

@discord.app_commands.guild_only()
class Modnotes(discord.app_commands.Group):
    def __init__(self, database: db.database, utils: bot_utils.utils):
        super().__init__()
        self.database = database
        self.utils = utils
        self.handler = modnotes_handler(database, utils)

        self.logger = botlogger.get_logger(f"{__name__}::Modnotes")
    
    @discord.app_commands.command(description='Create or edit a user\'s mod note (be aware this can be seen by the entire mod team)')
    async def edit(self, interaction: discord.Interaction, user: discord.Member):
        self.logger.info(f"{interaction.user} requested modnotes edit: {user}")

        if not await self.utils.ensure_secretary(interaction): return

        await self.handler.edit_modnote(interaction, user)
    
    @discord.app_commands.command(description='Fetch a user\'s mod note')
    @discord.app_commands.describe(revision='Which version of the note to retrieve (will retrieve latest by default)')
    async def get(self, interaction: discord.Interaction, user: discord.Member, revision: typing.Optional[int]=None):
        self.logger.info(f"{interaction.user} requested modnotes get: {user}")

        if not await self.utils.ensure_secretary(interaction): return

        raw_data = self.database.get_modnote(user.id, revision=revision)
        if not raw_data:
            await self.utils.safe_send(interaction, content=f"I couldn't find notes for that user...", ephemeral=True)
            return
        
        actual_revision, content, mod_id, updated_at = raw_data
        moderator = mod_id and await interaction.guild.fetch_member(mod_id)

        embed = discord.Embed(
            colour=random.choice(bot_utils.EMBED_COLORS),
            timestamp=datetime.datetime.now()
        )

        embed.set_author(name=f'{user}\'s mod notes', icon_url=user.avatar.url)
        embed.add_field(name="Content", value=content, inline=False)
        embed.set_footer(text=f"v{actual_revision} submitted by {moderator} on {self.utils.timestamp(when=updated_at.astimezone(datetime.timezone.utc))}")

        await self.utils.safe_send(interaction, embed=embed, ephemeral=True)

    @discord.app_commands.command(description='Fetch a user\'s browsable mod note')
    async def browse(self, interaction: discord.Interaction, user: discord.Member):
        self.logger.info(f"{interaction.user} requested modnotes browse: {user}")

        if not await self.utils.ensure_secretary(interaction): return

        raw_data = self.database.get_modnote(user.id)
        if not raw_data:
            await self.utils.safe_send(interaction, content=f"I couldn't find notes for that user...", ephemeral=True)
            return
        
        actual_revision, content, _, _ = raw_data

        browse_view = NotesBrowseView(interaction, user, actual_revision, self.database, self.utils)

        await self.utils.safe_send(interaction, 
            embed=await browse_view._get_content_as_embed(),
            view=browse_view,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none())
            # content=browse_view.content_text, 

