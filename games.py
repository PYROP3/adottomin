import discord
import enum
import random
import typing

import botlogger
import bot_utils

logger = botlogger.get_logger(__name__)

async def _silent_reply(interaction: discord.Interaction):
    try:
        await interaction.response.send_message()
    except discord.errors.HTTPException:
        pass # Silently ignore

class RPSGameBase(discord.ui.View):
    def __init__(self, tag: str, interaction: discord.Interaction, opponent: discord.Member, rules: typing.Dict[enum.Enum, typing.Dict[enum.Enum, str]]):
        super().__init__()
        self.tag = tag
        self.interaction = interaction
        self.rules = rules

        self.creator = interaction.user
        self.opponent = opponent

        self.choices = {self.creator.id: None}
        if self.opponent:
            self.choices[self.opponent.id] = random.choice(list(rules)) if self.opponent.bot else None
            if self.opponent.bot:
                logger.debug(f"[{self.tag}] I chose {self.choices[self.opponent.id]}")
                
        self.buttons = [RPSButtonBase(opt, self) for opt in list(rules)]
        
        for button in self.buttons:
            self.add_item(button)

        # TODO spawn a thread? and wait for game timeout

    def _ch(self, choice: enum.Enum):
        return f"{choice.value} {choice.name}"

    def _message_choices(self, winning: enum.Enum, losing: enum.Enum):
        return f"{self._ch(winning)} {self.rules[winning][losing]} {self._ch(losing)}"

    def _message_game_end(self, winning_choice, losing_choice):
        _opponent = "I" if self.opponent.bot else self.opponent.mention
        _winner, _loser = (self.creator.mention, _opponent) if winning_choice == self.choices[self.creator.id] else (_opponent, self.creator.mention)
        _preamble = "" if self.opponent.bot else f"Hey {_loser}, "
        return f"{_preamble}{self._message_choices(winning_choice, losing_choice)}, so {_winner} win{'' if _winner == 'I' else 's'}!~"

    async def _handle_game_over(self):
        cr = self.choices[self.creator.id]
        op = self.choices[self.opponent.id]
        if op == cr:
            content = f"Both {self.creator.mention} and {self.opponent.mention} chose {self._ch(op)}, so it's a tie!~"

            styles = lambda choice: discord.enums.ButtonStyle.gray

        else:
            winning_choice, losing_choice = (cr, op) if op in self.rules[cr] else (op, cr)
            content = self._message_game_end(winning_choice, losing_choice)

            _styles = {winning_choice: discord.enums.ButtonStyle.green, losing_choice: discord.enums.ButtonStyle.red}
            styles = lambda choice: choice in _styles and _styles[choice] or discord.enums.ButtonStyle.gray

        for button in self.buttons:
            button.disabled = True
            button.style = styles(button.choice)

        await self.interaction.edit_original_response(content=content, view=self)

    async def _on_button_callback(self, choice: enum.Enum, interaction: discord.Interaction):
        if interaction.user.id not in self.choices and self.opponent:
            await interaction.response.send_message(content=f'You\'re not playing, silly~', ephemeral=True)
            return

        if not self.opponent and interaction.user.id != self.creator.id:
            logger.debug(f"setting new opponent as {interaction.user}")
            self.opponent = interaction.user

        if interaction.user.id in self.choices and self.choices[interaction.user.id]:
            await interaction.response.send_message(content=f'You already chose an option, silly~', ephemeral=True)
            return

        await _silent_reply(interaction)

        self.choices[interaction.user.id] = choice

        logger.debug(f"[RockPaperScissors] self.choices={self.choices}")
        if len(self.choices) > 1 and None not in [self.choices[k] for k in self.choices]: # Both chose
            await self._handle_game_over()

class RPSButtonBase(discord.ui.Button):
    def __init__(self, choice: enum.Enum, parent: RPSGameBase):
        super().__init__(label=choice.name, emoji=choice.value)
        self.parent = parent
        self.choice = choice

    async def callback(self, interaction: discord.Interaction):
        logger.debug(f"[RockPaperScissors] {interaction.user}({interaction.user.id}) clicked on {self.choice}")
        await self.parent._on_button_callback(self.choice, interaction)

