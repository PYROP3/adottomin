import sys
import random
import string
from PIL import Image, ImageDraw, ImageFont

sup_template = "meme_stuff/supremacy_template.png"
nuts_template = "meme_stuff/nuts_template.png"
ic_size = (300, 300)
string_len = 20

def generate_sup(text, icon):

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