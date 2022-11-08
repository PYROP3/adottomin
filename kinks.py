import botlogger
import db
import discord
import enum
import logging
import bot_utils
import typing
import datetime
import random
import traceback

logger = botlogger.get_logger(__name__)

kinklist = {
    'Bodies': {
        'Skinny': 'Expresses an interest in characters that are waifish, thin, or slender.', 
        'Chubby': 'Expresses an interest in characters that are well-rounded, full in form, and pudgy.', 
        'Small breasts': 'Expresses an interest in breasts that are particularly small, sometimes to the point of appearing absent.', 
        'Large breasts': 'Expresses an interest in breasts that are particularly large.', 
        'Small cocks': 'Expresses an interest in cocks that are below average size.', 
        'Large cocks': 'Expresses an interest in cocks taht are above average size.'
    }, 
    'Clothing': {
        'Clothed sex': 'Engaging in an RP where you and/or your partner are not undressed during sexual interaction.', 
        'Lingerie': 'Expresses an interest in the inclusion of lingerie in the sexual context of an RP, or an interest in characters wearing such.', 
        'Stockings': 'Expresses an interest in the inclusion of stockings in the sexual context of an RP, or an interest in characters wearing such.', 
        'Heels': 'Expresses an interest in the inclusion of high heeled shoes in the sexual context of an RP, or an interest in characters wearing such.', 
        'Leather': 'Expresses an interest in the inclusion of leather clothing in the sexual context of an RP, or an interest in characters wearing such.', 
        'Latex': 'The usage of latex and/or rubber material worn as clothing', 
        'Uniform / costume': 'Expresses an interest in the inclusion of uniforms or costumes in the sexual context of an RP, or an interest in characters wearing such.', 
        'Cross-dressing': 'Engaging in an RP where one or more characters dress in the clothes of the gender opposite to their own.'
    }, 
    'Groupings': {
        'You and 1 male': None, 
        'You and 1 female': None, 
        'You and MtF trans': None, 
        'You and FtM trans': None, 
        'You and 1 male, 1 female': None, 
        'You and 2 males': None, 
        'You and 2 females': None, 
        'Orgy': 'multiple male and female characters'
    }, 
    'General': {
        'Romance / Affection': 'Displaying or expressing love or strong affection, passion, either during love making or during normal scenes.', 
        'Handjob / Fingering': 'Sexual stimulation by direct, physical contact of the hands or fingers to the genitals.', 
        'Blowjob': 'Sexual stimulation by direct, physical contact of the mouth or tongue to male genitals', 
        'Deep throat': 'The act of penetrating the mouth of another character to the depths at which the penis or insertion enters the back of the mouth cavity and/or throat, sometimes causing a gag reflex, or being the recipient of such actions.', 
        'Swallowing': 'The act of orally consuming semen, either directly or indirectly from a penis.', 
        'Facials': "The act of cumming directly onto one's face", 
        'Cunnilingus': 'Sexual stimulation by direct, physical contact of the mouth or tongue to female genitals', 
        'Face-sitting': "A sexual practice where someone sits on another character's face with their buttocks or genitals, causing the person to be smothered, sometimes to the point asphyxiation; often done as form of forcing oral gratification.", 
        'Edging': 'Keeping on the edge of climax without orgasm', 
        'Teasing': "Refers to extended scenes of foreplay prior to explicit, sexual intercourse, which may be physical and/or verbal, typically to arouse one's partner to the point of sexual frustration or desperation."
    }, 
    'Ass play': {
        'Anal toys': 'Refers to the inclusion of anal penetration with sex toys, including but not limited to dildos, vibrators, anal eggs, anal beads, etc.', 
        'Anal sex/pegging': 'Being penetrated by a partner, with a penis or strap-on', 
        'Rimming': "The act of giving oral stimulation to a partner's anus, by the means of licking and/or penetrating the recipient's anus with the tongue.", 
        'Double penetration': "The act of penetrating a single character's anus with two objects, including but not limited to the penis, sex toys, fist etc., or receiving such.", 
        'Anal fisting': "The act of inserting one's hand(s) and/or arm(s) into one's partner's anus, or being the recipient of such acts."
    }, 
    'Restrictive': {
        'Gag': "The act of placing and lodging an object in another character's mouth to force him or her to breathe through his or her nose, as well as creating the inability to speak, or receiving such actions.", 
        'Collar': 'Wearing a collar around the neck', 
        'Leash': 'Being lead around on a leash', 
        'Chastity': 'Sexual abstinence, either willing or forced; this can include someone simply abstaining from sexual activity, or the wearing of a device that prevents it.', 
        'Bondage (Light)': 'The use of bondage that is mild or moderate in either the position in which it causes the bound character to be in, the duration for which the character will be in bondage, the level of discomfort caused by the bondage or the amount of immobilization that will occur due to the bondage.', 
        'Bondage (Heavy)': 'The use of bondage that is extreme in either the position in which it causes the bound character to be in, the duration for which the character will be in bondage, the level of discomfort caused by the bondage or the amount of immobilization that will occur due to the bondage.', 
        'Encasement': "one's whole body being wrapped up like a mummy in a latex suit, sleepsack, or other fetish gear for the purposes of sexual gratification."
    }, 
    'Toys': {
        'Dildos': 'an object shaped like an erect penis used for sexual stimulation.', 
        'Plugs': 'a sex toy of a type designed to be inserted into the rectum.', 
        'Vibrators': 'a vibrating device used for sexual stimulation.', 
        'Sounding': "The act of inserting metal rods into a male or female's urethra, or receiving such actions; technically implies rods that resonate and/or vibrate in response to a form of stimulation, but does not necessarily mean so."
    }, 
    'Domination': {
        'General Dom / General Sub': 'Catchall for Dominant/Submissive Activities.', 
        'Domestic servitude': 'Being served by a butler, waitress, chauffeur, maid or housekeeper, or serving as one.', 
        'Slavery': "Serving as the dominant's beck and call, or recieving such service, without choice.", 
        'Pet play': 'Petplay is a in role in which the focus is on the sub entering the altered mind space of a different species, often a dog, cat, or horse.', 
        'DD/lg, MD/lb': 'Daddy or Mommy Dom/ Littly Girl or Boy. The daddy/mommy is the more dominant half of the relationship, the little is the more submissive.', 
        'Discipline': 'The use of reinforcement (rewards and/or punishments) in order to train a submissive to obey the various commands of a master.', 
        'Begging': 'The self-abasing act of pleading, as a form of submission, being incorporated into an RP.', 
        'Forced orgasm': 'A forced orgasm is consensual BDSM or kinky sexual play whereby a person consents to be forced to orgasm in a way that is beyond their control.', 
        'Orgasm control': 'Refers to the dominant being in control of when the submissive achieves orgasm, either by physical means or by command; typically involves domination and/or excessive teasing and edging; orgasm may be completely denied.', 
        'Orgasm denial': 'Refers to the dominant denying the submissive orgasm.', 
        'Power exchange': 'A relationship with service at the core.'
    }, 
    'No consent': {
        'Non-con / rape': "taking/being taken against one's will, often through force", 
        'Blackmail / coercion': 'Refers to the inclusion of Coercion and/or Blackmail in the context of the story arc of an RP, often in the form of a semi-consensual means of receiving sex from a partner.', 
        'Kidnapping': 'The act of abducting a character in an RP for the purpose of abusing, often sexually, or being abducted for such reasons; often implies indefinite imprisonment.', 
        'Drugs': 'The use of illicit drugs in the context of an RP, typically to disorientate or otherwise mentally incapacitate a character, or to elevate the sensations of sex.', 
        'Alcohol': 'The use of alcohol in the context of an RP, typically to disorientate or otherwise mentally incapacitate a character, or to elevate the sensations of sex.', 
        'Sleep play': 'Engaging in sexual acts with an unconscious/asleep partner'
    }, 
    'Taboo': {
        'Incest': 'Engaging in an RP in which at least two characters will be related', 
        'Age Gap': 'Refers to scenes in which there is a signifigant gap in the ages of characters.', 
        'Interracial': 'Scenes based on interracial interactions without relying on racial stereotypes.', 
        'Raceplay': 'Scenes based on racial stereotypes or racism, including scenes set in racist settings.', 
        'Bestiality': 'Refers to a sapient character engaging in a sexual act with a non-sapient animal, or playing a non-sapient animal in an RP and being engaged by a sapient character.', 
        'Necrophilia': 'The act of having sex with a dead, or otherwise unconscious or inanimate, character that was once alive, or, theoretically, receiving such actions.', 
        'Cheating': 'Where one or both partners are being unfaithful to significant others.', 
        'Exhibitionism': 'Engaging in an RP in which the setting is of a public nature; typically used in conjunction with exhibitionism and/or humiliation.', 
        'Voyeurism': "Refers to the derivation of sexual stimulation from either/or the action of watching, typically in secret, a person (or people) reveal themselves or do something otherwise explicit, or the act of revealing one's self and/or doing something otherwise explicit with the intent to be viewed."
    }, 
    'Surrealism': {
        'Futanari/Futa': 'characters who have an overall feminine body, but have both female and male genitalia (although testicles are not always present)', 
        'Furry': 'Anthropomorphic animal characters.', 
        'Vore': 'The act of physically consuming another character', 
        'Transformation': "The act of causing the physical characteristics of a participant of an RP, possibly including one's self, by magical or chemical means, to change in a dramatic fashion; may refer to a myriad of different types of transformations, and connotates receiving sexual pleasure from the act of transformation itself.", 
        'Tentacles': 'Engaging in an RP in which self-sentient tentacles or tentacle-like appendages will penetrate a character; often implies multiple penetration.', 
        'Monster or Alien': 'Various types of monsters, Extraterrestrials, and aesthetically challenging characters.', 
        'Ghost': 'The formerly living, not currently in posession of a body'
    }, 
    'Fluids': {
        'Blood': 'Pertains to the inclusion of blood or the retrieval of blood in any form in a sexual context, or engaging in acts which will draw blood.', 
        'Watersports': 'Pertains to the inclusion of urine, or the expelling of urine, in any form, in the sexual context of an RP.', 
        'Scat': 'Pertains to the inclusion of fecal matter or the expelling of fecal matter in any form in the sexual context of an RP.', 
        'Lactation': "The act of producing milk from one's breasts, or engaging in sex with a character that produces milk from one's breasts, typically in response to sexual stimulation, and any play that will emanate thereof.", 
        'Diapers': 'A situation in which at least one character will wear a diaper; typically implies that the diaper will be soiled with urine and/or fecal matter, usually in conjunction with age play or infantilism, but sometimes in conjunction with humiliation.', 
        'Cum play': 'Any number of situations focused on playing with cum.'
    }, 
    'Degradation': {
        'Glory hole': 'Servicing a partner or recieving service from a partner with a physical barrier between the participants', 
        'Name calling': 'Engaging in an RP in which one character will be called names, in an attempt to elicit either a response of sexual gratification from the emotions correlating to humiliation, or merely as a form of psychological domination or punishment.', 
        'Humiliation': 'Engaging in an RP in which one character will be embarrassed, typically extremely and/or frequently, in an attempt to elicit either a response of sexual gratification from the emotions correlating to humiliation, or merely as a form of psychological domination or punishment; typically a more intense form of degradation.'
    }, 
    'Touch & Stimulation': {
        'Cock/Pussy worship': "Gratuitous acknowledgment of one's partner's genitalia, either verbal and/or physical, or receiving such actions; typically implies oral stimulation.", 
        'Ass worship': "Gratuitous acknowledgment of one's partner's ass, either verbal and/or physical, or receiving such actions; typically implies oral stimulation.", 
        'Foot play': 'The act of incorporating the feet or feet paws into the sexual context of an RP, including but not limited to the worshiping of feet, receiving sexual gratification from the sight or smell of feet and/or humping feet, sometimes to the point of orgasm.', 
        'Tickling': 'The act of tickling and/or being tickled in a sexual context of an RP; or, receiving sexual stimulation from such.', 
        'Sensation play': "Sensation play describes a wide variety of activities, both vanilla and kinky, that use the body's senses as a way to arouse and provide stimulation to a partner. Although sensation play is often related to skin sensations, it doesn't have to be so limited. Sight, taste, and hearing can also be included in sensation play.", 
        'Electro stimulation': 'The use of sex toys that carry an electrical current; sometimes painful.'
    }, 
    'Misc. Fetish': {
        'Fisting': "The act of placing one's hand(s) and/or arm(s) into a vagina, or receiving such actions.", 
        'Gangbang': 'When multiple partners, usually 3 or more, engage in sexual intercourse with a single willing partner.', 
        'Breath play': 'A situation in which at least one character will have physical control over the breathing habits of another character, often by either intermittent choking and/or due to the penetration of the throat.', 
        'Impregnation': 'Impregnating a character', 
        'Pregnancy': 'Fetishizing a pregnant character', 
        'Feminization': 'Feminization is a type of role play that involves imposing traditionally female attributes onto a submissive male partner. It may also involve an adoption of traditionally feminine behaviors and mannerisms.', 
        'Cuckold / Cuckquean': 'Refers to the act of a character who, within the confines of the RP world has been designated to be in a relationship, will have sexual interaction with a character other than the one who has been predetermined to be in a relationship, in the context of the RP.'
    }, 
    'Pain': {
        'Light pain': 'Refers to the inclusion of light physical pain due to acts which are directly sexual.', 
        'Heavy pain': 'Refers to the inclusion of heavy physical pain due to acts which are directly sexual; typically rough or excessive penetrations. This is probably gonna leave a mark.', 
        'Nipple clamps': 'pressure device applied to nipples to create pain which produces pleasure.', 
        'Clothes pins': 'Pinching sking between the forks of a clothes pin', 
        'Caning': 'Caning is a technique used in BDSM in which the dominant repeatedly strikes the submissive with a long flexible cane, usually on the buttocks.', 
        'Flogging': 'The use of toys, typically associated with BDSM and domination/submission, being employed against a submissive or bottom, particularly referring to contact play involving whips of any type, riding crops, paddles or flogs.', 
        'Gagging / Choking': 'Being made to gag or choke, either by objects inserted into the mouth or hands/objects around the neck.', 
        'Beating': 'Being struck with fists or other objects', 
        'Spanking': 'The act of striking the buttocks of another character, or being the recipient of such; often as a form of erotic foreplay or as punishment in a BDSM setting.', 
        'Cock/Pussy slapping': 'slapping the genitalia of your partner, or recieving such slaps', 
        'Cock/Pussy torture': "Engaging in an RP in which at least one character's genitals will be given negative attention, the intent of which to be to cause physical pain.", 
        'Hot Wax': 'The act of using wax, typically hot candle wax, as a form of sexual stimulation and/or torture, or receiving such actions.', 
        'Scratching': 'One character scratching another with their nails or claws, sometimes leaving marks; sometimes but not necessarily painful.', 
        'Biting': 'The act of biting or being bitten; sometimes painful, sometimes playful.', 
        'Cutting ': 'The act of cutting a partner to cause pain in a sexual context.'
    }
}

