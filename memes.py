import sys
import random
import string
from PIL import Image, ImageDraw, ImageFont

sup_template = "meme_stuff/supremacy_template.png"
nuts_template = "meme_stuff/nuts_template.png"
pills_template = "meme_stuff/pills_template.png"

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