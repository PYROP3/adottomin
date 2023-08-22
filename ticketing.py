import datetime
import discord
import enum
import random
import traceback
import typing

import bot_utils
import botlogger
import db
import propervider as p

from discord.ext import commands

# MODNOTE_EDIT_TIMEOUT_S = 60

async def _silent_reply(interaction: discord.Interaction):
    # print("silent reply")
    try:
        await interaction.response.send_message()
    except discord.errors.HTTPException:
        # print("HTTPException")
        pass # Silently ignore

# ===================================================== TICKET CREATION =====================================================
class TicketCreatorWindowModal(discord.ui.Modal, title="Ticket creation"):
    def __init__(self, interaction: discord.Interaction, handler, sql: db.database, attachment: typing.Optional[discord.Attachment]=None):
        super().__init__()
        self.interaction = interaction
        self.handler = handler
        self.sql = sql
        self._content_text = discord.ui.TextInput(label="Ticket contents", style=discord.TextStyle.paragraph, required=False)
        self._evidence_text = discord.ui.TextInput(label="Evidence/screenshots (URL) - optional", style=discord.TextStyle.short, required=False, default=str(attachment) if attachment else None, placeholder="https://...")
        self.add_item(self._content_text)
        self.add_item(self._evidence_text)

    def auto_render(self):
        message = self._content_text.value
        if len(message) == 0:
            message = None
        evidence = self._evidence_text.value
        if len(evidence) == 0:
            evidence = None
        return self.render_embed(message=message, evidence=evidence)

    def render_embed(self, message: typing.Optional[str]=None, evidence: typing.Optional[str]=None):
        is_anonymous = True

        embed = discord.Embed(
            colour=discord.Color.red(),
            timestamp=datetime.datetime.now()
        )
        
        ticket_id = self.sql.create_ticket(self.interaction.user.id, message, is_anonymous, evidence=evidence)
        embed.set_footer(text=f'ID: {ticket_id}')
        
        if not is_anonymous:
            try:
                icon_url = self.interaction.user.avatar.url
            except Exception as e:
                self.logger.warning(f"Exception while trying to handle icon thumbnail: {e}\n{traceback.format_exc()}")
                icon_url = None

            embed.set_author(name=f'Ticket by {self.interaction.user}', icon_url=icon_url)
        else:
            embed.set_author(name=f'Anonymous ticket')

        if message:
            embed.add_field(name=f"Contents", value=message, inline=False)

        if evidence:
            embed.set_image(url=evidence)

        return embed, message, ticket_id
        
    async def on_submit(self, interaction: discord.Interaction) -> None:
        new_embed, is_valid, ticket_id = self.auto_render()
        if is_valid:
            message, explanation = await self.handler._finish_creating_ticket(new_embed)
            await interaction.response.send_message(content=explanation, ephemeral=True)
            self.sql.update_ticket_message_id(ticket_id, message.id)
        else:
            await interaction.response.send_message(content=f"Please input at least the text for the ticket~", ephemeral=True)

class ticket_creation_handler:
    def __init__(self, bot: commands.Bot, ticket_slowmode: datetime.timedelta, sql: db.database, utils: bot_utils.utils):
        self.ticket_slowmode = ticket_slowmode
        self.sql = sql
        self.bot = bot
        self.utils = utils

        self.logger = botlogger.get_logger(__name__)

    async def on_bot_ready(self):
        self.tickets_channel = await self.bot.fetch_channel(p.pint("TICKET_CHANNEL_ID"))
        
    # async def try_remove_ticket(self, user: int):
    #     ticket_data = self.sql.get_existing_ticket(user)
    #     if ticket_data:
    #         message_id, _ = int(ticket_data[0]), self.utils.db2datetime(ticket_data[1])

    #         try:
    #             old_ad = await self.tickets_channel.fetch_message(message_id)
    #             await old_ad.delete()
    #         except:
    #             pass
    #         return True
    #     return False

    async def create_ticket(self, interaction: discord.Interaction, attachment: typing.Optional[discord.Attachment]=None):
        ticket_data = self.sql.get_latest_ticket(interaction.user.id)
        if ticket_data:
            created_at = self.utils.db2datetime(ticket_data[0])

            if (created_at + self.ticket_slowmode) > datetime.datetime.now():
                return await self.utils.safe_send(interaction, content=f"You must wait a while before creating a new ticket~", ephemeral=True)
        
        window = TicketCreatorWindowModal(interaction, self, self.sql, attachment=attachment)
        return await interaction.response.send_modal(window)

    async def _finish_creating_ticket(self, embed: discord.Embed):
        try:
            ticket = await self.tickets_channel.send(embed=embed)
            return ticket, f"I've created a ticket as you requested, and the mods will take care of it ASAP~"
        except discord.errors.HTTPException:
            self.logger.debug("HTTPException in self.tickets_channel.send (url is probably incorrect)")
            return None, f"Hmm that doesn't look like a valid URL, try again pls~"
        
    async def resolve_ticket(self, interaction: discord.Interaction, ticket_id: int, resolution: str):
        message_id = self.sql.resolve_ticket(ticket_id, resolution, interaction.user.id)
        if message_id:
            msg = await self.tickets_channel.fetch_message(message_id)
            if not msg:
                pass # TODO send a new message in case the old one has been ddeleted
            embed = msg.embeds[0]
            embed.color = discord.Color.green()
            if embed.fields[-1].name != 'Resolution':
                embed.remove_field(len(embed.fields) - 1)
            embed.add_field(name=f"Resolution", value=resolution, inline=False)
            await msg.edit(embed=embed)
            return True
        return False