kink_splits = {
    'Bodies': ['General'],
    'Clothing': ['Self', 'Partner'],
    'Groupings': ['General'],
    'General': ['Giving', 'Receiving'],
    'Ass play': ['Giving', 'Receiving'],
    'Restrictive': ['Self', 'Partner'],
    'Toys': ['Self', 'Partner'],
    'Domination': ['As Dominant', 'As Submissive'],
    'No consent': ['Aggressor', 'Target'],
    'Taboo': ['General'],
    'Surrealism': ['Self', 'Partner'],
    'Fluids': ['General'],
    'Degradation': ['Giving', 'Receiving'],
    'Touch & Stimulation': ['Actor', 'Subject'],
    'Misc. Fetish': ['Giving', 'Receiving'],
    'Pain': ['Giving', 'Receiving']
}

class ratings(enum.Enum):
    Unknown = 0
    Favorite = 1
    Like = 2
    Okay = 3
    Maybe = 4
    No = 5

rating_emojis = {
    ratings.Unknown: '❓',
    ratings.Favorite: '💖',
    ratings.Like: '😊',
    ratings.Okay: '🙂',
    ratings.Maybe: '😕',
    ratings.No: '💀'
}

ratings_choices = [discord.app_commands.Choice(name=rat.name, value=rat.name) for rat in ratings]
ratings_options = [discord.components.SelectOption(label=rat.name, emoji=rating_emojis[rat]) for rat in ratings]

