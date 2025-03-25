import datetime
import discord
import random
import traceback
import typing

import bot_utils
import botlogger
import db

class AdvertisementWindowModal(discord.ui.Modal, title="Commission info editor"):
    def __init__(self, interaction: discord.Interaction, handler, attachment: typing.Optional[discord.Attachment]=None):
        super().__init__()
        self.interaction = interaction
        self.handler = handler
        self._content_text = discord.ui.TextInput(label="Commission info", style=discord.TextStyle.paragraph, required=False)
        self._reference_text = discord.ui.TextInput(label="Reference image (URL) - optional", style=discord.TextStyle.short, required=False, default=str(attachment) if attachment else None, placeholder="https://...")
        self.add_item(self._content_text)
        self.add_item(self._reference_text)

    def auto_render(self):
        message = self._content_text.value
        if len(message) == 0:
            message = None
        reference = self._reference_text.value
        if len(reference) == 0:
            reference = None
        return self.render_embed(message=message, reference=reference)

    def render_embed(self, message: typing.Optional[str]=None, reference: typing.Optional[str]=None):
        embed = discord.Embed(
            colour=random.choice(bot_utils.EMBED_COLORS),
            timestamp=datetime.datetime.utcnow()
        )
        
        embed.set_footer(text=f'ID: {self.interaction.user.id}')
        
        try:
            icon_url = self.interaction.user.avatar.url
        except Exception as e:
            self.logger.warning(f"Exception while trying to handle icon thumbnail: {e}\n{traceback.format_exc()}")
            icon_url = None

        embed.set_author(name=f'{self.interaction.user}\'s commission info', icon_url=icon_url)

        if message:
            embed.add_field(name=f"Comm info", value=message, inline=False)

        if reference:
            embed.set_image(url=reference)

        return embed, message or reference
        
    async def on_submit(self, interaction: discord.Interaction) -> None:
        new_embed, is_valid = self.auto_render()
        if is_valid:
            success, explanation = await self.handler._finish_creating_advertisement(new_embed, self.interaction.user.id)
            await interaction.response.send_message(content=explanation, embed=new_embed if success else None, ephemeral=True)
        else:
            await interaction.response.send_message(content=f"Please input at least a text or a reference sheet~", ephemeral=True)

class advert_handler:
    def __init__(self, advertisement_slowmode: datetime.timedelta, ad_channel_id: int, sql: db.database, utils: bot_utils.utils):
        self.advertisement_slowmode = advertisement_slowmode
        self.ad_channel_id = ad_channel_id
        self.sql = sql
        self.utils = utils

        self.logger = botlogger.get_logger(__name__)

    def inject_ad_channel(self, ad_channel: discord.TextChannel):
        self.ad_channel = ad_channel
        
    async def try_remove_advertisement(self, user: int):
        ad_data = self.sql.get_existing_advertisement(user)
        if ad_data:
            message_id, _ = int(ad_data[0]), self.utils.db2datetime(ad_data[1])

            try:
                old_ad = await self.ad_channel.fetch_message(message_id)
                await old_ad.delete()
            except:
                pass
            return True
        return False

    async def create_advertisement(self, interaction: discord.Interaction, attachment: typing.Optional[discord.Attachment]=None):
        ad_data = self.sql.get_existing_advertisement(interaction.user.id)
        if ad_data:
            message_id, created_at = int(ad_data[0]), self.utils.db2datetime(ad_data[1])

            if (created_at + self.advertisement_slowmode) > datetime.datetime.now():
                return await self.utils.safe_send(interaction, content=f"You must wait a while before advertising your commissions again~", ephemeral=True)
        
        window = AdvertisementWindowModal(interaction, self, attachment=attachment)
        return await interaction.response.send_modal(window)

    async def _finish_creating_advertisement(self, embed: discord.Embed, user_id: int):
        try:
            new_ad = await self.ad_channel.send(embed=embed)
        except discord.errors.HTTPException:
            self.logger.debug("HTTPException in self.ad_channel.send (url is probably incorrect)")
            return False, f"Hmm that doesn't look like a valid URL, try again pls~"

        created_or_updated = "created"

        # Delete previous advertisement
        if await self.try_remove_advertisement(user_id):
            created_or_updated = "updated"

        self.sql.create_advertisement(user_id, new_ad.id)

        return True, f"I've {created_or_updated} your commission info in {self.ad_channel.mention}~"