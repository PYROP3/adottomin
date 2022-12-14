import botlogger
import db
import discord
import enum
import re
import bot_utils
import typing
import datetime
import random
import sqlite3
import traceback
import requests
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sn
import string
import os

from bs4 import BeautifulSoup
from difflib import SequenceMatcher
from pathlib import Path

logger = botlogger.get_logger(__name__)
emoji_font = Path('./fonts/noto_emoji/static/NotoEmoji-Regular.ttf')

kinklist = {
    'Body Part':{
        'Asses':None,
        'Cocks':None,
        'Balls':None,
        'Breasts':None
    },
    'Bodies':{
        'Skinny':'Expresses an interest in characters that are waifish, thin, or slender.',
        'Chubby':'Expresses an interest in characters that are well-rounded, full in form, and pudgy.',
        'Cut Cocks':'Expresses an interest in circumcised penises, or penises with very little foreskin.',
        'Glasses':'A preference for characters who wear glasses.',
        'Muscular Partners':'Expresses an interest in characters that are powerfully-built and/or athletic.',
        'Nonsexual Piercings':'Engaging in sex with a character who has piercings on parts of his or her body that are not of a sexual nature, such as but not limited to tongue, ears, bellybutton etc.',
        'Pubic Hair':'Expresses an interest in pubic hair, possibly in large or excessive quantities.',
        'Twinks':'Expresses an interest in male characters that are feminine and subtly defined.',
        'Twins':'Expresses an interest in two or more characters who are identical, often siblings, who may or may not be played by the same player.',
        'Uncut Cocks':'Expresses an interest in penises that have not been circumsized and have a large amount of foreskin.',
        'Very Fat Partners':'Expresses an interest in characters that are exceptionally overweight or obese.',
        'Very Lithe Partners':'Expresses an interest in characters that are exceptionally thin or lank.',
        'Very Muscular Partners':'Expresses an interest in characters that are exceptionally muscular or toned.',
        'Voluptuousness':'Expresses an interest in characters with wider than average hips and large buttocks.'
    },
    'Clothing':{
        'Cross-dressing':'Engaging in an RP where one or more characters dress in the clothes of the gender opposite to their own.',
        'Clothed sex':'Engaging in an RP where you and/or your partner are not undressed during sexual interaction.',
        'Heels':'Expresses an interest in the inclusion of high heeled shoes in the sexual context of an RP, or an interest in characters wearing such.',
        'Latex':'The usage of latex and/or rubber material worn as clothing',
        'Leather':'Expresses an interest in the inclusion of leather clothing in the sexual context of an RP, or an interest in characters wearing such.',
        'Lingerie':'Expresses an interest in the inclusion of lingerie in the sexual context of an RP, or an interest in characters wearing such.',
        'Masks':"The use of masks (surgical, BDSM, gas masks, etc), typically to conceal the wearer's identity, in an RP scene.",
        'Stockings':'Expresses an interest in the inclusion of stockings in the sexual context of an RP, or an interest in characters wearing such.',
        'Uniform / costume':'Expresses an interest in the inclusion of uniforms or costumes in the sexual context of an RP, or an interest in characters wearing such.',
        'Skirts':'Expresses an interest in the inclusion of skirts in the sexual context of an RP, or an interest in characters wearing such.'
    },
    'Pairings':{
        'as Male':None,
        'as Female':None,
        'as Femboy':None,
        'as Futa':None,
        'as MtF trans':None,
        'as FtM trans':None,
        'as male & female':None,
        'as multiple males':None,
        'as multiple females':None,
        'as multiple males & females':None
    },
    'General':{
        'Biting':'The act of biting or being bitten; sometimes painful, sometimes playful.',
        'Condoms':'The use of condoms in any way; typically refers to a preference for the use of condoms during penetration, but may also refer to condom play, in which a condom (typically filled), is used as a sex toy; or, the filling of condoms with fluids, such as semen.',
        'Consensual':"A preference for sexual interactions between characters in an RP to be fully consenting, by their characters' own free wills.",
        'Cuddling':'Characters showing affection through hugging, snuggling, and other forms of physical closeness.',
        'Dirty Talking':"The act of speaking in a typically explicit manner to provoke sexual stimulation from a participant, sometimes one's self; often in the context of seduction or foreplay.",
        'Docking':"Phallic insertion into another person's sheath and/or foreskin.",
        'Edging':'Keeping on the edge of climax without orgasm',
        'Ear Play':'Interest in roleplay where ears play an important role. This can involve suckling, caressing, breathing/whispering into, pulling them, or any other kind of interaction focusing on the ears.',
        'Femboys':'Effeminate, girly males.',
        'Flexibility/Contortionism':'Exceptional or unrealistic flexibility, typically used to achieve extremely difficult or impossible sexual positions to derive maximum stimulation.',
        'Face-sitting':"A sexual practice where someone sits on another character's face with their buttocks or genitals, causing the person to be smothered, sometimes to the point asphyxiation; often done as form of forcing oral gratification.",
        'Facials':"The act of cumming directly onto one's face",
        'Frotting':'The act of at least two penises being ground against each other for sexual gratification.',
        'Gender Transformation':'Changes to sex or gender, sometimes willing, sometimes unwilling. Encompasses both magical and sci-fi changes, as well as more realistic gender reassignment.',
        'Handjob / Fingering':'Sexual stimulation by direct, physical contact of the hands or fingers to the genitals.',
        'Swallowing':'The act of orally consuming semen, either directly or indirectly from a penis.',
        'Hotdogging':'The act of placing a penis between the ass cheeks and pressing them against it -- sliding it between them in order to reach sexual satisfaction.',
        'Ice':'The use of ice in any fashion during sex, typically as a form of erotic foreplay.',
        'Intelligent Partners':'Exhibits a preference for partners that have particularly high levels of intelligence, wit, cunning and manipulation skills.',
        'Kissing':'Expresses an interest in kissing or being kissed by another character, typically denoting French kissing.',
        'Leather':'The use of leather, often in a bondage situation; typically includes leather garments or equipment associated with dominants, as well as harness gear.',
        'Licking':'The act of one character licking another. May or may not be sexual; when sexual, often in areas of the body that are sexual, including but not limited to the nipples, breasts, anus, genitalia etc.',
        'Masturbation':'The act of stimulating oneself sexually, usually utilizing physical contact from the hands or fingers to the genitals.',
        'Navel Play':"Engaging in sexual acts involving pleasure derived from a character's bellybutton; often refers to licking or tonguing of the navel.",
        'Photography/Videotaping':'The act of visually recording a scene amongst participants, often as a form of humiliation, exhibitionist fetishism and/or blackmail/extortion.',
    },
    'General 2':{
        'Romance / Affection':'Displaying or expressing love or strong affection, passion, either during love making or during normal scenes.',
        'Smoking':'Refers to the act of smoking and/or receiving pleasure from an aspect of smoking or smoke during an RP.',
        'Socks/Stockings':'Expresses an interest in the inclusion of socks and/or stockings in the sexual context of an RP, or an interest in characters wearing such.',
        'Strip Tease':'The act of dramatically removing clothing or watching a participant do such, typically as a form of seduction.',
        'Teasing':"Refers to extended scenes of foreplay prior to explicit, sexual intercourse, which may be physical and/or verbal, typically to arouse one's partner to the point of sexual frustration or desperation.",
        'Tickling':'The act of tickling and/or being tickled in a sexual context of an RP; or, receiving sexual stimulation from such.',
        'Tomboys':'Females who behave or present themselves in a masculine manner.',
        'Transformation':"The act of causing the physical characteristics of a participant of an RP, possibly including one's self, by magical or chemical means, to change in a dramatic fashion; may refer to a myriad of different types of transformations, and connotates receiving sexual pleasure from the act of transformation itself.",
        'Tribadism / Scissoring':"Form of non-penetrative sex in which a person rubs their vagina against a same-sex partner's body for sexual stimulation, in most cases vaginal-to-vaginal contact through scissoring.",
        'Underwear':"An affinity for underwear, either being worn on one's self, one's partner(s) or by itself; often involves stimulation from the scent or tactility of the underwear, but may also refer to using underwear as a sex toy in any way.",
        'Unintelligent Partners':'Exhibits a preference for characters that exhibit below-average intelligence, often low enough to make them easy to manipulate; this includes everything from air-headed bimbos to large, animalistic brutes.',
        'Vanilla Sex':'Sex which does not involve such elements as BDSM, kink, or fetish activities.',
        'Voyeurism/Exhibitionism':"Refers to the derivation of sexual stimulation from either/or the action of watching, typically in secret, a person (or people) reveal themselves or do something otherwise explicit, or the act of revealing one's self and/or doing something otherwise explicit with the intent to be viewed."
    },
    'Oral Sex':{
        'Blowjob':'Sexual stimulation by direct, physical contact of the mouth or tongue to male genitals',
        'Cunnilingus':'Sexual stimulation by direct, physical contact of the mouth or tongue to female genitals',
        'Deep throat':'The act of penetrating the mouth of another character to the depths at which the penis or insertion enters the back of the mouth',
        'Face-Fucking':'Refers to the act of penetrating the mouth of another character with a similar technique as fucking a vagina or anus, typically by bracing the mouth or skull and thrusting back and forth; often rough.',
        'Oral Virginity':'Engaging in an RP in which a character that has never performed fellatio or cunnilingus performs such acts.',
        'Throat Penetration':'The act of penetrating the mouth of another character to the depths at which the penis or insertion enters the back of the mouth cavity and/or throat, sometimes causing a gag reflex, or being the recipient of such actions.'
    },
    'Ass play':{
        'Ass Worship':"Gratuitous acknowledgment of one's partner's ass or buttocks, either verbal and/or physical, or receiving such actions.",
        'Anal Fisting':"The act of inserting one's hand(s) and/or arm(s) into one's partner's anus, or being the recipient of such acts.",
        'Anal Training':"Engaging in the use of the various anatomy of a character's anus to otherwise prepare and/or acclimate the character to an insertion, the size of which the character would not otherwise be comfortable taking.",
        'Anal Toys':'Refers to the inclusion of anal penetration with sex toys, including but not limited to dildos, vibrators, anal eggs, anal beads, etc.',
        'Anal Virginity':'Engaging in anal sex with a character who has never been anally penetrated before, or being anally penetrated while playing a character that has never been penetrated before.',
        'Anal sex/pegging':'Being penetrated by a partner, with a penis or strap-on',
        'Double penetration':"The act of penetrating a single character's anus with two objects, including but not limited to the penis, sex toys, fist etc., or receiving such.",
        'Enemas':'The application of a liquid, typically warm water or a body fluid, to the intestines of a character, often to clean them out, but sometimes as a form of discipline or sexual gratification, or receiving such actions; might imply a form of administration other than phallic penetration.',
        'Rimming':"The act of giving oral stimulation to a partner's anus, by the means of licking and/or penetrating the recipient's anus with the tongue.",
        'Gaping (Anal)':'Stretching the anus during penetration, to the point that it stays open for a period of time.'
    },
    'Restrictive':{
        'Bondage (Light)':'The use of bondage that is mild or moderate in either the position in which it causes the bound character to be in, the duration for which the character will be in bondage, the level of discomfort caused by the bondage or the amount of immobilization that will occur due to the bondage.',
        'Bondage (Heavy)':'The use of bondage that is extreme in either the position in which it causes the bound character to be in, the duration for which the character will be in bondage, the level of discomfort caused by the bondage or the amount of immobilization that will occur due to the bondage.',
        'Chastity':'Sexual abstinence, either willing or forced; this can include someone simply abstaining from sexual activity, or the wearing of a device that prevents it.',
        'Collar':'Wearing a collar around the neck',
        'Encasement':'oneâ€™s whole body being wrapped up like a mummy in a latex suit, sleepsack, or other fetish gear for the purposes of sexual gratification.',
        'Gag':"The act of placing and lodging an object in another character's mouth to force him or her to breathe through his or her nose, as well as creating the inability to speak, or receiving such actions.",
        'Leash':'Being lead around on a leash'
    },
    'Toys':{
        'Dildos':'an object shaped like an erect penis used for sexual stimulation.',
        'Plugs':'a sex toy of a type designed to be inserted into the rectum.',
        'Sounding':"The act of inserting metal rods into a male or female's urethra, or receiving such actions; technically implies rods that resonate and/or vibrate in response to a form of stimulation, but does not necessarily mean so.",
        'Strap-ons':'Engaging in an RP in which at least one character will wear a strap-on to penetrate another character.',
        'Vibrators':'a vibrating device used for sexual stimulation.'
    },
    'Domination':{
        'General Dom / General Sub':'Catchall for Dominant/Submissive Activities.',
        'Domestic servitude':'Being served by a butler, waitress, chauffeur, maid or housekeeper, or serving as one.',
        'DD/lg, MD/lb':'Daddy or Mommy Dom/ Littly Girl or Boy. The daddy/mommy is the more dominant half of the relationship, the little is the more submissive.',
        'Discipline':'The use of reinforcement (rewards and/or punishments) in order to train a submissive to obey the various commands of a master.',
        'Forced orgasm':'A forced orgasm is consensual BDSM or kinky sexual play whereby a person consents to be forced to orgasm in a way that is beyond their control.',
        'General Dominant / Submissive':None,
        'Immobilization':'Engaging in an RP in which at least one character will be entirely, physically immobilized by any means, often heavy bondage or mummification; typically involved in BDSM play.',
        'Orgasm control':'Refers to the dominant being in control of when the submissive achieves orgasm, either by physical means or by command; typically involves domination and/or excessive teasing and edging; orgasm may be completely denied.',
        'Orgasm denial':'Refers to the dominant denying the submissive orgasm.',
        'Power exchange':'A relationship with service at the core.',
        'Pet play':'Petplay is a in role in which the focus is on the sub entering the altered mind space of a different species, often a dog, cat, or horse.',
        'Slavery':"Serving as the dominant's beck and call, or receiving such service, without choice."
    },
    'No consent':{
        'Blackmail / coercion':'Refers to the inclusion of Coercion and/or Blackmail in the context of the story arc of an RP, often in the form of a semi-consensual means of receiving sex from a partner.',
        'Dubious consent':"situations where one partner's consent is in question, though not outright rape.",
        'Drugs':'The use of illicit drugs in the context of an RP, typically to disorientate or otherwise mentally incapacitate a character, or to elevate the sensations of sex.',
        'Alcohol':'The use of alcohol in the context of an RP, typically to disorientate or otherwise mentally incapacitate a character, or to elevate the sensations of sex.',
        'Kidnapping':'The act of abducting a character in an RP for the purpose of abusing, often sexually, or being abducted for such reasons; often implies indefinite imprisonment.',
        'Non-con / rape':"taking/being taken against one's will, often through force",
        'Sleep play':'Engaging in sexual acts with an unconscious/asleep partner'
    },
    'Taboo':{
        'Age Gap':'Refers to scenes in which there is a signifigant gap in the ages of characters.',
        'Bestiality':'Refers to a sapient character engaging in a sexual act with a non-sapient animal, or playing a non-sapient animal in an RP and being engaged by a sapient character.',
        'Cheating':'Where one or both partners are being unfaithful to significant others.',
        'Exhibitionism':'Engaging in an RP in which the setting is of a public nature; typically used in conjunction with exhibitionism and/or humiliation.',
        'Incest':'Engaging in an RP in which at least two characters will be related',
        'Interracial':'Scenes based on interracial interactions without relying on racial stereotypes.',
        'Raceplay':'Scenes based on racial stereotypes or racism, including scenes set in racist settings.',
        'Necrophilia':'The act of having sex with a dead, or otherwise unconscious or inanimate, character that was once alive, or, theoretically, receiving such actions.',
        'Voyeurism':"Refers to the derivation of sexual stimulation from either/or the action of watching, typically in secret, a person (or people) reveal themselves or do something otherwise explicit, or the act of revealing one's self and/or doing something otherwise explicit with the intent to be viewed."
    },
    'Surrealism':{
        'Breast Growth':"A situation in which at least one character's female breasts grow in size, typically to fantastical proportions, by any means, including but not limited to magical or chemical.",
        'Cock/Ball Growth':"A situation in which at least one character's male penis and testicles grow in size, typically to fantastical proportions, by any means, including but not limited to magical or chemical infusion or due to sexual fluids becoming blocked or otherwise obstructed.",
        'Cum Inflation':'Engaging in an RP in which at least one character is filled with an impossible amount of semen, typically directly from the penis due to anal, vaginal or oral sex, causing his or her stomach and/or body to expand to fantastical sizes.',
        'Extreme Pregnancy':'The act of becoming pregnant with an incredible or unrealistic size and/or number of fetuses/eggs, often in an unrealistically short time span, and often to the point of immobility, or engaging in an RP in which at least one character fits such a description.',
        'Forced Growth':'Expresses an interest in which at least one character will be forced to endure any part(s) of his/her body growing against his/her will, typically as a side-effect of magic or chemical alteration, or as an unwelcome response to certain stimuli.',
        'Furry':'Anthropomorphic animal characters.',
        'Futanari/Futa':'characters who have an overall feminine body, but have both female and male genitalia (although testicles are not always present)',
        'Ghost':'The formerly living, not currently in posession of a body',
        'Growth':'Growing in body size by magical, medicinal, or otherwise fantastic means.',
        'Hyper Muscle Growth':"Increasing the size or strength of one's muscles to excessive or impossible degrees.",
        'Inflation':'Engaging in an RP in which at least one character is filled with an impossible amount of a substance other than a bodily fluid, typically a gas or liquid, causing his or her stomach and/or body to expand to fantastical sizes.',
        'Macrophilia':'Expresses an interest in characters that are incredibly and unrealistically tall.',
        'Magic Users':'RPs involving characters that are capable of performing magical or supernatural feats that may or may not be sexual in nature; typically refers to transformation or mind control-related play.',
        'Male Pregnancy':'The act of a male character becoming pregnant during the course of an RP, or engaging in an RP in which at least one male character is pregnant.',
        'Microphilia':'Expresses an interest in characters that are impossibly and unrealistically small.',
        'Monster or Alien':'Various types of monsters, Extraterrestrials, and aesthetically challenging characters.',
        'Multiple Breasts':'Expresses an interest in characters that have more than one pair of breasts, typically found on canine females.',
        'Muscle Growth':"Increasing the size or strength of one's muscles by magical, medicinal, or other fantastic means.",
        'Nipple Penetration':'The act of penetrating the nipple, often deep into the breast, with an object such as a finger, sex toy or penis, etc, or receiving such actions.',
        'Oviposition':'Engaging in an RP in which at least one character will lay eggs through an orifice.',
        'Popping':"The act of causing a part of a character's anatomy, or the entire character, to explode by means of ballooning or inflation, or being the recipient of such actions.",
        'Prehensile Cocks':'Expresses an interest in characters that have the ability to control the motion of their penises.',
        'Rubber/Gel Characters':'Expresses an interest in characters who are composed of rubber, latex, gel or an otherwise elastic material.',
        'Transformation':"The act of causing the physical characteristics of a participant of an RP, possibly including one's self, by magical or chemical means, to change in a dramatic fashion; may refer to a myriad of different types of transformations, and connotates receiving sexual pleasure from the act of transformation itself.",
        'Tentacles':'Engaging in an RP in which self-sentient tentacles or tentacle-like appendages will penetrate a character; often implies multiple penetration.'
    },
    'Vore / Unbirth':{
        'Absorption':'Vore by means of merging with the predator, or being absorbed and/or dissolved by an anatomical fluid of the predator.',
        'Alternative Vore':'The act of physically consuming another character, performed through an orifice other than the mouth, penis, vagina or anus, or receiving such actions.',
        'Anal Vore':'Vore where something or someone is swallowed into the anus.',
        'Cock Vore':'The act of physically consuming another character, performed through the penis, often resulting in the prey character being lodged into the testicles, or being the recipient of such actions.',
        'Digestion':'Engaging in a vore-related RP in which the prey character will be digested in whatever fluid(s) are applicable.',
        'Disposal':'Engaging in a vore-related RP in which the prey will be consumed, digested and released as fecal matter and/or urine.',
        'Hard Vore':'Engaging in vore in which the prey character is chewed and/or eaten piece by piece, or otherwise physically mutilated by the act of being consumed.',
        'Realistic Vore':'Engaging in a vore scene in which realistic physiology is taken into account; typically connotates hard vore and digestion.',
        'Soft Vore':'Engaging in vore in which the prey character is consumed whole, causing no or minimal damage to the character due to the vore process.',
        'Unbirthing':'The act of physically consuming another character through the vagina and into the womb, or being the recipient of such actions.',
        'Unrealistic Vore':'Engaging in a vore scene in which realistic physiology is not taken into account; typically connotates soft vore.',
        'Vore - Being Predator':'Being the consuming partner in a vore or unbirth situation, acting as the predator.',
        'Vore - Being Prey':'Being the consumed partner in a vore-related RP situation.'
    },
    'Fluids':{
        'Blood':'Pertains to the inclusion of blood or the retrieval of blood in any form in a sexual context, or engaging in acts which will draw blood.',
        'Cum play':'Any number of situations focused on playing with cum.',
        'Diapers':'A situation in which at least one character will wear a diaper; typically implies that the diaper will be soiled with urine and/or fecal matter, usually in conjunction with age play or infantilism, but sometimes in conjunction with humiliation.',
        'Lactation':"The act of producing milk from one's breasts, or engaging in sex with a character that produces milk from one's breasts, typically in response to sexual stimulation, and any play that will emanate thereof.",
        'Messy':'Engaging in an RP in which the sexual portion of the RP is set in a venue in which a large amount of liquids, which may be bodily fluids, will be involved, such as but not limited to mud, food, snot or slime.',
        'Saliva':'Interest in roleplay that prominently includes saliva. This may refer to excessive secretion and great appreciation of it.',
        'Scat':'Pertains to the inclusion of fecal matter or the expelling of fecal matter in any form in the sexual context of an RP.',
        'Sweat':'The act of sweating and/or receiving sexual gratification from the appearance, taste, scent and/or tactility of sweat.',
        'Watersports':'Pertains to the inclusion of urine, or the expelling of urine, in any form, in the sexual context of an RP.',
        'Begging':'The self-abasing act of pleading, as a form of submission, being incorporated into an RP.',
        'Cock Slapping':"The act of using one's penis to slap one's partner and/or being slapped by a penis, usually in order to humiliate or debase a bottom prior to or during fellatio.",
        'Forced Nudity':'The act of either forcing a character to be nude or being forced to be nude by another character; typically used in public situations.',
        'Force Feeding':'Engaging in an RP in which a character, typically bound or otherwise immobile, is forced to consume large, often impossible and unrealistic, amounts of food against his or her will, often resulting in inflation and/or weight gain.',
        'Glory hole':'Servicing a partner or receiving service from a partner with a physical barrier between the participants',
        'Humiliation':'Engaging in an RP in which one character will be embarrassed, typically extremely and/or frequently, in an attempt to elicit either a response of sexual gratification from the emotions correlating to humiliation, or merely as a form of psychological domination or punishment; typically a more intense form of degradation.',
        'Name calling':'Engaging in an RP in which one character will be called names, in an attempt to elicit either a response of sexual gratification from the emotions correlating to humiliation, or merely as a form of psychological domination or punishment.',
        'Verbal Abuse':'The act of verbally accosting or being verbally accosted with derogatory terms pertaining to sex, or in the effort to demean, degrade or otherwise humiliate another character, or occasionally to elicit sexual stimulation from abuse.'
    },
    'Touch & Stimulation':{
        'Ass worship':"Gratuitous acknowledgment of one's partner's ass, either verbal and/or physical, or receiving such actions; typically implies oral stimulation.",
        'Cock/Pussy worship':"Gratuitous acknowledgment of one's partner's genitalia, either verbal and/or physical, or receiving such actions; typically implies oral stimulation.",
        'Electro stimulation':'The use of sex toys that carry an electrical current; sometimes painful.',
        'Foot play':'The act of incorporating the feet or feet paws into the sexual context of an RP, including but not limited to the worshiping of feet, receiving sexual gratification from the sight or smell of feet and/or humping feet, sometimes to the point of orgasm.',
        'Sensation play':"Sensation play describes a wide variety of activities, both vanilla and kinky, that use the body's senses as a way to arouse and provide stimulation to a partner. Although sensation play is often related to skin sensations, it doesn't have to be so limited. Sight, taste, and hearing can also be included in sensation play.",
        'Tickling':'The act of tickling and/or being tickled in a sexual context of an RP; or, receiving sexual stimulation from such.'
    },
    'Misc. Fetish':{
        'Breast/Nipple Worship':"Gratuitous acknowledgement of one's partner's chest or nipples, either verbal and/or physical, or receiving such actions.",
        'Breath play':'A situation in which at least one character will have physical control over the breathing habits of another character, often by either intermittent choking and/or due to the penetration of the throat.',
        'Breeding':'Entails the act sexual intercourse for the sole purpose of inducing pregnancy and/or producing offspring.',
        'Crotch Sniffing':'The act of receiving pleasure from inhaling the scent of the crotch, or receiving such actions. Emphasis is often placed on the musk and/or pheromone-related properties of the scent.',
        'Cuckold / Cuckquean':'Refers to the act of a character who, within the confines of the RP world has been designated to be in a relationship, will have sexual interaction with a character other than the one who has been predetermined to be in a relationship, in the context of the RP.',
        'Double Penetration':'The act of penetrating a single character with two objects, including but not limited to the penis, sex toys, fist etc., or receiving such.',
        'Extreme Tightness':'Engaging in an RP in which at least one character exhibits exceptional tightness in his or her anus, vagina or throat; sometimes implies pain, exceptionally large penetrations and/or inexperience.',
        'Feminization':'Feminization is a type of role play that involves imposing traditionally female attributes onto a submissive male partner. It may also involve an adoption of traditionally feminine behaviors and mannerisms.',
        'Fisting':"The act of placing one's hand(s) and/or arm(s) into a vagina, or receiving such actions.",
        'Food Play':'The act of incorporating food into the sexual context of an RP, including but not limited to force-feeding, use of whipped cream or chocolate sauce or receiving sexual gratification from the act of eating; typically implies incredible and/or unrealistically large amounts of food being consumed.',
        'Foot Play':'The act of incorporating the feet or feet paws into the sexual context of an RP, including but not limited to the worshiping of feet, receiving sexual gratification from the sight or smell of feet and/or humping feet, sometimes to the point of orgasm.',
        'Foreskin Worship':None,
        'Gangbang':"Gratuitous acknowledgment of one's partner's foreskin, either verbal and/or physical, or receiving such actions; typically implies oral stimulation.",
        'Genital/Nipple Piercings':'Engaging in an RP in which at least one character has piercings that are located on the nipples or sexual areas of the body; typically cock piercings.',
        'Muscle Worship':"Gratuitous acknowledgment of someone's muscular physique, either verbal or physical.",
        'Musk':'Refers to an RP involving characters that are exceptionally musky; typically implies pheromones derived from the crotch, which may or may not lack hygiene to any degree.',
        'Onomatopoeia':'Engaging in an RP, or getting turned on by an emphasis on exaggerated descriptions of sexual noises in a roleplay, usually described with onomatopoeia, words that seek to duplicate the sounds they describe. Often refers to fluid noises such as: slosh, splurt, squirt, gurgle, splortch, or others.',
        'Pregnancy':'Fetishizing a pregnant character',
        'Queefing':'The sounds of air expulsion via intercourse.',
        'Sexual Exhaustion':"Engaging in an RP in which at least one character's genitals and/or orifice(s) endure pain due to exceptionally arduous sex or sex of an exceptional duration; implies continuing despite such.",
        'Sexual Frustration':'Engaging in an RP in which at least one character is exceptionally desperate or horny and is often willing to eschew standard inhibitions in order to receive sexual stimulation.',
        'Shaving':'Engaging in the removal of fur/hair from a participant in an RP by the means of shaving.',
        'Slob':'Characters without hygiene or uncaring of typical standards for cleanliness due to laziness, personal choice, or otherwise; may emphasize and derive pleasure from laziness or from actions linked with a lack of hygiene.'
    },
    'Cum-related':{
        'Bukkake':'The act of a group of at least two people ejaculating directly onto the face and/or body of a single recipient, or receiving such actions.',
        'Creampie':'The act of orgasming into or onto an exposed, often gaping, orifice, or receiving such actions.',
        'Cum Bath':"The act of being treated physically with cum -- typically in large amounts -- like having it rubbed into one's skin or fur, or literally bathing in it, or having one's semen used in such ways.",
        'Cum Enemas':'The act of performing an enema, the liquid being used in such being semen, or receiving such actions, often by means of an orgasm.',
        'Cum From Mouth/Nose':"The act of ejaculating with such force and/or by such a volume that the cum leaks and/or sprays from the bottom's mouth and/or nose, or receiving such actions.",
        'Cum Marking':'The act of cumming onto a bottom or submissive with the intent for the scent or sight of the cum to work as a proprietary mark, sometimes for extended or permanent periods of time, or receiving such actions.',
        'Cum Milking':'The act of collecting or milking the semen from at least one male partner, typically done through manual or mechanical stimulation to the penis, or using stored semen as a sexual toy in an RP. Often involves machines and apparati.',
        'Cum on Clothes':'The act of ejaculating onto clothing or wearing clothing that has been ejaculated on, often in public and/or for extended periods of time.',
        'Excessive Precum':'Engaging in an RP in which a character produces a larger than average amount of precum; typically unrealistic.',
        'Excessive Semen':'Engaging in an RP in which a character produces a larger than average amount of semen; typically unrealistic.',
        'Heavily Excessive Precum':'Engaging in an RP in which a character, typically unrealistically endowed, produces exceptionally large volumes of precum, including but not limited to multiple gallons, and/or looses precum with exceptional force and consistency, often to the point of being comparable to urinating or further.',
        'Heavily Excessive Semen':'Engaging in an RP in which a character, typically unrealistically endowed, produces exceptionally large volumes of semen, including but not limited to multiple gallons, and/or looses semen with exceptional force and consistency, often to the point of being comparable to urinating or further.',
        'Premature Ejaculation':'Expresses interest in at least one partner reaching orgasm very quickly; typically implies eagerness, excessive sensitivity and/or prolonged teasing.',
        'Realistic Cum':'Expresses a preference for engaging in an RP in which the volume and quality of sexual fluid is realistic.',
        'Shooting Precum':'Engaging in an RP in which a character spurts precum with exceptional force and consistency.',
        'Sloppy Seconds':"Engaging in an RP in which a character that has just been came in receives sex from a different partner in the same orifice without removing the previous top's semen.",
        'Snowballing':"The act of receiving cum into one's mouth transmitted from another person's mouth, or french kissing while sharing a load of cum between one anothers' mouths.",
        'Thick/Sticky Cum':"A preference for characters' semen to be particularly thick and/or viscous, often comparable to tar or glue.",
        'Stomach Bulging':"Engaging in an RP in which a character's stomach will bulge, either due to an exceptionally large insertion (often taking the shape of such), due to eating an exceptionally large amount of food or as a localized form of inflation from any liquid or gas."
    },
    'BDSM & Related':{
        'Sadism/Masochism':'The act of taking the role of a sadist or masochist, meaning one that receives sexual gratification from being the recipient of or administering physical pain.',
        'Apparatuses':'The use of complex objects with moving parts in order to bondage, immobilize or otherwise sexually gratify and/or incapacitate a character, in the sexual context of an RP.',
        'Begging':'The self-abasing act of pleading, as a form of submission, being incorporated into an RP.',
        'Blindfolds':'The use of blindfolds or other objects to obscure the vision of at least one character in a sexual context.',
        'Branding':'A situation in which at least one character will be branded, typically as a form of sadomasochism. Typically by means of applying intense heat in a specific pattern designed to visually show ownership.',
        'Caging':'The act of placing another character in a cage, or being placed in a cage, or other confining, device.',
        'Chastity':'Sexual abstinence, either willing or forced; this can include someone simply abstaining from sexual activity, or the wearing of a device that prevents it.',
        'Degradation':'A situation where one character will be purposefully degraded, meaning his or her sense of self worth will be lowered; typically in the context of guilt or BDSM.',
        'Discipline/Reinforcement':'The use of reinforcement (rewards and/or punishments) in order to train a submissive to obey the various commands of a master.',
        'Extreme Humiliation':'Engaging in an RP in which one character will purposefully be humiliated to the point (or attempted point) of intense, mental anguish and total loss of self-worth through sexual interaction; typically implies exceptional or devastating, psychological damage.',
        'Face Slapping':'Slaps to the face, of any degree or severity.',
        'Flogging/Whipping':'The use of toys, typically associated with BDSM and domination/submission, being employed against a submissive or bottom, particularly referring to contact play involving whips of any type, riding crops, paddles or flogs.',
        'Gags':"The act of placing and lodging an object in another character's mouth to force him or her to breathe through his or her nose, as well as creating the inability to speak, or receiving such actions.",
        'Hand Cuffs':'The use of hand cuffs to partially immobilize a character during an RP, or to restrain a character to an object.',
        'Heavy/Extreme Bondage':'The use of bondage that is extreme in either the position in which it causes the bound character to be in, the duration for which the character will be in bondage, the level of discomfort caused by the bondage or the amount of immobilization that will occur due to the bondage.',
        'Humiliation':'Engaging in an RP in which one character will be embarrassed, typically extremely and/or frequently, in an attempt to elicit either a response of sexual gratification from the emotions correlating to humiliation, or merely as a form of psychological domination or punishment; typically a more intense form of degradation.',
        'Leash & Collar':'Engaging in an RP in which a submissive or bottom will be adorned with a collar that will be attached to a leash.',
        'Light/Medium Bondage':'The use of bondage that is mild or moderate in either the position in which it causes the bound character to be in, the duration for which the character will be in bondage, the level of discomfort caused by the bondage or the amount of immobilization that will occur due to the bondage.',
        'Master/Pet':'Engaging in an RP in which a domination/submission relationship is played between at least two characters, and in which the bottom character takes on the role of a pet; typically a training-based scenario with positive reinforcement over negative reinforcement, as well as the inclusion of affection.',
        'Master/Slave':'Engaging in an RP in which a domination/submission relationship is played between at least two characters, and in which the bottom character takes on the role of a slave; typically requires the slave to accept any and all commands, often involves non-sexual forms of abuse and uses negative reinforcement.',
        'Objectification':'The act of either being treated or treating another character as a specific and set object, often articles of furniture, or bestowing dehumanizing tasks to a character in order to imbue a character with the traits of an object.',
        'Physical Restraints':'The act of giving or receiving commands, typically verbal, that limit the way in which another character is permitted to physically interact with another character.',
        'Public Humiliation':'One or more characters engaging in explicit and elicit, sexual activity in a public setting for the purposes of humiliating one or more characters.',
        'Sissification':'The act of changing the appearance of a male character through realistic means, particularly by the use of makeup, female clothes and/or female accessories, to appear as a female and/or forcing the male to adopt the mannerisms of a female, or being the recipient of such actions.',
        'Wax Play':'The act of using wax, typically hot candle wax, as a form of sexual stimulation and/or torture, or receiving such actions.'
    },
    'Watersports / Scat':{
        'Bathroom Control':'A situation in which a character controls when, how and where another character may use the bathroom in any fashion, typically as a form of control or degradation.',
        'Diapers':'A situation in which at least one character will wear a diaper; typically implies that the diaper will be soiled with urine and/or fecal matter, usually in conjunction with age play or infantilism, but sometimes in conjunction with humiliation.',
        'Farting':'Farting, during sexual intercourse, or just as an act during the roleplay. May be exaggerated (visible expulsions of air) and/or with exaggerated flatulent noises.',
        'Hyper Scat':'Producing unnatural amounts of feces, or using other means to obtain feces in huge, often unrealistic, amounts within an RP, the excretion of product thereof causing sexual stimulation and/or distress to one or more characters.',
        'Hyper Watersports':'Producing unnatural amounts of urine, or using other means to obtain urine in huge, often unrealistic, amounts within an RP, the excretion of product thereof causing sexual stimulation and/or distress to one or more characters.',
        'Marking':'The act of urinating on another character in order to mark them with your proprietary scent of urine, or being the recipient of such actions.',
        'Piss Enemas':'The act of performing an enema, the liquid being used in such being urine, or receiving such actions, often by means of someone urinating inside his/her partner.',
        'Scat':'Pertains to the inclusion of fecal matter or the expelling of fecal matter in any form in the sexual context of an RP.',
        'Scat Torture':'The act of using fecal matter or the act of expelling fecal matter to abuse another character who is unwilling or uninterested in taking part in such actions, or being the recipient of such.',
        'Soiling':'The act of "fecal soiling" in one\'s underwear, pants or clothes, or having another character perform such actions.',
        'Swallowing Feces':'Engaging in an RP in which a character will orally consume fecal matter.',
        'Swallowing Urine':'Engaging in an RP in which a character will orally consume urine.',
        'Swallowing Vomit':'Engaging in an RP in which a character will orally consume vomit.',
        'Vomiting':'The act of vomiting, being vomited upon, consuming vomit or otherwise including vomit in the sexual context of an RP; typically in a BDSM context.',
        'Watersports':'Pertains to the inclusion of urine, or the expelling of urine, in any form, in the sexual context of an RP.',
        'Wetting':"The act of urinating in one's underwear, pants or clothes, or having another character urinate onto a person who is clothed to any degree."
    },
    'Pain':{
        'Light pain':'Refers to the inclusion of light physical pain due to acts which are directly sexual.',
        'Heavy pain':'Refers to the inclusion of heavy physical pain due to acts which are directly sexual; typically rough or excessive penetrations. This is probably gonna leave a mark.',
        'Nipple clamps':'pressure device applied to nipples to create pain which produces pleasure.',
        'Clothes pins':'Pinching sking between the forks of a clothes pin',
        'Caning':'Caning is a technique used in BDSM in which the dominant repeatedly strikes the submissive with a long flexible cane, usually on the buttocks.',
        'Flogging':'The use of toys, typically associated with BDSM and domination/submission, being employed against a submissive or bottom, particularly referring to contact play involving whips of any type, riding crops, paddles or flogs.',
        'Gagging / Choking':'Being made to gag or choke, either by objects inserted into the mouth or hands/objects around the neck.',
        'Beating':'Being struck with fists or other objects',
        'Spanking':'The act of striking the buttocks of another character, or being the recipient of such; often as a form of erotic foreplay or as punishment in a BDSM setting.',
        'Cock/Pussy slapping':'slapping the genitalia of your partner, or receiving such slaps',
        'Cock/Pussy torture':"Engaging in an RP in which at least one character's genitals will be given negative attention, the intent of which to be to cause physical pain.",
        'Hot Wax':'The act of using wax, typically hot candle wax, as a form of sexual stimulation and/or torture, or receiving such actions.',
        'Scratching':'One character scratching another with their nails or claws, sometimes leaving marks; sometimes but not necessarily painful.',
        'Biting':'The act of biting or being bitten; sometimes painful, sometimes playful.',
        'Cutting':'The act of cutting a partner to cause pain in a sexual context.',
        'Snuff':'Murder a character as part of sex.',
        'Ballbusting':'Harm to the testicles, usually for sexual pleasure.',
        '3+ Penetration':'The act of penetrating a single character with three or more objects, including but not limited to the penis, sex toys, fist etc., or receiving such actions.',
        'Anal Prolapse':'Where insides of the anus are pulled out by force (unnatural means, such as a cream, liquid or suction method or internal massage) or naturally (either by a cock, dildo, or pushing)',
        'Breast Smothering':"The act of smothering a character using one's breasts, making it hard to breathe.",
        'Breath Control':'A situation in which at least one character will have physical control over the breathing habits of another character, often by either intermittent choking and/or due to the penetration of the throat.',
        'Choking':"A situation in which one character will control another character's breath with extreme force, and typically for extended and/or dangerous periods of time.",
        'Cock/Ball Smothering':'The act of smothering a character with a cock and/or balls, making it difficult to breathe.',
        'Cock Fucking':"The act of inserting one's penis into another penis and thrusting into it as if it were a more traditional orifice.",
        'Hair Pulling':"The act of pulling or tugging on another character's hair, or being the recipient of such."
    },
    'Blood & Gore / Torture / Death':{
        'Abrasions':'Engaging in a situation in which at least one character will receive abrasions, defined as scrapes that are at their mildest in severity capable of causing bleeding; typically administered via rough or coarse objects, such as sandpaper or cement.',
        'Bloodplay':'Pertains to the inclusion of blood or the retrieval of blood in any form in a sexual context, or engaging in acts which will draw blood.',
        'Breast/Nipple Torture':"A situation in which at least one character's breasts or nipples will be the subject of physical, non-sexual pain of an extended duration.",
        'Burning':'A situation in which at least one character will be burned.',
        'Castration':'An action where the testicles are removed or disabled, whether by surgical, chemical or magical means; sometimes also refers to removing or disabling the ovaries in those who have them.',
        'Death':'A situation in which a character will die at any point by any means.',
        'Emasculation':'The act whereby the genitalia are removed by magical or surgical means, usually the penis and/or the testicles. May also imply humiliation; e.g. to render a male less of a man.',
        'Genital Torture':"Engaging in an RP in which at least one character's genitals will be given negative attention, the intent of which to be to cause physical pain.",
        'Impalement':'Engaging in the act of being penetrated by an object from one orifice and having it extend out of another orifice in a typically non-fatal manner.',
        'Menses':'Engaging in an RP in which female menstruation will be applied to the sexual context of a scene.',
        'Mutilation':'The act of physically damaging or otherwise causing irreparable change and/or harm to a character in an RP, typically by the use of cutting, stabbing or contact objects; often exceptionally painful.',
        'Necrophilia':'The act of having sex with a dead, or otherwise unconscious or inanimate, character that was once alive, or, theoretically, receiving such actions.',
        'Non-Sexual Pain':"Refers to either the administering and/or receiving of pain that is not derived through sexual activity and does not cause sexual gratification for the recipient, often interpreted to mean pain that is located in non-sexual parts of one's body.",
        'Nonsexual Torture':'The act of causing or receiving extended scenes of pain due to acts that are not of a sexual nature, or giving or being the recipient of psychological abuse for extended periods of time or at a great degree of intensity.',
        'Nullification':'The removal of any body part.',
        'Piercing':"The act of piercing a character's body, typically in a painful manner, and often in a sexual or exceptionally sensitive location on the person's body, or having one's own body pierced.",
        'Sexual Torture':'Torture that is sexual in nature, or greatly harms one sexually.',
        'Swallowing Blood':'The act of orally consuming blood.'
    },
    'Meta':{
        'First Person':None,
        'Third Person':None,
        'Short Post Length (~1-3 sentences)':None,
        'Medium Post Length (~3-7 sentences)':None,
        'Long Post Length (~2-4 paragraphs)':None,
        'Story (3+ paragraphs)':None,
        'Dynamic Post Length':None
    },
    'Time-Scale':{
        'Short-Term Scenes':None,
        'Medium-Term Scenes':None,
        'Long-Term Scenes':None,
        'Quick Replies (0~10 mins)':None,
        'Fast Replies (10~30 mins)':None,
        'Normal Replies (30min ~ 2hours)':None,
        'Slow Replies (2~8 hours)':None,
        'Glacial Replies (8-24 hours)':None,
        'Occasional Replies (24+ hours)':None
    }
}