def _options_for(kink: str):
    return [discord.components.SelectOption(label=f"{kink}: {rat.name}") for rat in ratings]

kinklist_choices = [discord.app_commands.Choice(name=kink, value=kink) for category in kinklist for kink in kinklist[category]]

def kink_choices_in_category(category: str):
    return [discord.app_commands.Choice(name=kink, value=kink) for kink in kinklist[category]]

def splits_choices_for_category(category: str):
    return [discord.app_commands.Choice(name=split, value=split) for split in kink_splits[category]]

def reverse_category(kink: str):
    aux = [category for category in kinklist if kink in kinklist[category]]
    return None if len(aux) == 0 else aux[0]

def get_explanation(kink: str):
    aux = [kinklist[category][kink] for category in kinklist if kink in kinklist[category]]
    return None if len(aux) == 0 else aux[0]

async def _silent_reply(interaction: discord.Interaction):
    try:
        await interaction.response.send_message()
    except discord.errors.HTTPException:
        pass # Silently ignore

class KinkDropdown(discord.ui.Select):
    def __init__(self, category: str, watcher, selected=None, disabled=False, do_silent_reply=True):
        self.watcher = watcher
        self.category = category
        self.do_silent_reply = do_silent_reply
        options = [discord.components.SelectOption(label=kink, default=kink==selected) for kink in kinklist[category]]
        super().__init__(placeholder=f"Please choose a kink", min_values=1, max_values=1, options=options, disabled=disabled)

    def _update_selected(self, selected=None):
        for opt in self.options:
            opt.default = opt.label==selected
        # logger.debug(f"KinkDropdown {self.category} opts now={self.options}")

    async def callback(self, interaction: discord.Interaction):
        self._update_selected(self.values[0])
        await self.watcher.on_kink_selected(self.values[0], interaction)
        if self.do_silent_reply:
            await _silent_reply(interaction)

