import datetime
import random
import re
import requests
import string
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

sup_template = "meme_stuff/supremacy_template.png"
nuts_template = "meme_stuff/nuts_template.png"
pills_template = "meme_stuff/pills_template.png"
no_horny = "meme_stuff/no_horny.png"

string_len = 20

def _paste_centered(icon, ic_size, base, pos):
    with Image.open(icon) as ic:
        base.paste(ic.resize(ic_size), (pos[0] - ic_size[0]//2, pos[1] - ic_size[1]//2))

def generate_sup(text, icon):

    ic_size = (300, 300)
    
    with Image.open(sup_template) as im:

        draw = ImageDraw.Draw(im)

        # get a font
        fnt = ImageFont.truetype("arial.ttf", 75)
        # get a drawing context
        draw.text((im.size[0]//2, 310), text, font=fnt, anchor="ms", fill=(0, 0, 0, 255))
        
        with Image.open(icon) as ic:
            im.paste(ic.resize(ic_size), (70, im.size[1]//2 - ic_size[1]//2))

        # write to stdout
        name = "trash/" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=string_len)) + ".png"
        im.save(name, "PNG")

    return name

def generate_nuts(icon):

    with Image.open(nuts_template) as im:
        
        with Image.open(icon) as ic:
            im.paste(ic.resize((im.size[0]//2, im.size[1]//2)), (0, im.size[1]//2))

        # write to stdout
        name = "trash/" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=string_len)) + ".png"
        im.save(name, "PNG")

    return name

def generate_pills(icon):

    pos = (250, 220)

    with Image.open(pills_template) as im:
        
        _paste_centered(icon, (150, 150), im, (250, 220))

        # write to stdout
        name = "trash/" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=string_len)) + ".png"
        im.save(name, "PNG")

    return name

def percent_from(content, daily=True):
    if daily:
        content += f"/{datetime.datetime.now().strftime('%d/%m/%Y')}"
    pct = hash(content) % 101
    return (pct, " (nice!)" if pct == 69 else "")

dad_program = re.compile(r"im|i'm|i am|Im|I'm|I am")
def hi_dad(msg):
    res = dad_program.search(msg)
    if res is None: return None
    sp = res.span()
    words = msg[sp[0] + sp[1] + 1:].split()
    name = words[0]
    if (len(words) > 1):
        name += f" {words[1]}"
    return f"Hi {name}, I'm dad! :sunglasses:"

def get_formatted_definition(contents):
    clean_term = contents.replace(" ", "+")
    url = f"https://www.urbandictionary.com/define.php?term={clean_term}"

    definition = BeautifulSoup(requests.get(url).content, 'html.parser').find("div", {"class": "definition"})

    # Term itself
    word_txt = definition.find("div", {"class": "flex"}).text

    # Meaning
    meaning = definition.find("div", {"class": "meaning"})
    for elem in meaning.find_all(["br"]):
        elem.replace_with('\n')
    meaning_txt = meaning.text.replace("\n\n", "\n")
    meaning_txt = "".join([f"\t{line}\n" for line in meaning_txt.split("\n")]).rstrip()

    # Example
    example = definition.find("div", {"class": "example"})
    for elem in example.find_all(["br"]):
        elem.replace_with('\n')
    example_txt = example.text.replace("\n\n", "\n")
    example_txt = "".join([f"> {line}\n" for line in example_txt.split("\n")]).rstrip()

    return f"**{word_txt}**\n\n{meaning_txt}\n\n{example_txt}"