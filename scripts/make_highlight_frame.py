"""Highlight letterbox overlay: transparent 1920x1080 PNG with cinematic bars and a '● 하이라이트 미리보기' tag."""
import sys
from PIL import Image, ImageDraw, ImageFont
out, font = sys.argv[1], sys.argv[2]
W, H, BAR = 1920, 1080, 100
im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
d.rectangle([0, 0, W, BAR], fill=(0, 0, 0, 255))
d.rectangle([0, H - BAR, W, H], fill=(0, 0, 0, 255))
f = ImageFont.truetype(font, 38)
cy = BAR // 2
d.ellipse([60, cy - 11, 82, cy + 11], fill=(235, 45, 45, 255))
d.text((100, cy), '하이라이트 미리보기', font=f, fill=(255, 255, 255, 255), anchor='lm')
im.save(out)
print('saved', out)