class KinkConditionalDropdown(discord.ui.Select):
    def __init__(self, category: str, watcher, selected=None):
        self.watcher = watcher
        self.category = category
        options = [discord.components.SelectOption(label=split, default=split==selected) for split in kink_splits[category]]
        super().__init__(placeholder=f"Please choose one", min_values=1, max_values=1, options=options)

    def _update_selected(self, selected=None):
        for opt in self.options:
            opt.default = opt.label==selected
        # logger.debug(f"KinkConditionalDropdown {self.category} opts now={self.options}")

    async def callback(self, interaction: discord.Interaction):
        self._update_selected(self.values[0])
        await self.watcher.on_conditional_selected(self.values[0])
        await _silent_reply(interaction)

class KinkRatingDropdown(discord.ui.Select):
    def __init__(self, watcher):
        self.watcher = watcher
        super().__init__(placeholder=f"How much do you like it?", min_values=1, max_values=1, options=ratings_options, disabled=True)

    def _update_selected(self, selected=None):
        for opt in self.options:
            opt.default = opt.label==selected
        # logger.debug(f"KinkRatingDropdown opts now={self.options}")

    def enable(self):
        self.disabled = False

    async def callback(self, interaction: discord.Interaction):
        await self.watcher.on_rating_selected(self.values[0], interaction)

