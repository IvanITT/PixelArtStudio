"""Generates docs/assets/banner.png and logo.png for the README.

Run with the project virtual environment:
    backend\\.venv\\Scripts\\python.exe docs\\assets\\make_banner.py
"""
from __future__ import annotations

import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1280, 440
WHITE = (248, 250, 255)
MUTED = (197, 207, 222)
VIOLET = (139, 92, 246)
TEAL = (20, 184, 166)
AMBER = (245, 158, 11)
BLUE = (59, 130, 246)


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(r"C:\Windows\Fonts", name), size)


def build_banner() -> Image.Image:
    base = Image.new("RGB", (W, H), (9, 11, 17))
    draw = ImageDraw.Draw(base)
    for y in range(H):
        t = y / (H - 1)
        draw.line([(0, y), (W, y)], fill=(int(9 + t * 7), int(11 + t * 9), int(17 + t * 16)))

    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-220, -260, 560, 440], fill=(VIOLET[0], VIOLET[1], VIOLET[2], 38))
    gd.ellipse([780, 80, 1420, 640], fill=(TEAL[0], TEAL[1], TEAL[2], 28))
    gd.ellipse([560, -260, 1180, 260], fill=(AMBER[0], AMBER[1], AMBER[2], 16))
    glow = glow.filter(ImageFilter.GaussianBlur(80))
    img = Image.alpha_composite(base.convert("RGBA"), glow)
    draw = ImageDraw.Draw(img)

    for x in range(0, W, 24):
        draw.line([(x, 0), (x, H)], fill=(29, 34, 47, 255))
    for y in range(0, H, 24):
        draw.line([(0, y), (W, y)], fill=(29, 34, 47, 255))

    panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel)
    pd.rounded_rectangle([54, 30, 830, 404], radius=26, fill=(7, 9, 15, 188), outline=(49, 58, 78, 190), width=1)
    img = Image.alpha_composite(img, panel)
    draw = ImageDraw.Draw(img)

    draw.text((86, 54), "OFFLINE-FIRST  |  CPU-ONLY  |  LOCAL REST API", font=font("consolab.ttf", 13), fill=(167, 139, 250))
    draw.text((82, 88), "PIXEL ART", font=font("segoeuib.ttf", 64), fill=WHITE)
    draw.text((84, 162), "& GAME ASSET STUDIO", font=font("segoeuib.ttf", 35), fill=(196, 181, 253))
    draw.text((85, 226), "Turn photos and flat art into game-ready sprites,", font=font("segoeui.ttf", 20), fill=MUTED)
    draw.text((85, 255), "tilesets, animations and 2.5D assets - entirely local.", font=font("segoeui.ttf", 20), fill=MUTED)

    pills = [
        ("31 generators", TEAL),
        ("Style consistency", VIOLET),
        ("ES / EN", BLUE),
        ("Godot / Unity / RPG Maker", AMBER),
    ]
    x, py = 85, 302
    for text, color in pills:
        width = int(draw.textlength(text, font=font("segoeui.ttf", 13)) + 26)
        draw.rounded_rectangle(
            [x, py, x + width, py + 30],
            radius=15,
            fill=(color[0] // 4, color[1] // 4, color[2] // 4, 255),
            outline=(color[0], color[1], color[2], 170),
            width=1,
        )
        draw.text((x + 13, py + 6), text, font=font("segoeui.ttf", 13), fill=(226, 232, 242))
        x += width + 11

    draw.text((86, 365), "v1.0.0   |   Windows launcher   |   MIT License", font=font("consola.ttf", 12), fill=(143, 156, 176))

    sx, sy, sw, sh = 886, 66, 318, 308
    frame = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    fd = ImageDraw.Draw(frame)
    fd.rounded_rectangle([0, 0, sw, sh], radius=18, fill=(15, 18, 27, 245), outline=(52, 62, 82, 255), width=2)
    for i, color in enumerate([(244, 63, 94), (245, 158, 11), (34, 197, 94)]):
        fd.ellipse([14 + i * 16, 13, 21 + i * 16, 20], fill=color)
    fd.text((74, 10), "sprite_workshop.pas", font=font("consola.ttf", 12), fill=(118, 130, 150))

    for yy in range(238, 294):
        for xx in range(16, 302):
            color = (24, 29, 41, 255) if (((xx - 16) // 16 + (yy - 238) // 16) % 2 == 0) else (29, 35, 48, 255)
            fd.rectangle([xx, yy, xx + 15, yy + 15], fill=color)

    def block(x: int, y: int, w: int, h: int, color: tuple[int, int, int, int]) -> None:
        fd.rectangle([16 + x * 16, 56 + y * 16, 16 + (x + w) * 16 - 1, 56 + (y + h) * 16 - 1], fill=color)

    # tree
    block(3, 6, 2, 4, (120, 74, 44, 255))
    block(1, 3, 6, 2, (31, 122, 82, 255))
    block(2, 2, 4, 5, (45, 168, 108, 255))
    block(2, 2, 2, 2, (84, 210, 146, 255))
    block(5, 4, 2, 2, (45, 168, 108, 255))
    block(0, 5, 2, 2, (31, 122, 82, 255))
    block(7, 3, 2, 2, (31, 122, 82, 255))
    # house
    block(10, 7, 5, 5, (202, 162, 104, 255))
    block(10, 7, 5, 1, (154, 64, 82, 255))
    block(9, 6, 7, 2, (208, 94, 112, 255))
    block(11, 9, 1, 2, (70, 52, 44, 255))
    block(13, 9, 1, 1, (250, 220, 120, 255))
    block(12, 6, 1, 2, (88, 58, 62, 255))
    # chest
    block(3, 12, 4, 3, (166, 105, 55, 255))
    block(3, 12, 4, 1, (212, 148, 82, 255))
    block(4, 13, 1, 1, (245, 196, 74, 255))
    # sword
    block(12, 12, 1, 4, (196, 211, 230, 255))
    block(11, 15, 3, 1, (245, 158, 11, 255))
    block(12, 16, 1, 1, (245, 158, 11, 255))
    # crystal
    block(17, 9, 2, 5, (38, 130, 160, 255))
    block(17, 8, 1, 3, (96, 210, 220, 255))
    block(18, 9, 1, 2, (170, 240, 245, 255))

    random.seed(11)
    for _ in range(22):
        xx, yy = random.randint(30, sw - 20), random.randint(34, 225)
        radius = random.choice([1, 1, 2])
        fd.ellipse([xx, yy, xx + radius, yy + radius], fill=(185, 170, 255, 130))

    img.alpha_composite(frame, (sx, sy))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, H - 4, W, H], fill=(VIOLET[0], VIOLET[1], VIOLET[2], 255))
    return img.convert("RGB")


def build_logo() -> Image.Image:
    logo = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    draw = ImageDraw.Draw(logo)
    draw.rounded_rectangle([18, 18, 494, 494], radius=96, fill=(12, 14, 20, 255), outline=VIOLET, width=20)
    light = (196, 181, 253, 255)
    blocks = [
        (144, 128, VIOLET), (208, 128, VIOLET), (272, 128, light), (336, 128, light),
        (144, 192, VIOLET), (208, 192, light), (272, 192, light), (336, 192, VIOLET),
        (144, 256, VIOLET), (208, 256, VIOLET), (272, 256, VIOLET), (336, 256, VIOLET),
        (208, 320, TEAL), (272, 320, TEAL), (208, 384, TEAL), (272, 384, TEAL),
    ]
    for x, y, color in blocks:
        draw.rectangle([x, y, x + 63, y + 63], fill=color)
    return logo


if __name__ == "__main__":
    build_banner().save(os.path.join(HERE, "banner.png"), quality=95)
    build_logo().save(os.path.join(HERE, "logo.png"))
    print("Written:", os.path.join(HERE, "banner.png"))
    print("Written:", os.path.join(HERE, "logo.png"))
