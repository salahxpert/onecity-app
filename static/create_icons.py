from PIL import Image, ImageDraw, ImageFont
import os

def create_icon(size, filename):
    img = Image.new('RGB', (size, size), color=(13, 110, 253))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", size//2)
    except:
        font = ImageFont.load_default()
    text = "OC"
    bbox = d.textbbox((0,0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    d.text(((size-w)//2, (size-h)//2), text, fill=(255,255,255), font=font)
    img.save(filename)
    print(f"Created {filename}")

create_icon(192, "icon-192.png")
create_icon(512, "icon-512.png")