class KinkCategoryDropdown(discord.ui.Select):
    def __init__(self, watcher, selected=None):
        self.watcher = watcher
        options = [discord.components.SelectOption(label=category, default=category==selected) for category in kinklist]
        super().__init__(placeholder=f"Please choose a category", min_values=1, max_values=1, options=options)

    def _update_selected(self, selected=None):
        for opt in self.options:
            opt.default = opt.label==selected
        # logger.debug(f"KinkCategoryDropdown {self.category} opts now={self.options}")

    async def callback(self, interaction: discord.Interaction):
        self._update_selected(self.values[0])
        await self.watcher.on_category_selected(self.values[0])
        await _silent_reply(interaction)

class KinksView(discord.ui.View):
    def __init__(self, category: str, interaction: discord.Interaction, database: db.database):
        super().__init__()
        self.interaction = interaction
        self.database = database
        self._kink = None
        self._conditional = None
        self._category = category
        self._kink_dd = KinkDropdown(category, self)
        self.add_item(self._kink_dd)
        self._notified_explanation = False
        if len(kink_splits[category]) > 1:
            self._conditional_dd = KinkConditionalDropdown(category, self)
            self.add_item(self._conditional_dd)
        else:
            self._conditional = kink_splits[category][0]
        self._rating_dd = KinkRatingDropdown(self)
        self.add_item(self._rating_dd)

    async def update_if_needed(self):
        if self._kink is None or self._conditional is None: return
        # logger.debug("Enabling dd")
        self._rating_dd.enable()
        prev = self.database.get_kink(self.interaction.user.id, self._kink, self._conditional, self._category)
        if prev is not None:
            logger.debug(f"{self.interaction.user.id} had {prev}/{ratings(prev).name} saved for {self._kink}/{self._conditional}/{self._category}")
        else:
            logger.debug(f"{self.interaction.user.id} has no saved rating for {self._kink}/{self._conditional}/{self._category}")
        self._rating_dd._update_selected(ratings(prev).name if prev is not None else None)
        await self.interaction.edit_original_response(view=self)

    async def on_kink_selected(self, kink, interaction):
        # logger.debug("on_kink_selected cb")
        self._kink = kink
        self.print_dbg()
        await self.update_if_needed()

    async def on_conditional_selected(self, conditional):
        # logger.debug("on_conditional_selected cb")
        self._conditional = conditional
        self.print_dbg()
        await self.update_if_needed()

    async def on_rating_selected(self, rating, interaction):
        logger.info(f"{self.interaction.user.id} selected rating {rating} for {self._category}/{self._kink} ({self._conditional})")
        self.database.create_or_update_kink(self.interaction.user.id, self._kink, self._conditional, self._category, ratings[rating].value)
        if not self._notified_explanation:
            await interaction.response.send_message(content=f"Noted! You may continue adding new kinks with the same menu, and I'll keep track of everything~", ephemeral=True)
            self._notified_explanation = True

    def print_dbg(self):
        # logger.debug(f"self._kink = {self._kink}\nself._conditional = {self._conditional}")
        pass

