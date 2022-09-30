import datetime
import os
import random
import re
import requests
import traceback
import string
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

memes_folder = "meme_stuff"

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
    if icon is None: return
    with Image.open(icon) as ic:
        base.paste(ic.resize(ic_size), (pos[0] - ic_size[0]//2, pos[1] - ic_size[1]//2))

# icon: icon, size, position
# text: text, bbox, position
_baserules = {
    "icon": lambda image, draw, args: paste_centered(args["icon"], args["size"], image, args["position"]),
    "text": lambda image, draw, args: draw_text_with_bbox(args["text"], "arial.ttf", args["position"], args["bbox"], draw, image)
}

def _args_icon(icon: str, size: tuple[int, int], position: tuple[int, int]):
    return ("icon", {"icon": icon, "size": size, "position": position})
    
def _args_text(text: str, bbox: tuple[int, int], position: tuple[int, int]):
    return ("text", {"text": text, "bbox": bbox, "position": position})

def automeme(template, rules):
    with Image.open(template) as im:
        draw = ImageDraw.Draw(im)
        # print(f"got rules={rules} for {template}")
        for (rule, args) in rules:
            # print(f"rule=[{rule}], args=[{args}]")
            try:
                _baserules[rule](im, draw, args)
            except Exception as e:
                # print(f"Error while trying to execute rule: {e}\n{traceback.format_exc()}")
                pass

        name = "trash/" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=string_len)) + ".png"
        im.save(name, "PNG")
    return name

def _args_for(id: str, icon: str=None, text=None):
    if id == "supremacy": return [_args_text(text, (800, 150), (600, 310)), _args_icon(icon, (300,300), (220, 563))], # (1200, 1127)
    if id == "deeznuts": return [_args_icon(icon, (598, 582), (0, 582))], # (1196, 1165)
    if id == "pills": return [_args_icon(icon, (150, 150), (250, 220))],
    if id == "bromeme": return [_args_icon(icon, (270, 270), (575, 205))], # (828, 807)
    if id == "needs": return [_args_text(text, (210, 280), (377, 402))],
    if id == "fivemins": return [_args_icon(icon, (150, 150), (244, 735))],
    if id == "custom_bingo": return [_args_text(f"{text[0]}'s bingo~", (1136, 155), (600, 105))] + [_args_text(f"{thing}", (200, 200), (145 + 227 * (idx % 5), 446 + 227 * (idx // 5))) 
                for idx, thing in enumerate(text[1:13] + ["Free space~"] + text[13:])] # (1200, 1499)

def create_meme(id: str, icon: str=None, text=None):
    return automeme(f"{memes_folder}/{id}_template.png", _args_for(id, icon=icon, text=text)[0])

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