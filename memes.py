import datetime
import os
import random
import re
import requests
import string
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

memes_folder = "meme_stuff"

sup_template = f"{memes_folder}/supremacy_template.png"
nuts_template = f"{memes_folder}/nuts_template.png"
pills_template = f"{memes_folder}/pills_template.png"
needs_template = f"{memes_folder}/needs_template.png"
bingo_template = f"{memes_folder}/bingo_template.png"
no_horny = f"{memes_folder}/no_horny.png"

use_pilmoji = False
if use_pilmoji:
    from pilmoji import Pilmoji

string_len = 20

def get_bingos():
    return [file[:-4] for file in os.listdir(f"{memes_folder}/bingos") if file[-4:] == ".png"]

def bingo_filepath(name):
    if name[-4:] != ".png": name += ".png"
    return f"{memes_folder}/bingos/{name}"

def get_wrapped_text(text: str, font: ImageFont.ImageFont,
                     line_length: int, do_strip: bool):
        lines = ['']
        for word in text.split():
            line = f'{lines[-1]} {word}'.strip() if do_strip else f'{lines[-1]} {word}'
            if font.getlength(line) <= line_length:
                lines[-1] = line
            else:
                lines.append(word)
        while len(lines[0]) == 0:
            lines = lines[1:]
        # print(f"wrapped lines = {lines}")
        return '\n'.join(lines)

def get_max_size(text: str, font_family: str, bbox: tuple, draw_ctx: ImageDraw.Draw, align: str):
    sz = 2
    _txt = re.sub(r'[^\x00-\x7F]','m', text)
    while True:
        fnt = ImageFont.truetype(font_family, sz)
        wrapped = get_wrapped_text(_txt, fnt, bbox[0], True)
        new_bbox = draw_ctx.textbbox((0,0), wrapped, font=fnt, align=align)
        # print(f"new bbox {sz} = {new_bbox}")
        if (new_bbox[2] > bbox[0]) or (new_bbox[3] > bbox[1]):
            return sz - 2
        sz += 2

def draw_text_with_bbox(text: str, font_family: str, center_anchor: tuple, bbox: tuple, draw_ctx: ImageDraw.Draw, img):
    use_emoji = re.search(r"[^\x00-\x7f]", text) is not None
    _align = 'left' if use_emoji else 'center'
    sz = get_max_size(text, font_family, bbox, draw_ctx, _align)
    fnt = ImageFont.truetype(font_family, sz)
    if use_pilmoji and use_emoji:
        _bbox = draw_ctx.textbbox((0,0), get_wrapped_text(text, fnt, bbox[0], False), font=fnt, align=_align)
        _anchor = (center_anchor[0], int(center_anchor[1] - _bbox[3]/2))
        # _txt = re.sub(r'[^\x00-\x7F]',' ', text)
        with Pilmoji(img) as pilmoji:
            pilmoji.text(_anchor, get_wrapped_text(text, fnt, bbox[0], False), font=fnt, anchor="mm", fill=(0, 0, 0, 255), align=_align, emoji_position_offset=(int(-_bbox[2]/4), int(-_bbox[3]/4)))
    else:
        draw_ctx.text(center_anchor, get_wrapped_text(text, fnt, bbox[0], True), font=fnt, anchor="mm", fill=(0, 0, 0, 255), align=_align)

def paste_centered(icon, ic_size, base, pos):
    with Image.open(icon) as ic:
        base.paste(ic.resize(ic_size), (pos[0] - ic_size[0]//2, pos[1] - ic_size[1]//2))

def generate_sup(text, icon):

    ic_size = (300, 300)
    
    with Image.open(sup_template) as im:

        draw = ImageDraw.Draw(im)

        draw_text_with_bbox(text, "arial.ttf", (im.size[0]//2, 310), (2*im.size[0]//3, 150), draw, im)
        
        paste_centered(icon, ic_size, im, (150, im.size[1]//2))

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
        
        paste_centered(icon, (150, 150), im, (250, 220))

        # write to stdout
        name = "trash/" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=string_len)) + ".png"
        im.save(name, "PNG")

    return name

def generate_needs(text):
    with Image.open(needs_template) as im:

        draw = ImageDraw.Draw(im)

        draw_text_with_bbox(text, "arial.ttf", (377, 402), (210, 280), draw, im)

        # write to stdout
        name = "trash/" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=string_len)) + ".png"
        im.save(name, "PNG")

    return name

def generate_custom_bingo(name, items):
    bingo_cell = (200, 200)
    bingo_spacing = 227
    bingo_start = (145, 446)
    name_y = 105
    name_bbox = (1136, 155)
    font = "arial.ttf"
    with Image.open(bingo_template) as im:

        draw = ImageDraw.Draw(im)

        draw_text_with_bbox(f"{name}'s bingo~", font, (im.size[0]//2, name_y), name_bbox, draw, im)

        _lin = 0
        _col = 0
        coords = bingo_start
        for i in range(12):
            draw_text_with_bbox(items[i], font, coords, bingo_cell, draw, im)
            _col += 1
            if _col == 5:
                _col = 0
                _lin += 1
                coords = (bingo_start[0], coords[1] + bingo_spacing)
            else:
                coords = (coords[0] + bingo_spacing, coords[1])
                
        draw_text_with_bbox("Free space~", font, coords, bingo_cell, draw, im)
        coords = (coords[0] + bingo_spacing, coords[1])
        _col += 1

        for i in range(12):
            draw_text_with_bbox(items[i + 12], font, coords, bingo_cell, draw, im)
            _col += 1
            if _col == 5:
                _col = 0
                _lin += 1
                coords = (bingo_start[0], coords[1] + bingo_spacing)
            else:
                coords = (coords[0] + bingo_spacing, coords[1])

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