class Kinktionary(discord.ui.View):
    def __init__(self, interaction: discord.Interaction):
        super().__init__()
        self.interaction = interaction
        self._kink = None
        self._kink_dd = None
        self._category = None
        self._category_dd = KinkCategoryDropdown(self)
        self.add_item(self._category_dd)

    async def on_category_selected(self, category):
        # logger.debug("on_category_selected cb")
        self._category = category
        if self._kink_dd is not None:
            self.remove_item(self._kink_dd)
        self._kink_dd = KinkDropdown(category, self, do_silent_reply=False)
        self.add_item(self._kink_dd)
        await self.interaction.edit_original_response(view=self)

    async def on_kink_selected(self, kink, interaction: discord.Interaction):
        # logger.debug("on_kink_selected cb")
        self._kink = kink
        expl = kinklist[self._category][kink]
        if expl is not None:
            content = f"Here's what I found about {kink}:\n> {expl}"
        else:
            content = f"I couldn't find any info about {kink} :c"
        await interaction.response.send_message(content=content, ephemeral=True)

# Commands
@discord.app_commands.guild_only()
class Kink(discord.app_commands.Group):
    def __init__(self, database: db.database, utils: bot_utils.utils):
        super().__init__()
        self.database = database
        self.utils = utils

    @discord.app_commands.command(description='Manage body-related kinks')
    async def bodies(self, interaction: discord.Interaction):
        logger.debug(f"Got kink bodies request from {interaction.user.id}")
        await self.utils.safe_send(view=KinksView('Bodies', interaction, self.database), ephemeral=True)

    @discord.app_commands.command(description='Manage clothing-related kinks')
    async def clothing(self, interaction: discord.Interaction):
        logger.info(f"Got kink clothing request from {interaction.user.id}")
        await self.utils.safe_send(view=KinksView('Clothing', interaction, self.database), ephemeral=True)

    @discord.app_commands.command(description='Manage grouping-related kinks')
    async def groupings(self, interaction: discord.Interaction):
        logger.info(f"Got kink grouping request from {interaction.user.id}")
        await self.utils.safe_send(view=KinksView('Groupings', interaction, self.database), ephemeral=True)

    @discord.app_commands.command(description='Manage general kinks')
    async def general(self, interaction: discord.Interaction):
        logger.info(f"Got kink general request from {interaction.user.id}")
        await self.utils.safe_send(view=KinksView('General', interaction, self.database), ephemeral=True)

    @discord.app_commands.command(description='Manage ass-play-related kinks')
    async def assplay(self, interaction: discord.Interaction):
        logger.info(f"Got kink ass-play request from {interaction.user.id}")
        await self.utils.safe_send(view=KinksView('Ass play', interaction, self.database), ephemeral=True)

    @discord.app_commands.command(description='Manage restrictive-related kinks')
    async def restrictive(self, interaction: discord.Interaction):
        logger.info(f"Got kink restrictive request from {interaction.user.id}")
        await self.utils.safe_send(view=KinksView('Restrictive', interaction, self.database), ephemeral=True)

    @discord.app_commands.command(description='Manage toy-related kinks')
    async def toys(self, interaction: discord.Interaction):
        logger.info(f"Got kink toys request from {interaction.user.id}")
        await self.utils.safe_send(view=KinksView('Toys', interaction, self.database), ephemeral=True)

    @discord.app_commands.command(description='Manage domination-related kinks')
    async def domination(self, interaction: discord.Interaction):
        logger.info(f"Got kink domination request from {interaction.user.id}")
        await self.utils.safe_send(view=KinksView('Domination', interaction, self.database), ephemeral=True)

    @discord.app_commands.command(description='Manage noncon-related kinks')
    async def noncon(self, interaction: discord.Interaction):
        logger.info(f"Got kink noncon request from {interaction.user.id}")
        await self.utils.safe_send(view=KinksView('No consent', interaction, self.database), ephemeral=True)

    @discord.app_commands.command(description='Manage taboo kinks')
    async def taboo(self, interaction: discord.Interaction):
        logger.info(f"Got kink taboo request from {interaction.user.id}")
        await self.utils.safe_send(view=KinksView('Taboo', interaction, self.database), ephemeral=True)

    @discord.app_commands.command(description='Manage surrealism-related kinks')
    async def surrealism(self, interaction: discord.Interaction):
        logger.info(f"Got kink surrealism request from {interaction.user.id}")
        await self.utils.safe_send(view=KinksView('Surrealism', interaction, self.database), ephemeral=True)

    @discord.app_commands.command(description='Manage fluid-related kinks')
    async def fluids(self, interaction: discord.Interaction):
        logger.info(f"Got kink fluids request from {interaction.user.id}")
        await self.utils.safe_send(view=KinksView('Fluids', interaction, self.database), ephemeral=True)

    @discord.app_commands.command(description='Manage degradation-related kinks')
    async def degradation(self, interaction: discord.Interaction):
        logger.info(f"Got kink degradation request from {interaction.user.id}")
        await self.utils.safe_send(view=KinksView('Degradation', interaction, self.database), ephemeral=True)

    @discord.app_commands.command(description='Manage stimulation-related kinks')
    async def stimulation(self, interaction: discord.Interaction):
        logger.info(f"Got kink stimulation request from {interaction.user.id}")
        await self.utils.safe_send(view=KinksView('Touch & Stimulation', interaction, self.database), ephemeral=True)

    @discord.app_commands.command(description='Manage misc kinks')
    async def misc(self, interaction: discord.Interaction):
        logger.info(f"Got kink misc request from {interaction.user.id}")
        await self.utils.safe_send(view=KinksView('Misc. Fetish', interaction, self.database), ephemeral=True)

    @discord.app_commands.command(description='Manage pain-related kinks')
    async def pain(self, interaction: discord.Interaction):
        logger.info(f"Got kink pain request from {interaction.user.id}")
        await self.utils.safe_send(view=KinksView('Pain', interaction, self.database), ephemeral=True)

