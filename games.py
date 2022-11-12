import discord
import enum
import random
import typing

import botlogger
import bot_utils

logger = botlogger.get_logger(__name__)

class RockPaperScissorsOptions(enum.Enum):
    Rock=('🪨', 0)
    Paper=('📝', 1)
    Scissors=('✂️', 2)

class RockPaperScissors(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, opponent: discord.Member):
        super().__init__()
        self.interaction = interaction

        self.creator = interaction.user
        self.opponent = opponent

        self.choices = {self.creator.id: None}
        if self.opponent:
            self.choices[self.opponent.id] = random.choice(list(RockPaperScissorsOptions)) if self.opponent.bot else None
            if self.opponent.bot:
                logger.debug(f"[RockPaperScissors] I chose {self.choices[self.opponent.id]}")

        # logger.debug(f"[RockPaperScissors] self.choices={self.choices}")

        self.buttons = [
            RockPaperScissorsButton(RockPaperScissorsOptions.Rock, self),
            RockPaperScissorsButton(RockPaperScissorsOptions.Paper, self),
            RockPaperScissorsButton(RockPaperScissorsOptions.Scissors, self)]
        
        for button in self.buttons:
            self.add_item(button)

    def _ch(self, choice: RockPaperScissorsOptions):
        return f"{choice.value[0]} {choice.name}"

    def _message_game_end(self):
        cr = self.choices[self.creator.id]
        op = self.choices[self.opponent.id]
        # logger.debug(f"[RockPaperScissors] self.choices={self.choices}")
        # logger.debug(f"[RockPaperScissors] cr={cr} ({self.creator.id})")
        # logger.debug(f"[RockPaperScissors] op={op} ({self.opponent.id})")
        if op == cr:
            return f"Both players chose {self._ch(op)}, so it's a tie!~"
        _opponent = "I" if self.opponent.bot else self.opponent.mention
        _winner = self.creator.mention if (op.value[1] + 1) % 3 == cr.value[1] else _opponent
        return f"{self.creator.mention} chose {self._ch(cr)} and {_opponent} chose {self._ch(op)}, so {_winner} win{'' if _winner == 'I' else 's'}!~"

    async def _handle_game_over(self):
        for button in self.buttons:
            button.disabled = True

        await self.interaction.edit_original_response(content=self._message_game_end(), view=self)

    async def _on_button_callback(self, choice: RockPaperScissorsOptions, interaction: discord.Interaction):
        if interaction.user.id not in self.choices and self.opponent:
            await interaction.response.send_message(content=f'You\'re not playing, silly~', ephemeral=True)
            return

        if not self.opponent:
            self.opponent = interaction.user

        if self.choices[interaction.user.id]:
            await interaction.response.send_message(content=f'You already chose an option, silly~', ephemeral=True)
            return

        await interaction.response.send_message(content=f'Got it~', ephemeral=True)

        self.choices[interaction.user.id] = choice

        # logger.debug(f"[RockPaperScissors] self.choices={self.choices}")
        if None not in [self.choices[k] for k in self.choices]: # Both chose
            #await interaction.response.send_message(content=f'{self.creator.mention} chose {self.choices[self.creator.id]}\n{self.opponent.mention} chose {self.choices[self.opponent.id]}')
            await self._handle_game_over()

class RockPaperScissorsButton(discord.ui.Button):
    def __init__(self, choice: RockPaperScissorsOptions, parent: RockPaperScissors):
        super().__init__(label=choice.name, emoji=choice.value[0])
        self.parent = parent
        self.choice = choice

    async def callback(self, interaction: discord.Interaction):
        logger.debug(f"[RockPaperScissors] {interaction.user}({interaction.user.id}) clicked on {self.choice}")
        await self.parent._on_button_callback(self.choice, interaction)

@discord.app_commands.guild_only()
class Game(discord.app_commands.Group):
    def __init__(self, utils: bot_utils.utils, bot):
        super().__init__()
        self.utils = utils
        self.bot = bot

    @discord.app_commands.command(description='Rock paper scissors')
    @discord.app_commands.describe(user='Who you wanna play against (leave it empty to play against the first person to answer, or put me to play against me)')
    async def rps(self, interaction: discord.Interaction, user: typing.Optional[discord.Member]):
        logger.info(f"{interaction.user} requested RPS against {user}")

        if user and user.id == interaction.user.id:
            await self.utils.safe_send(interaction, content=f"Try choosing someone other than yourself, silly~", ephemeral=True)
            return

        if user and user.bot and user.id != self.bot.user.id:
            await self.utils.safe_send(interaction, content=f"I'm the only robot who will play against you, silly~", ephemeral=True)
            return

        if user and user.id == self.bot.user.id:
            content = f'Okay {interaction.user.mention}! Pick your choice carefully~'
        elif user:
            content = f'Hey {user.mention}! {interaction.user.mention} is challenging you to a round of Rock Paper Scissors~'
        else:
            content = f'Hey everyone! {interaction.user.mention} wants to play a game, first come first serve~'

        await self.utils.safe_send(interaction, 
            content=content, 
            view=RockPaperScissors(interaction, user))