class RockPaperScissors(RPSGameBase):
    class Options(enum.Enum):
        Rock='🪨'
        Paper='📝'
        Scissors='✂️'

    def __init__(self, interaction: discord.Interaction, opponent: discord.Member):
        super().__init__(
            "RockPaperScissors", 
            interaction, 
            opponent, 
            {
                RockPaperScissors.Options.Rock: {RockPaperScissors.Options.Scissors: "crushes"},
                RockPaperScissors.Options.Paper: {RockPaperScissors.Options.Rock: "covers"},
                RockPaperScissors.Options.Scissors: {RockPaperScissors.Options.Paper: "cuts"}
            })

class RockPaperScissorsLizardSpock(RPSGameBase):
    class Options(enum.Enum):
        Rock='🪨'
        Paper='📝'
        Scissors='✂️'
        Lizard='🦎'
        Spock='🖖'

    def __init__(self, interaction: discord.Interaction, opponent: discord.Member):
        super().__init__(
            "RockPaperScissorsLizardSpock", 
            interaction, 
            opponent, 
            {
                RockPaperScissorsLizardSpock.Options.Rock: {
                    RockPaperScissorsLizardSpock.Options.Scissors: "crushes",
                    RockPaperScissorsLizardSpock.Options.Lizard: "crushes"},
                RockPaperScissorsLizardSpock.Options.Paper: {
                    RockPaperScissorsLizardSpock.Options.Spock: "disproves",
                    RockPaperScissorsLizardSpock.Options.Rock: "covers"},
                RockPaperScissorsLizardSpock.Options.Scissors: {
                    RockPaperScissorsLizardSpock.Options.Lizard: "decapitates",
                    RockPaperScissorsLizardSpock.Options.Paper: "cuts"},
                RockPaperScissorsLizardSpock.Options.Lizard: {
                    RockPaperScissorsLizardSpock.Options.Paper: "eats",
                    RockPaperScissorsLizardSpock.Options.Spock: "poisons"},
                RockPaperScissorsLizardSpock.Options.Spock: {
                    RockPaperScissorsLizardSpock.Options.Rock: "vaporizes",
                    RockPaperScissorsLizardSpock.Options.Scissors: "smashes"}
            })