# FIXME 
# Traceback (most recent call last):
#   File "adottomin.py", line 1459, in <module>
#     async def _test(self: Kink, interaction: discord.Interaction):
#   File "AppData\Local\Programs\Python\Python310\lib\site-packages\discord\app_commands\commands.py", line 2008, in decorator
#     return Command(
#   File "AppData\Local\Programs\Python\Python310\lib\site-packages\discord\app_commands\commands.py", line 677, in __init__
#     self._params: Dict[str, CommandParameter] = _extract_parameters_from_callback(callback, callback.__globals__)
#   File "AppData\Local\Programs\Python\Python310\lib\site-packages\discord\app_commands\commands.py", line 393, in _extract_parameters_from_callback
#     param = annotation_to_parameter(resolved, parameter)
#   File "AppData\Local\Programs\Python\Python310\lib\site-packages\discord\app_commands\transformers.py", line 828, in annotation_to_parameter
#     (inner, default, validate_default) = get_supported_annotation(annotation)
#   File "AppData\Local\Programs\Python\Python310\lib\site-packages\discord\app_commands\transformers.py", line 787, in get_supported_annotation
#     raise TypeError(f'unsupported type annotation {annotation!r}')
# TypeError: unsupported type annotation <class 'discord.interactions.Interaction'>
# @discord.app_commands.guild_only()
# class Kink(discord.app_commands.Group):
#     pass

# def safe_name(id: str):
#     return id.lower().replace('&', '').replace('  ', ' ').replace(' ', '-').replace('.', '')