kink_splits = {
    'Body Part': ['Small', 'Large'],
    'Bodies': ['General'],
    'Clothing': ['Self', 'Partner'],
    'Pairings': ['Self', 'Partner'],
    'General': ['Giving', 'Receiving'],
    'General 2': ['Giving', 'Receiving'],
    'Oral Sex': ['Giving', 'Receiving'],
    'Ass play': ['Giving', 'Receiving'],
    'Restrictive': ['Self', 'Partner'],
    'Toys': ['Self', 'Partner'],
    'Domination': ['As Dominant', 'As Submissive'],
    'No consent': ['Aggressor', 'Target'],
    'Taboo': ['General'],
    'Surrealism': ['Self', 'Partner'],
    'Vore / Unbirth': ['Predator', 'Prey'],
    'Fluids': ['Giving', 'Receiving'],
    'Touch & Stimulation': ['Actor', 'Subject'],
    'Misc. Fetish': ['Giving', 'Receiving'],
    'Cum-related': ['General'],
    'BDSM & Related': ['As Dominant', 'As Submissive'],
    'Watersports / Scat': ['General'],
    'Pain': ['Giving', 'Receiving'],
    'Blood & Gore / Torture / Death': ['General'],
    'Meta': ['Self', 'Partner'],
    'Time-Scale': ['Self', 'Partner']
}