class RockPaperScissors25(RPSGameBase):
    class Options(enum.Enum):
        Gun='🔫'
        Dynamite='🧨'
        Nuke='☢️'
        Lightning='⚡'
        Devil='😈'
        Dragon='🐉'
        Alien='👽'
        Water='🌊'
        Bowl='🥣'
        Air='💨'
        Moon='🌙'
        Paper='📝'
        Sponge='🧽'
        Wolf='🐺'
        Cockroach='🪳'
        Tree='🌳'
        Man='👨'
        Woman='👩'
        Monkey='🐒'
        Snake='🐍'
        Axe='🪓'
        Scissors='✂️'
        Fire='🔥'
        Sun='☀️'
        Rock='🪨'

    def __init__(self, interaction: discord.Interaction, opponent: discord.Member):
        super().__init__(
            "RockPaperScissors25", 
            interaction, 
            opponent, 
            {
                RockPaperScissors25.Options.Gun: {
                    RockPaperScissors25.Options.Rock: "targets",
                    RockPaperScissors25.Options.Sun: "shoots at",
                    RockPaperScissors25.Options.Fire: "shoots",
                    RockPaperScissors25.Options.Scissors: "destroys",
                    RockPaperScissors25.Options.Axe: "chips",
                    RockPaperScissors25.Options.Snake: "shoots",
                    RockPaperScissors25.Options.Monkey: "shoots",
                    RockPaperScissors25.Options.Woman: "shoots",
                    RockPaperScissors25.Options.Man: "shoots",
                    RockPaperScissors25.Options.Tree: "targets",
                    RockPaperScissors25.Options.Cockroach: "shoots",
                    RockPaperScissors25.Options.Wolf: "shoots",
                },
                RockPaperScissors25.Options.Dynamite: {
                    RockPaperScissors25.Options.Gun: "outclasses",
                    RockPaperScissors25.Options.Rock: "explodes",
                    RockPaperScissors25.Options.Sun: "blots out",
                    RockPaperScissors25.Options.Fire: "starts",
                    RockPaperScissors25.Options.Scissors: "explodes",
                    RockPaperScissors25.Options.Axe: "explodes",
                    RockPaperScissors25.Options.Snake: "explodes",
                    RockPaperScissors25.Options.Monkey: "explodes",
                    RockPaperScissors25.Options.Woman: "explodes",
                    RockPaperScissors25.Options.Man: "explodes",
                    RockPaperScissors25.Options.Tree: "explodes",
                    RockPaperScissors25.Options.Cockroach: "explodes",
                },
                RockPaperScissors25.Options.Nuke: {
                    RockPaperScissors25.Options.Dynamite: "outclasses",
                    RockPaperScissors25.Options.Gun: "outclasses",
                    RockPaperScissors25.Options.Rock: "incinerates",
                    RockPaperScissors25.Options.Sun: "has power of",
                    RockPaperScissors25.Options.Fire: "starts massive",
                    RockPaperScissors25.Options.Scissors: "incinerates",
                    RockPaperScissors25.Options.Snake: "incinerates",
                    RockPaperScissors25.Options.Axe: "incinerates",
                    RockPaperScissors25.Options.Monkey: "incinerates",
                    RockPaperScissors25.Options.Woman: "incinerates",
                    RockPaperScissors25.Options.Man: "incinerates",
                    RockPaperScissors25.Options.Tree: "incinerates",
                },
                RockPaperScissors25.Options.Lightning: {
                    RockPaperScissors25.Options.Nuke: "defuses",
                    RockPaperScissors25.Options.Dynamite: "ignites",
                    RockPaperScissors25.Options.Gun: "melts",
                    RockPaperScissors25.Options.Rock: "splits",
                    RockPaperScissors25.Options.Sun: "storm blocks",
                    RockPaperScissors25.Options.Fire: "starts",
                    RockPaperScissors25.Options.Scissors: "melts",
                    RockPaperScissors25.Options.Axe: "melts",
                    RockPaperScissors25.Options.Snake: "strikes",
                    RockPaperScissors25.Options.Monkey: "strikes",
                    RockPaperScissors25.Options.Woman: "strikes",
                    RockPaperScissors25.Options.Man: "strikes",
                },
                RockPaperScissors25.Options.Devil: {
                    RockPaperScissors25.Options.Lightning: "casts",
                    RockPaperScissors25.Options.Nuke: "inspires",
                    RockPaperScissors25.Options.Dynamite: "inspires",
                    RockPaperScissors25.Options.Gun: "inspires",
                    RockPaperScissors25.Options.Rock: "hurls",
                    RockPaperScissors25.Options.Sun: "curses",
                    RockPaperScissors25.Options.Fire: "breathes",
                    RockPaperScissors25.Options.Scissors: "is immune to",
                    RockPaperScissors25.Options.Axe: "is immune to",
                    RockPaperScissors25.Options.Snake: "eats",
                    RockPaperScissors25.Options.Monkey: "enrages",
                    RockPaperScissors25.Options.Woman: "tempts",
                },
                RockPaperScissors25.Options.Dragon: {
                    RockPaperScissors25.Options.Devil: "commands",
                    RockPaperScissors25.Options.Lightning: "breathes",
                    RockPaperScissors25.Options.Nuke: "lived before",
                    RockPaperScissors25.Options.Dynamite: "flosses with",
                    RockPaperScissors25.Options.Gun: "is immune to",
                    RockPaperScissors25.Options.Rock: "rests upon",
                    RockPaperScissors25.Options.Sun: "blots out",
                    RockPaperScissors25.Options.Fire: "breathes",
                    RockPaperScissors25.Options.Scissors: "is immune to",
                    RockPaperScissors25.Options.Axe: "is immune to",
                    RockPaperScissors25.Options.Snake: "spawns",
                    RockPaperScissors25.Options.Monkey: "chars",
                },
                RockPaperScissors25.Options.Alien: {
                    RockPaperScissors25.Options.Dragon: "vaporizes",
                    RockPaperScissors25.Options.Devil: "does not believe in",
                    RockPaperScissors25.Options.Lightning: "shoots",
                    RockPaperScissors25.Options.Nuke: "defuses",
                    RockPaperScissors25.Options.Dynamite: "defuses",
                    RockPaperScissors25.Options.Gun: "force-fields",
                    RockPaperScissors25.Options.Rock: "vaporizes",
                    RockPaperScissors25.Options.Sun: "destroys",
                    RockPaperScissors25.Options.Fire: "fuses",
                    RockPaperScissors25.Options.Scissors: "force-fields",
                    RockPaperScissors25.Options.Axe: "force-fields",
                    RockPaperScissors25.Options.Snake: "mutates",
                },
                RockPaperScissors25.Options.Water: {
                    RockPaperScissors25.Options.Alien: "is toxic to",
                    RockPaperScissors25.Options.Dragon: "drowns",
                    RockPaperScissors25.Options.Devil: "blesses",
                    RockPaperScissors25.Options.Lightning: "conducts",
                    RockPaperScissors25.Options.Nuke: "short-circuits",
                    RockPaperScissors25.Options.Dynamite: "douses",
                    RockPaperScissors25.Options.Gun: "rusts",
                    RockPaperScissors25.Options.Rock: "erodes",
                    RockPaperScissors25.Options.Sun: "reflects",
                    RockPaperScissors25.Options.Fire: "puts out",
                    RockPaperScissors25.Options.Scissors: "rusts",
                    RockPaperScissors25.Options.Axe: "rusts",
                },
                RockPaperScissors25.Options.Bowl: {
                    RockPaperScissors25.Options.Water: "contains",
                    RockPaperScissors25.Options.Alien: "is shaped like ship of",
                    RockPaperScissors25.Options.Dragon: "drowns",
                    RockPaperScissors25.Options.Devil: "blesses",
                    RockPaperScissors25.Options.Lightning: "focuses",
                    RockPaperScissors25.Options.Nuke: "encases core of",
                    RockPaperScissors25.Options.Dynamite: "splashes",
                    RockPaperScissors25.Options.Gun: "splashes",
                    RockPaperScissors25.Options.Rock: "is made of",
                    RockPaperScissors25.Options.Sun: "focuses",
                    RockPaperScissors25.Options.Fire: "snuffs out",
                    RockPaperScissors25.Options.Scissors: "covers",
                },
                RockPaperScissors25.Options.Air: {
                    RockPaperScissors25.Options.Bowl: "tips over",
                    RockPaperScissors25.Options.Water: "evaporates",
                    RockPaperScissors25.Options.Alien: "chokes",
                    RockPaperScissors25.Options.Dragon: "freezes",
                    RockPaperScissors25.Options.Devil: "chokes",
                    RockPaperScissors25.Options.Lightning: "creates",
                    RockPaperScissors25.Options.Nuke: "blows away",
                    RockPaperScissors25.Options.Dynamite: "blows out",
                    RockPaperScissors25.Options.Gun: "tarnishes",
                    RockPaperScissors25.Options.Rock: "erodes",
                    RockPaperScissors25.Options.Sun: "cools heat from",
                    RockPaperScissors25.Options.Fire: "blows out",
                },
                RockPaperScissors25.Options.Moon: {
                    RockPaperScissors25.Options.Air: "has no",
                    RockPaperScissors25.Options.Bowl: "is shaped like",
                    RockPaperScissors25.Options.Water: "has no",
                    RockPaperScissors25.Options.Alien: "houses",
                    RockPaperScissors25.Options.Dragon: "shines on",
                    RockPaperScissors25.Options.Devil: "terrifies",
                    RockPaperScissors25.Options.Lightning: "can't be reached by",
                    RockPaperScissors25.Options.Nuke: "can't be reached by",
                    RockPaperScissors25.Options.Dynamite: "suffocates",
                    RockPaperScissors25.Options.Gun: "inspires duel with",
                    RockPaperScissors25.Options.Rock: "shines on",
                    RockPaperScissors25.Options.Sun: "eclipses",
                },
                RockPaperScissors25.Options.Paper: {
                    RockPaperScissors25.Options.Moon: "blocks out",
                    RockPaperScissors25.Options.Air: "fans",
                    RockPaperScissors25.Options.Bowl: "covers",
                    RockPaperScissors25.Options.Water: "floats on",
                    RockPaperScissors25.Options.Alien: "disproves",
                    RockPaperScissors25.Options.Dragon: "rebukes",
                    RockPaperScissors25.Options.Devil: "rebukes",
                    RockPaperScissors25.Options.Lightning: "defines",
                    RockPaperScissors25.Options.Nuke: "defines",
                    RockPaperScissors25.Options.Dynamite: "encases",
                    RockPaperScissors25.Options.Gun: "outlaws",
                    RockPaperScissors25.Options.Rock: "covers",
                },
                RockPaperScissors25.Options.Sponge: {
                    RockPaperScissors25.Options.Paper: "soaks",
                    RockPaperScissors25.Options.Moon: "looks like",
                    RockPaperScissors25.Options.Air: "contains",
                    RockPaperScissors25.Options.Bowl: "cleans",
                    RockPaperScissors25.Options.Water: "absorbs",
                    RockPaperScissors25.Options.Alien: "intrigues",
                    RockPaperScissors25.Options.Dragon: "cleanses",
                    RockPaperScissors25.Options.Devil: "cleanses",
                    RockPaperScissors25.Options.Lightning: "conducts",
                    RockPaperScissors25.Options.Nuke: "cleans",
                    RockPaperScissors25.Options.Dynamite: "soaks",
                    RockPaperScissors25.Options.Gun: "cleans",
                },
                RockPaperScissors25.Options.Wolf: {
                    RockPaperScissors25.Options.Sponge: "chews up",
                    RockPaperScissors25.Options.Paper: "chews up",
                    RockPaperScissors25.Options.Moon: "howls at",
                    RockPaperScissors25.Options.Air: "breathes",
                    RockPaperScissors25.Options.Bowl: "drinks from",
                    RockPaperScissors25.Options.Water: "drinks",
                    RockPaperScissors25.Options.Alien: "chases",
                    RockPaperScissors25.Options.Dragon: "outruns",
                    RockPaperScissors25.Options.Devil: "chases",
                    RockPaperScissors25.Options.Lightning: "outruns",
                    RockPaperScissors25.Options.Nuke: "launches",
                    RockPaperScissors25.Options.Dynamite: "outruns",
                },
                RockPaperScissors25.Options.Cockroach: {
                    RockPaperScissors25.Options.Wolf: "sleeps in fur of",
                    RockPaperScissors25.Options.Sponge: "nests in",
                    RockPaperScissors25.Options.Paper: "nests in",
                    RockPaperScissors25.Options.Monkey: "comes out with",
                    RockPaperScissors25.Options.Air: "breathes",
                    RockPaperScissors25.Options.Bowl: "hides under",
                    RockPaperScissors25.Options.Water: "drinks",
                    RockPaperScissors25.Options.Alien: "stows away with",
                    RockPaperScissors25.Options.Dragon: "eats eggs of",
                    RockPaperScissors25.Options.Man: "scares",
                    RockPaperScissors25.Options.Lightning: "hides from",
                    RockPaperScissors25.Options.Nuke: "survives",
                },
                RockPaperScissors25.Options.Tree: {
                    RockPaperScissors25.Options.Cockroach: "shelters",
                    RockPaperScissors25.Options.Wolf: "shelters",
                    RockPaperScissors25.Options.Sponge: "outlives",
                    RockPaperScissors25.Options.Paper: "creates",
                    RockPaperScissors25.Options.Monkey: "blocks",
                    RockPaperScissors25.Options.Air: "produces",
                    RockPaperScissors25.Options.Bowl: "wood creates",
                    RockPaperScissors25.Options.Water: "absorbs",
                    RockPaperScissors25.Options.Alien: "ensnares ship of",
                    RockPaperScissors25.Options.Dragon: "shelters",
                    RockPaperScissors25.Options.Devil: "imprisons",
                    RockPaperScissors25.Options.Lightning: "attracts",
                },
                RockPaperScissors25.Options.Man: {
                    RockPaperScissors25.Options.Tree: "plants",
                    RockPaperScissors25.Options.Cockroach: "steps on",
                    RockPaperScissors25.Options.Wolf: "tames",
                    RockPaperScissors25.Options.Sponge: "cleans with",
                    RockPaperScissors25.Options.Paper: "writes",
                    RockPaperScissors25.Options.Monkey: "travels to",
                    RockPaperScissors25.Options.Air: "breathes",
                    RockPaperScissors25.Options.Bowl: "eats from",
                    RockPaperScissors25.Options.Water: "drinks",
                    RockPaperScissors25.Options.Alien: "disproves",
                    RockPaperScissors25.Options.Dragon: "slays",
                    RockPaperScissors25.Options.Devil: "exorcises",
                },
                RockPaperScissors25.Options.Woman: {
                    RockPaperScissors25.Options.Man: "tempts",
                    RockPaperScissors25.Options.Tree: "plants",
                    RockPaperScissors25.Options.Cockroach: "steps on",
                    RockPaperScissors25.Options.Wolf: "tames",
                    RockPaperScissors25.Options.Sponge: "cleans with",
                    RockPaperScissors25.Options.Paper: "writes",
                    RockPaperScissors25.Options.Moon: "aligns with",
                    RockPaperScissors25.Options.Air: "breathes",
                    RockPaperScissors25.Options.Bowl: "eats from",
                    RockPaperScissors25.Options.Water: "drinks",
                    RockPaperScissors25.Options.Alien: "disproves",
                    RockPaperScissors25.Options.Dragon: "subdues",
                },
                RockPaperScissors25.Options.Monkey: {
                    RockPaperScissors25.Options.Woman: "throws poop at",
                    RockPaperScissors25.Options.Man: "throws poop at",
                    RockPaperScissors25.Options.Tree: "lives in",
                    RockPaperScissors25.Options.Cockroach: "eats",
                    RockPaperScissors25.Options.Wolf: "enrages",
                    RockPaperScissors25.Options.Sponge: "rips up",
                    RockPaperScissors25.Options.Paper: "rips up",
                    RockPaperScissors25.Options.Moon: "screeches at",
                    RockPaperScissors25.Options.Air: "breathes",
                    RockPaperScissors25.Options.Bowl: "smashes",
                    RockPaperScissors25.Options.Water: "drinks",
                    RockPaperScissors25.Options.Alien: "infuriates",
                },
                RockPaperScissors25.Options.Snake: {
                    RockPaperScissors25.Options.Monkey: "bites",
                    RockPaperScissors25.Options.Woman: "bites",
                    RockPaperScissors25.Options.Man: "bites",
                    RockPaperScissors25.Options.Tree: "lives in",
                    RockPaperScissors25.Options.Cockroach: "eats",
                    RockPaperScissors25.Options.Wolf: "bites",
                    RockPaperScissors25.Options.Sponge: "swallows",
                    RockPaperScissors25.Options.Paper: "nests in",
                    RockPaperScissors25.Options.Moon: "comes out with",
                    RockPaperScissors25.Options.Air: "breathes",
                    RockPaperScissors25.Options.Bowl: "sleeps in",
                    RockPaperScissors25.Options.Water: "drinks",
                },
                RockPaperScissors25.Options.Axe: {
                    RockPaperScissors25.Options.Snake: "chops",
                    RockPaperScissors25.Options.Monkey: "cleaves",
                    RockPaperScissors25.Options.Woman: "cleaves",
                    RockPaperScissors25.Options.Man: "cleaves",
                    RockPaperScissors25.Options.Tree: "chops down",
                    RockPaperScissors25.Options.Cockroach: "chops",
                    RockPaperScissors25.Options.Woman: "cleaves",
                    RockPaperScissors25.Options.Sponge: "chops",
                    RockPaperScissors25.Options.Paper: "slices",
                    RockPaperScissors25.Options.Moon: "reflects",
                    RockPaperScissors25.Options.Air: "flies through",
                    RockPaperScissors25.Options.Bowl: "chops",
                },
                RockPaperScissors25.Options.Scissors: {
                    RockPaperScissors25.Options.Axe: "are sharper than",
                    RockPaperScissors25.Options.Snake: "stab",
                    RockPaperScissors25.Options.Monkey: "stab",
                    RockPaperScissors25.Options.Woman: "cut hair of",
                    RockPaperScissors25.Options.Man: "cut hair of",
                    RockPaperScissors25.Options.Tree: "carve",
                    RockPaperScissors25.Options.Cockroach: "stab",
                    RockPaperScissors25.Options.Wolf: "trims",
                    RockPaperScissors25.Options.Sponge: "cut up",
                    RockPaperScissors25.Options.Paper: "cut",
                    RockPaperScissors25.Options.Moon: "reflect",
                    RockPaperScissors25.Options.Air: "fly through",
                },
                RockPaperScissors25.Options.Fire: {
                    RockPaperScissors25.Options.Scissors: "melts",
                    RockPaperScissors25.Options.Axe: "forges",
                    RockPaperScissors25.Options.Snake: "burns",
                    RockPaperScissors25.Options.Monkey: "burns",
                    RockPaperScissors25.Options.Woman: "burns",
                    RockPaperScissors25.Options.Man: "burns",
                    RockPaperScissors25.Options.Tree: "burns down",
                    RockPaperScissors25.Options.Cockroach: "burns",
                    RockPaperScissors25.Options.Wolf: "burns",
                    RockPaperScissors25.Options.Sponge: "burns",
                    RockPaperScissors25.Options.Paper: "burns",
                    RockPaperScissors25.Options.Moon: "inspires camping with",
                },
                RockPaperScissors25.Options.Sun: {
                    RockPaperScissors25.Options.Fire: "made of",
                    RockPaperScissors25.Options.Scissors: "melts",
                    RockPaperScissors25.Options.Axe: "melts",
                    RockPaperScissors25.Options.Snake: "warms",
                    RockPaperScissors25.Options.Monkey: "warms",
                    RockPaperScissors25.Options.Woman: "warms",
                    RockPaperScissors25.Options.Man: "warms",
                    RockPaperScissors25.Options.Tree: "provides energy to",
                    RockPaperScissors25.Options.Cockroach: "warms",
                    RockPaperScissors25.Options.Wolf: "warms",
                    RockPaperScissors25.Options.Sponge: "dries up",
                    RockPaperScissors25.Options.Paper: "shines through",
                },
                RockPaperScissors25.Options.Rock: {
                    RockPaperScissors25.Options.Sun: "shades",
                    RockPaperScissors25.Options.Fire: "pounds out",
                    RockPaperScissors25.Options.Scissors: "smashes",
                    RockPaperScissors25.Options.Axe: "chips",
                    RockPaperScissors25.Options.Snake: "crushes",
                    RockPaperScissors25.Options.Monkey: "crushes",
                    RockPaperScissors25.Options.Woman: "crushes",
                    RockPaperScissors25.Options.Man: "crushes",
                    RockPaperScissors25.Options.Tree: "blocks",
                    RockPaperScissors25.Options.Cockroach: "squishes",
                    RockPaperScissors25.Options.Wolf: "crushes",
                    RockPaperScissors25.Options.Sponge: "crushes",
                }
            })