# for category in kinks.kinklist:
#     @discord.app_commands.command(name=safe_name(category), description=f'Manage {category.lower()}-related kinks')
#     async def _test(self: Kink, interaction: discord.Interaction):
#         log_debug(interaction, f"Got kink modal request from {interaction.user.id}")
#         await interaction.response.send_message(view=kinks.KinksView(category, interaction), ephemeral=True)
#     setattr(Kink, category.lower(), classmethod(_test))
#     logger.debug(f"Added {category} to group class")

@discord.app_commands.guild_only()
class Kinklist(discord.app_commands.Group):
    def __init__(self, database: db.database, utils: bot_utils.utils):
        super().__init__()
        self.database = database
        self.utils = utils
    
    @discord.app_commands.command(description='Hide or show your kink list')
    @discord.app_commands.choices(visibility=[discord.app_commands.Choice(name=b, value=b) for b in ['public', 'private']])
    async def manage(self, interaction: discord.Interaction, visibility: discord.app_commands.Choice[str]):
        logger.info(f"{interaction.user} requested kinklist manage: {visibility.value}")

        self.database.set_kinklist_visibility(interaction.user.id, visibility.value == 'public')

        if visibility.value == 'public':
            content = "Okay, now people will be able to see your kink list!"
        else:
            content = "Okay, your kinklist is now private and only you will be able to see it!"

        await self.utils.safe_send(interaction, content=content, ephemeral=True)

    @discord.app_commands.command(description='Get someone\'s kink list')
    @discord.app_commands.describe(user='Whose list to get (gets yours by default)')
    async def show(self, interaction: discord.Interaction, user: typing.Optional[discord.Member]=None):
        user = user or interaction.user
        logger.info(f"{interaction.user} requested kink list: {user}")

        is_own = user.id == interaction.user.id

        is_public = self.database.get_kinklist_visibility(user.id)

        if not is_own and not is_public:
            await self.utils.safe_send(interaction, content=f"{user.mention}'s kinklist is currently private, you can ask them personally for it~", ephemeral=True)
            return

        data = self.database.get_kinks(user.id, ratings.Unknown.value)
        if len(data) == 0:
            await self.utils.safe_send(interaction, content=f"I couldn't find anything about " + ("you" if is_own else f"{user.mention}"), ephemeral=not (is_own and is_public))
            return

        aux = {rating.name: [] for rating in ratings}
        del(aux[ratings.Unknown.name])
        for kink in data:
            kink_name = kink[1]
            aux[ratings(kink[4]).name] += ['`' + kink_name + ("" if len(kink_splits[kink[3]]) == 1 else f" ({kink[2]})") + '`']

        logger.debug(f"Aux = {aux}")

        embed = discord.Embed(
            colour=random.choice(bot_utils.EMBED_COLORS)
        )
        
        embed.set_footer(text=f'Created at: {datetime.datetime.utcnow()}')
        
        try:
            icon_url = interaction.user.avatar.url
        except Exception as e:
            logger.warning(f"Exception while trying to handle icon thumbnail: {e}\n{traceback.format_exc()}")
            icon_url = None

        embed.set_author(name=f'{interaction.user}\'s kinklist', icon_url=icon_url)

        for rating in aux:
            if len(aux[rating]) == 0: continue
            embed.add_field(name=f"{rating_emojis[ratings[rating]]} {self.utils.plural(rating, len(aux[rating]))}", value=", ".join(aux[rating]), inline=False)

        # TODO create image from list
        # attachments = pin.attachments
        # if len(attachments) >= 1:
        #     embed.set_image(url=?)

        await self.utils.safe_send(interaction, embed=embed, ephemeral=not (is_own and is_public))

    @discord.app_commands.command(description='Clear your kink list (this cannot be undone!)')
    @discord.app_commands.describe(confirmation='Please type "I understand" to confirm you\'re aware this command cannot be undone')
    # @discord.app_commands.choices(confirmation=[discord.app_commands.Choice(name=b, value=b) for b in ['I understand', 'Cancel']])
    async def clear(self, interaction: discord.Interaction, confirmation: str):
        logger.info(f"Got kink clear request from {interaction.user.id}: '{confirmation}'")

        if confirmation.replace('"', '').lower() == 'i understand':
            self.database.clear_kinks(interaction.user.id)
            content = "Kink list cleared! Feel free to recreate it whenever you want~"
        else:
            content = "Ok, your list is still just as you left it~"

        await self.utils.safe_send(content=content, ephemeral=True)