# ===================================================== TICKET NAVIGATION =====================================================

class FunctionalButton(discord.ui.Button):
    def __init__(self, callback: typing.Callable, **kwargs):
        super().__init__(**kwargs)
        self._cb = callback
        self.logger = botlogger.get_logger(f"{__name__}::FunctionalButton")
        self.logger.setLevel("INFO")

    async def callback(self, interaction: discord.Interaction):
        self.logger.debug(f"{interaction.user}({interaction.user.id}) clicked on {self}")
        await self._cb(interaction)

class TicketsBrowseView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, user: discord.Member, ticket: int, sql: db.database, utils: bot_utils.utils):
        super().__init__()
        self.logger = botlogger.get_logger(f"{__name__}::TicketsBrowseView")
        self.logger.setLevel("INFO")
        self.interaction = interaction
        self.target_user = user
        self.current_ticket = ticket
        self.sql = sql
        self.utils = utils

        self.creator = interaction.user

        self.previous_button = FunctionalButton(lambda interaction: self._directional_callback(interaction, -1), self, emoji="⬅️")
        # self.resolve_button  = FunctionalButton(lambda interaction: (), emoji="✅") # TODO
        self.next_button     = FunctionalButton(lambda interaction: self._directional_callback(interaction, +1), self, emoji="➡️")

        self._enable_disable_buttons()
        self.content_text = self._get_content()
        
        self.add_item(self.previous_button)
        # self.add_item(self.resolve_button)
        self.add_item(self.next_button)

    def _enable_disable_buttons(self):
        self.previous_button.disabled = self.current_revision <= 1
        self.next_button.disabled     = self.current_revision >= self.max_revision

    def _get_content(self):
        raw_data = self.sql.get_ticket(self.current_ticket)
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

        embed.set_author(name=f'{self.target_user}\'s mod tickets', icon_url=self.target_user.avatar.url)
        embed.add_field(name="Content", value=content, inline=False)
        embed.set_footer(text=f"v{actual_revision} submitted by {moderator} on {updated_at.astimezone(datetime.timezone.utc)}")

        return embed
    
    async def _update_view(self):
        return await self.interaction.edit_original_response(embed=await self._get_content_as_embed(), view=self)
        # return await self.interaction.edit_original_response(content=self.content_text, view=self)

    async def _directional_callback(self, interaction: discord.Interaction, direction: int):
        if direction < 0 and self.current_revision <= 1:
            self.logger.warning("Already on leftmost revision")
            await _silent_reply(interaction)
            await self._update_view()
            await _silent_reply(interaction)
            return
        
        if direction > 0 and self.current_revision >= self.max_revision:
            self.logger.warning("Already on rightmost revision")
            await _silent_reply(interaction)
            await self._update_view()
            await _silent_reply(interaction)
            return
        
        self.current_revision += direction

        self._enable_disable_buttons()
        self.content_text = self._get_content()

        await self._update_view()
        await _silent_reply(interaction)

# class TicketsWindowModal(discord.ui.Modal, title="User tickets editor"):
#     def __init__(self, interaction: discord.Interaction, handler, user: discord.Member, revision: int, content: str, moderator: discord.Member, updated_at: datetime.datetime):
#         super().__init__(timeout=MODNOTE_EDIT_TIMEOUT_S)
#         self.logger = botlogger.get_logger(f"{__name__}::TicketsWindowModal")
#         self.interaction = interaction
#         self.handler = handler
#         self.user_id = user.id
#         self.mod_id = interaction.user.id
#         shortname = name if len(name := str(user)) < 20 else name[:17] + "..."
#         if revision > 0:
#             label = f"{shortname}'s info (v{revision+1})"
#         else:
#             label = f"{shortname}'s info (first revision)"
#         self._content_text = discord.ui.TextInput(label=label, style=discord.TextStyle.paragraph, default=content, required=False)
#         self.add_item(self._content_text)

#     async def on_timeout(self) -> None:
#         self.logger.info(f"on_timeout: {self._content_text.value}")
#         self._on_free()
    
#     async def on_error(self, interaction: discord.Interaction, error: Exception, /) -> None:
#         self.logger.info(f"on_error: {self._content_text.value} by {interaction.user}")
#         self._on_free()
        