@discord.app_commands.guild_only()
class Game(discord.app_commands.Group):
    def __init__(self, utils: bot_utils.utils, bot):
        super().__init__()
        self.utils = utils
        self.bot = bot

    def _validate_rps(self, interaction: discord.Interaction, user: typing.Optional[discord.Member]):
        if user and user.id == interaction.user.id:
            return f"Try choosing someone other than yourself, silly~", False

        if user and user.bot and user.id != self.bot.user.id:
            return f"I'm the only bot who will play against you, silly~", False

        if user and user.id == self.bot.user.id:
            return f'Okay {interaction.user.mention}! Pick your choice carefully~', True
        
        if user:
            return f'Hey {user.mention}! {interaction.user.mention} is challenging you to a round of Rock Paper Scissors~', True
    
        return f'Hey everyone! {interaction.user.mention} wants to play a game, first come first serve~', True

    @discord.app_commands.command(description='Play rock/paper/scissors')
    @discord.app_commands.describe(user='Who you wanna play against (leave it empty to play against the first person to answer, or put me to play against me)')
    async def rps(self, interaction: discord.Interaction, user: typing.Optional[discord.Member]):
        logger.info(f"{interaction.user} requested RPS against {user}")

        content, valid = self._validate_rps(interaction, user)

        await self.utils.safe_send(interaction, 
            content=content, 
            view=RockPaperScissors(interaction, user) if valid else None,
            ephemeral=not valid)

    @discord.app_commands.command(description='Play rock/paper/scissors/lizard/spock')
    @discord.app_commands.describe(user='Who you wanna play against (leave it empty to play against the first person to answer, or put me to play against me)')
    async def rpsls(self, interaction: discord.Interaction, user: typing.Optional[discord.Member]):
        logger.info(f"{interaction.user} requested RPSLS against {user}")

        content, valid = self._validate_rps(interaction, user)

        await self.utils.safe_send(interaction, 
            content=content, 
            view=RockPaperScissorsLizardSpock(interaction, user) if valid else None,
            ephemeral=not valid)

    @discord.app_commands.command(description='Play rock/paper/scissors with 25 weapons')
    @discord.app_commands.describe(user='Who you wanna play against (leave it empty to play against the first person to answer, or put me to play against me)')
    async def rps25(self, interaction: discord.Interaction, user: typing.Optional[discord.Member]):
        logger.info(f"{interaction.user} requested RPS25 against {user}")

        content, valid = self._validate_rps(interaction, user)

        await self.utils.safe_send(interaction, 
            content=content, 
            view=RockPaperScissors25(interaction, user) if valid else None,
            ephemeral=not valid)