_all_kinks = [kink for cat in kinklist for kink in kinklist[cat]]
_rev_kinks = {kink: cat for cat in kinklist for kink in kinklist[cat]}

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

_flist_url_prog = re.compile(r"(https?://)?www.f-list.net/c/(.+)")

_flist_conversion = {
    'Fave': ratings.Favorite.value,
    'Yes': ratings.Like.value,
    'Maybe': ratings.Maybe.value,
    'No': ratings.No.value
}

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

def _similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

class KinklistScrollableView(discord.ui.View):
    def __init__(self, database: db.database, utils: bot_utils.utils, interaction: discord.Interaction, user: discord.Member):
        super().__init__()
        self.database = database
        self.utils = utils
        self.interaction = interaction
        self.user = user
        self.selected_categories = ["All"]
        self.selected_ratings = ["All"]
        self.position = 0 # TODO use buttons to scroll position

        self.add_item(KinklistCategoryDropdown(self))
        self.add_item(KinklistRatingDropdown(self))

        # Query all data and keep it prepared
        self.userdata = {}
        for rat, dataset in self.database.iterate_kinks(self.user.id, [ratings.Favorite.value, ratings.Like.value, ratings.Okay.value, ratings.Maybe.value, ratings.No.value]):
            if len(dataset) == 0: continue
            self.userdata[rat] = {}
            for _kink, _conditional, _category in dataset:
                if _category not in self.userdata[rat]:
                    self.userdata[rat][_category] = {}
                if _kink not in self.userdata[rat][_category]:
                    self.userdata[rat][_category][_kink] = []
                self.userdata[rat][_category][_kink] += [_conditional]
        # logger.debug(f"[__init__] userdata = {self.userdata}")

    async def on_category_updates(self, selected_categories: typing.List[str], interaction: discord.Interaction):
        self.selected_categories = selected_categories
        await self.edit_original()
        await _silent_reply(interaction)

    async def on_rating_updates(self, selected_ratings: typing.List[str], interaction: discord.Interaction):
        self.selected_ratings = selected_ratings
        await self.edit_original()
        await _silent_reply(interaction)

    async def edit_original(self):
        embed = self.render_kinks()
        await self.interaction.edit_original_response(embed=embed, view=self)

    async def validate_interaction(self, interaction: discord.Interaction):
        valid = self.interaction.user.id == interaction.user.id
        if not valid:
            await self.utils.safe_send(interaction, content="This interaction is not yours, silly~")
        return valid

    def render_kinks(self):
        embed = discord.Embed(
            colour=random.choice(bot_utils.EMBED_COLORS),
            timestamp=datetime.datetime.now()
        )
        
        embed.set_footer(text=f'ID: {self.interaction.user.id}')

        logger.debug(f"[render_kinks] selected_ratings = {self.selected_ratings}")
        logger.debug(f"[render_kinks] selected_categories = {self.selected_categories}")
        
        try:
            icon_url = self.interaction.user.avatar.url
        except Exception as e:
            logger.warning(f"Exception while trying to handle icon thumbnail: {e}\n{traceback.format_exc()}")
            icon_url = None

        embed.set_author(name=f'{self.interaction.user}\'s kinklist', icon_url=icon_url)

        hit = False
        for rating in self.userdata:
            if len(self.userdata[rating]) == 0: continue
            if (rating not in self.selected_ratings) and ("All" not in self.selected_ratings): 
                # logger.debug(f"[render_kinks] skip rating {rating}")
                continue
            entries = 0
            content = ''
            content_len = 0
            filled = False
            for cat in self.userdata[rating]:
                if filled: break
                if len(self.userdata[rating][cat]) == 0: continue
                if (cat not in self.selected_categories) and ("All" not in self.selected_categories): 
                    # logger.debug(f"[render_kinks] skip cat {cat}")
                    continue
                for kink in self.userdata[rating][cat]:
                    if filled: break
                    if len(self.userdata[rating][cat][kink]) == len(kink_splits[cat]):
                        elem = f'`{kink}`'
                        if entries > 0:
                            elem = f', {elem}'
                        len_elem = len(elem)
                        if content_len + len_elem < 1019:
                            entries += 1
                            content += elem
                            content_len += len_elem
                        else:
                            content += ', ...'
                            filled = True
                        continue

                    for conditional in self.userdata[rating][cat][kink]:
                        elem = f'`{kink} ({conditional})`'
                        if entries > 0:
                            elem = f', {elem}'
                        len_elem = len(elem)
                        if content_len + len_elem < 1019:
                            entries += 1
                            content += elem
                            content_len += len_elem
                        else:
                            content += ', ...'
                            filled = True
            if len(content) > 0: # Prevent errors from empty fields (discord.errors.HTTPException: 400 Bad Request (error code: 50035): Invalid Form Body - In embeds.0.fields.3.value: This field is required) 
                embed.add_field(name=f"{rating_emojis[ratings(rating)]} {self.utils.plural(ratings(rating).name, entries)}", value=content, inline=False)
                hit = True

        if not hit:
            embed.add_field(name=f"No data?", value="I couldn't find any data matching those, chief... Choose something else and try again~", inline=False)

        return embed