#     async def on_submit(self, interaction: discord.Interaction) -> None:
#         self.logger.info(f"on_submit: {self._content_text.value} by {interaction.user}")
#         self.handler._cb_update_modnote(self.user_id, self.mod_id, self._content_text.value)
#         await interaction.response.send_message(content=f"Okay, I've written that down for <@{self.user_id}>!\nYou can check it out with /modtickets get <@{self.user_id}>~", ephemeral=True)
#         self._on_free()

#     def _on_free(self):
#         self.handler._cb_on_free(self.user_id)

# class modtickets_handler:
#     def __init__(self, sql: db.database, utils: bot_utils.utils):
#         self.sql = sql
#         self.utils = utils
#         self.locks = {}

#         self.logger = botlogger.get_logger(f"{__name__}::modtickets_handler")
    
#     def _cb_on_free(self, user: int):
#         self.logger.debug(f"Free lock {user}")
#         del(self.locks[user])

#     async def edit_modnote(self, interaction: discord.Interaction, user: discord.Member):
#         if user.id in self.locks:
#             return await interaction.response.send_message(content=f"<@{self.locks[user.id]}> is already editing tickets for {user}, please try again in a few minutes~", ephemeral=True)
        
#         self.locks[user.id] = interaction.user.id
        
#         latest_revision, content, mod_id, updated_at = self.sql.get_modnote(user.id) or (0, '', None, None)

#         moderator = mod_id and await interaction.guild.fetch_member(mod_id)
        
#         window = TicketsWindowModal(interaction, self, user, latest_revision, content, moderator, updated_at)
#         return await interaction.response.send_modal(window)
    
#     def _cb_update_modnote(self, user: int, mod: int, content: str):
#         self.sql.create_or_update_modnote(user, mod, content)

@discord.app_commands.guild_only()
class Ticket(discord.app_commands.Group):
    def __init__(self, database: db.database, utils: bot_utils.utils, creation_handler: ticket_creation_handler):
        super().__init__()
        self.database = database
        self.utils = utils
        self.creation_handler = creation_handler
        # self.browse_handler = browse_handler

        self.logger = botlogger.get_logger(f"{__name__}::Ticket")
    
    @discord.app_commands.command(description='Create a ticket for the moderation team')
    async def create(self, interaction: discord.Interaction, attachment: typing.Optional[discord.Attachment]=None):
        self.logger.info(f"{interaction.user} requested new ticket")
        await self.creation_handler.create_ticket(interaction, attachment=attachment)
    
    @discord.app_commands.command(description='Mark a ticket as resolved')
    async def resolve(self, interaction: discord.Interaction, ticket: int, resolution: str):
        self.logger.info(f"{interaction.user} requested new ticket")
        success = await self.creation_handler.resolve_ticket(interaction, ticket, resolution)
        if success:
            await self.utils.safe_send(interaction, content="Ticket resolved!")
    
    # @discord.app_commands.command(description='Fetch a user\'s mod note')
    # @discord.app_commands.describe(revision='Which version of the note to retrieve (will retrieve latest by default)')
    # async def get(self, interaction: discord.Interaction, user: discord.Member, revision: typing.Optional[int]=None):
    #     self.logger.info(f"{interaction.user} requested modtickets get: {user}")

    #     raw_data = self.database.get_modnote(user.id, revision=revision)
    #     if not raw_data:
    #         await self.utils.safe_send(interaction, content=f"I couldn't find tickets for that user...", ephemeral=True)
    #         return
        
    #     actual_revision, content, mod_id, updated_at = raw_data
    #     moderator = mod_id and await interaction.guild.fetch_member(mod_id)

    #     embed = discord.Embed(
    #         colour=random.choice(bot_utils.EMBED_COLORS),
    #         timestamp=datetime.datetime.now()
    #     )

    #     embed.set_author(name=f'{user}\'s mod tickets', icon_url=user.avatar.url)
    #     embed.add_field(name="Content", value=content, inline=False)
    #     embed.set_footer(text=f"v{actual_revision} submitted by {moderator} on {self.utils.timestamp(when=updated_at.astimezone(datetime.timezone.utc))}")

    #     await self.utils.safe_send(interaction, embed=embed, ephemeral=True)

    # @discord.app_commands.command(description='Fetch a user\'s browsable mod note')
    # async def browse(self, interaction: discord.Interaction, user: discord.Member):
    #     self.logger.info(f"{interaction.user} requested modtickets browse: {user}")

    #     if not await self.utils.ensure_secretary(interaction): return

    #     raw_data = self.database.get_modnote(user.id)
    #     if not raw_data:
    #         await self.utils.safe_send(interaction, content=f"I couldn't find tickets for that user...", ephemeral=True)
    #         return
        
    #     actual_revision, content, _, _ = raw_data

    #     browse_view = TicketsBrowseView(interaction, user, actual_revision, self.database, self.utils)

    #     await self.utils.safe_send(interaction, 
    #         embed=await browse_view._get_content_as_embed(),
    #         view=browse_view,
    #         ephemeral=True,
    #         allowed_mentions=discord.AllowedMentions.none())
    #         # content=browse_view.content_text, 