class KinklistCategoryDropdown(discord.ui.Select):
    def __init__(self, watcher: KinklistScrollableView):
        self.watcher = watcher
        self.selected = []
        self.selected_all = True # TODO fix ALL
        options = [discord.components.SelectOption(label=cat, default=True) for cat in kinklist]
        logger.debug(f"There are {len(options)} options")
        super().__init__(placeholder=f"Filter by category", min_values=1, max_values=len(options), options=options, disabled=False)

    def _update_selected(self):
        if "All" in self.values:
            if self.selected_all: # All was already previously selected, remove it
                self.values.remove("All")
                self.selected_all = False
            else: # All was just selected, remove all but it
                self.values = ["All"]
                self.selected_all = True
        for opt in self.options:
            opt.default = opt.label in self.values

    async def callback(self, interaction: discord.Interaction):
        if not await self.watcher.validate_interaction(interaction): return
        self._update_selected()
        await self.watcher.on_category_updates(self.values, interaction)

class KinklistRatingDropdown(discord.ui.Select):
    def __init__(self, watcher: KinklistScrollableView):
        self.watcher = watcher
        # self.selected_all = True
        options = [discord.components.SelectOption(label="All", default=True)] + [discord.components.SelectOption(label=rat.name, emoji=rating_emojis[rat]) for rat in ratings if rat != ratings.Unknown]
        super().__init__(placeholder=f"Filter by interest", min_values=1, max_values=len(options), options=options, disabled=False)

    def _update_selected(self):
        # if "All" in self.values:
            # if self.selected_all: # All was already previously selected, remove it
            #     self.values.remove("All")
            #     self.selected_all = False
            # else: # All was just selected, remove all but it
                # self.values = ["All"] # AttributeError: can't set attribute 'values'
                # self.selected_all = True
        for opt in self.options:
            opt.default = opt.label in self.values

    async def callback(self, interaction: discord.Interaction):
        if not await self.watcher.validate_interaction(interaction): return
        self._update_selected()
        aux = ["All"] if "All" in self.values else [ratings[v].value for v in self.values]
        await self.watcher.on_rating_updates(aux, interaction)

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
            await interaction.response.send_message(content=f"Noted! You may continue adding new kinks with the same menu, and I'll keep track of everything~\nAnd you can always remove a kink from your list by setting it back to {rating_emojis[ratings.Unknown]}{ratings.Unknown.name}", ephemeral=True)
            self._notified_explanation = True
        else:
            await _silent_reply(interaction)

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
    def __init__(self):
        super().__init__()

def safe_name(id: str):
    return id.lower().replace('&', '').replace('/', ' ').replace('  ', ' ').replace('  ', ' ').replace(' ', '-').replace('.', '')

def _make_kink_cmd(database, utils, category):
    @discord.app_commands.command(name=safe_name(category), description=f'Manage {category.lower()}-related kinks')
    async def _test(interaction: discord.Interaction):
        logger.info(f"Got kink {category} request from {interaction.user.id}")
        await utils.safe_send(interaction, view=KinksView(category, interaction, database), ephemeral=True)
    return _test

def get_kink_cmds(database, utils):
    cmds = Kink()
    for category in kinklist:
        cmds.add_command(_make_kink_cmd(database, utils, category))
        logger.debug(f"Added '{category}' to group class as '{safe_name(category)}'")
    return cmds

@discord.app_commands.guild_only()
class Kinklist(discord.app_commands.Group):
    def __init__(self, database: db.database, utils: bot_utils.utils):
        super().__init__()
        self.database = database
        self.utils = utils
    
    @discord.app_commands.command(description='Hide or show your kink list', nsfw=True)
    @discord.app_commands.choices(visibility=[discord.app_commands.Choice(name=b, value=b) for b in ['public', 'private']])
    async def manage(self, interaction: discord.Interaction, visibility: discord.app_commands.Choice[str]):
        logger.info(f"{interaction.user} requested kinklist manage: {visibility.value}")

        self.database.set_kinklist_visibility(interaction.user.id, visibility.value == 'public')

        if visibility.value == 'public':
            content = "Okay, now people will be able to see your kink list!"
        else:
            content = "Okay, your kinklist is now private and only you will be able to see it!"

        await self.utils.safe_send(interaction, content=content, ephemeral=True)
    
    @discord.app_commands.command(description='[Beta] Get someone\'s kink list', nsfw=True)
    @discord.app_commands.describe(user='Whose list to get (gets yours by default)', public='Whether to let everyone see it or only you (if the list is not yours, it will be hidden anyway)')
    async def showbeta(self, interaction: discord.Interaction, user: typing.Optional[discord.Member]=None, public: typing.Optional[bool]=False):
        user = user or interaction.user
        logger.info(f"{interaction.user} requested kink list: {user}")

        is_own = user.id == interaction.user.id

        is_public = self.database.get_kinklist_visibility(user.id)

        if not is_own and not is_public:
            await self.utils.safe_send(interaction, content=f"{user.mention}'s kinklist is currently private, you can ask them personally for it~", ephemeral=True)
            return

        if self.database.count_kinks(user.id, ratings.Unknown.value) == 0:
            await self.utils.safe_send(interaction, content=f"I couldn't find anything about " + ("you" if is_own else f"{user.mention}"), ephemeral=not (is_own and is_public and public))
            return

        view = KinklistScrollableView(self.database, self.utils, interaction, user)
        await self.utils.safe_send(interaction, view=view, embed=view.render_kinks(), ephemeral=not (is_own and is_public and public))

    @discord.app_commands.command(description='Get someone\'s kink list', nsfw=True)
    @discord.app_commands.describe(user='Whose list to get (gets yours by default)')
    async def show(self, interaction: discord.Interaction, user: typing.Optional[discord.Member]=None):
        user = user or interaction.user
        logger.info(f"{interaction.user} requested kink list: {user}")

        is_own = user.id == interaction.user.id

        is_public = self.database.get_kinklist_visibility(user.id)

        if not is_own and not is_public:
            await self.utils.safe_send(interaction, content=f"{user.mention}'s kinklist is currently private, you can ask them personally for it~", ephemeral=True)
            return

        kinks = {}
        for rat, dataset in self.database.iterate_kinks(user.id, [ratings.Favorite.value, ratings.Like.value, ratings.Okay.value, ratings.Maybe.value, ratings.No.value]):
            if len(dataset) == 0: continue
            kinks[rat] = {}
            for _kink, _conditional, _category in dataset:
                if _category not in kinks[rat]:
                    kinks[rat][_category] = {}
                if _kink not in kinks[rat][_category]:
                    kinks[rat][_category][_kink] = []
                kinks[rat][_category][_kink] += [_conditional]

        if len(kinks) == 0:
            await self.utils.safe_send(interaction, content=f"I couldn't find anything about " + ("you" if is_own else f"{user.mention}"), ephemeral=not (is_own and is_public))
            return

        embed = discord.Embed(
            colour=random.choice(bot_utils.EMBED_COLORS),
            timestamp=datetime.datetime.now()
        )
        
        embed.set_footer(text=f'ID: {user.id}')
        
        try:
            icon_url = user.avatar.url
        except Exception as e:
            logger.warning(f"Exception while trying to handle icon thumbnail: {e}\n{traceback.format_exc()}")
            icon_url = None

        embed.set_author(name=f'{user}\'s kinklist', icon_url=icon_url)

        # for rating in aux:
        #     if len(aux[rating]) == 0: continue
        #     embed.add_field(name=f"{rating_emojis[ratings[rating]]} {self.utils.plural(rating, len(aux[rating]))}", value=", ".join(aux[rating]), inline=False)

        for rating in kinks:
            if len(kinks[rating]) == 0: continue
            entries = 0
            content = ''
            content_len = 0
            filled = False
            for cat in kinks[rating]:
                if filled: break
                if len(kinks[rating][cat]) == 0: continue
                for kink in kinks[rating][cat]:
                    if filled: break
                    if len(kinks[rating][cat][kink]) == len(kink_splits[cat]):
                        elem = f'`{kink}`'
                        if entries > 0:
                            elem = f', {elem}'
                        len_elem = len(elem)
                        if content_len + len_elem < 1019:
                            entries += 1
                            content += elem
                            content_len += len_elem
                        else:
                            content += ', ...'
                            filled = True
                        continue

                    for conditional in kinks[rating][cat][kink]:
                        elem = f'`{kink} ({conditional})`'
                        if entries > 0:
                            elem = f', {elem}'
                        len_elem = len(elem)
                        if content_len + len_elem < 1019:
                            entries += 1
                            content += elem
                            content_len += len_elem
                        else:
                            content += ', ...'
                            filled = True
            # logger.debug(f"Adding {rating} field with content={content}")
            embed.add_field(name=f"{rating_emojis[ratings(rating)]} {self.utils.plural(ratings(rating).name, entries)}", value=content, inline=False)

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

        await self.utils.safe_send(interaction, content=content, ephemeral=True)

    @discord.app_commands.command(description='Calculate your kink compatibility matrix with someone else', nsfw=True)
    @discord.app_commands.describe(user='Whose kinks to compare yours with')
    async def matrix(self, interaction: discord.Interaction, user: discord.Member):
        logger.info(f"Got kink compatibility matrix request from {interaction.user.id}: '{user}'")

        if interaction.user.id == user.id:
            await self.utils.safe_send(interaction, content=f"Try choosing someone other than yourself~", ephemeral=True)
            return

        if user.bot:
            await self.utils.safe_send(interaction, content=f"That user is a bot~", ephemeral=True)
            return

        if not self.database.get_kinklist_visibility(user.id):
            await self.utils.safe_send(interaction, content=f"{user.mention}'s kinklist is currently private~", ephemeral=True)
            return

        await self.utils.safe_defer(interaction)
        
        con = sqlite3.connect(db.kinks_db_file)
        cur = con.cursor()
        try:
            data = cur.execute("""
            SELECT rating1, rating2, COUNT(*) FROM (
                SELECT 
                    k2.kink||";"||k2.conditional||";"||k2.category AS tag, 
                    k1.rating AS rating1, 
                    k2.rating AS rating2
                FROM kinks k1 
                INNER JOIN kinks k2 
                ON 
                    k1.kink == k2.kink AND 
                    k1.conditional == k2.conditional AND 
                    k1.category == k2.category 
                WHERE 
                    k1.user = :user1 AND 
                    k2.user = :user2
            ) GROUP BY rating1, rating2;
            """, {"user1": interaction.user.id, "user2": user.id}).fetchall()
        except sqlite3.OperationalError:
            data = []
        con.close()

        if len(data) == 0:
            await self.utils.safe_send(interaction, content=f"I couldn't find any similarities between your lists...", is_followup=True, send_anyway=True)
            return

        mat = np.zeros((5,5))
        for i, j, n in data:
            mat[i-1][j-1] = n

        plt.figure(figsize = (10,8))
        labels = ['💖', '😊', '🙂', '😕', '💀']
        fig = sn.heatmap(mat, annot=True, vmin=0, cmap=sn.color_palette("plasma", as_cmap=True), xticklabels=labels, yticklabels=labels)
        for tick in fig.get_xticklabels():
            # tick.set_fontname("Segoe UI Emoji")
            tick.set_fontproperties(emoji_font)
            tick.set_fontsize(30)
        for tick in fig.get_yticklabels():
            # tick.set_fontname("Segoe UI Emoji")
            tick.set_fontproperties(emoji_font)
            tick.set_fontsize(30)
            tick.set_rotation(0)
        fig.invert_yaxis()
        fig.set_title(f'Kink similarities between {interaction.user}\nand {user}')
        sn.set(font_scale=2)

        name = "trash/" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=30)) + ".png"
        plt.savefig(name)
        report_file = discord.File(name, filename=f"user_matrix.png")

        await self.utils.safe_send(interaction, file=report_file, is_followup=True, send_anyway=True)

        os.remove(name)

    @discord.app_commands.command(description='Calculate your kink compatibility with someone else', nsfw=True)
    @discord.app_commands.describe(user='Whose kinks to compare yours with')
    async def compatibility(self, interaction: discord.Interaction, user: discord.Member):
        logger.info(f"Got kink compatibility request from {interaction.user.id}: '{user}'")

        if interaction.user.id == user.id:
            await self.utils.safe_send(interaction, content=f"Try choosing someone other than yourself~", ephemeral=True)
            return

        if user.bot:
            await self.utils.safe_send(interaction, content=f"That user is a bot~", ephemeral=True)
            return

        if not self.database.get_kinklist_visibility(user.id):
            await self.utils.safe_send(interaction, content=f"{user.mention}'s kinklist is currently private~", ephemeral=True)
            return

        author_kinks = {f"{kink[1]}|{kink_splits[kink[3]].index(kink[2])}|{kink[3]}": kink[4] 
            for kink in self.database.get_kinks(interaction.user.id, ratings.Unknown.value)}
        user_kinks = {f"{kink[1]}|{len(kink_splits[kink[3]]) - kink_splits[kink[3]].index(kink[2]) - 1}|{kink[3]}": kink[4] # Math magic to flip conditional if needed
            for kink in self.database.get_kinks(user.id, ratings.Unknown.value)}
        
        common = set(author_kinks.keys()).intersection(user_kinks.keys())

        if len(common) == 0:
            await self.utils.safe_send(interaction, content=f"You have no kinks in common with {user.mention}...", send_anyway=True)
            return

        score = 0
        for kink in common:
            score += 5 - max(author_kinks[kink], user_kinks[kink])
            logger.debug(f"Analyzing kink {kink} -> {author_kinks[kink]} vs {user_kinks[kink]} -> new score={score}")
        score /= 4 * len(common)
        score = int(score * 100)

        await self.utils.safe_send(interaction, content=f"{interaction.user.mention}'s kinklist is {score}% compatible with {user.mention}'s~", send_anyway=True)

    @discord.app_commands.command(description='[BETA] Import your f-list (be aware this may overwrite some of your current ratings)')
    @discord.app_commands.describe(url='Your f-list link (e.g. www.f-list.net/c/xyz)')
    # @discord.app_commands.choices(confirmation=[discord.app_commands.Choice(name=b, value=b) for b in ['I understand', 'Cancel']])
    async def import_flist(self, interaction: discord.Interaction, url: str):
        logger.info(f"Got kink import_flist request from {interaction.user.id}: '{url}'")

        _regexed = _flist_url_prog.search(url)
        if _regexed is None:
            await self.utils.safe_send(interaction, content=f"That's not a valid f-list link", ephemeral=True)
            return

        await self.utils.safe_send(interaction, content=f"Fetching your f-list...", ephemeral=True)

        _username = _regexed.group(2)

        r = requests.get(f"https://www.f-list.net/c/{_username}", cookies={'warning':'1'})
        if r.status_code != 200:
            logger.warning(f"Error {r.status_code} for {_username} flist")
            await interaction.edit_original_response(content=f"I got an error ({r.status_code}) while trying to fetch your f-list... :c")
            return

        self.database.create_or_update_flist(interaction.user.id, _username)

        await interaction.edit_original_response(content=f"F-list downloaded, parsing...")

        soup = BeautifulSoup(r.text, 'html.parser')
        rev_comp = {}
        for flist in _flist_conversion:
            rat = _flist_conversion[flist]
            for fave in soup.find(id=f'Character_Fetishlist{flist}').find_all('a'):
                aux = fave.text.strip()
                this = max([(kink, _similar(aux.lower(), kink.lower()), rat) for kink in _all_kinks], key=lambda x: x[1])
                matched = this[0]
                if (matched not in rev_comp) or (this[1] > rev_comp[matched][1]):
                    rev_comp[matched] = (aux, this[1], rat)
        logger.debug(f"Reverse list[{len(rev_comp)}] = {rev_comp}")

        await interaction.edit_original_response(content=f"F-list parsed, filtering matches...")

        matches = [(kink, rev_comp[kink][2]) for kink in rev_comp if rev_comp[kink][1] > 0.95]
        logger.debug(f"Matches[{len(matches)}] = {matches}")

        await interaction.edit_original_response(content=f"F-list filtered, updating kinks...")

        for kink, rating in matches:
            cat = _rev_kinks[kink]
            for split in kink_splits[cat]:
                # logger.debug(f"Updating -> {interaction.user.id}, [{kink}], [{split}], [{cat}] = {rating}")
                self.database.create_or_update_kink(interaction.user.id, kink, split, cat, rating)

        await interaction.edit_original_response(content=f"All done! I've imported {len(matches)} kinks from your f-list~")
