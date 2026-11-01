"""Generates the launcher icon used by PixelArtStudio.exe."""
from PIL import Image, ImageDraw

SIZE = 256
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# Dark rounded tile with an accent border.
d.rounded_rectangle([8, 8, SIZE - 8, SIZE - 8], radius=44, fill=(12, 14, 20, 255), outline=(139, 92, 246, 255), width=10)

# Pixel-art glyph: a small sprite made of 32 px blocks.
accent = (139, 92, 246, 255)
light = (196, 181, 253, 255)
teal = (20, 184, 166, 255)
blocks = [
    (72, 64, accent), (104, 64, accent), (136, 64, light), (168, 64, light),
    (72, 96, accent), (104, 96, light), (136, 96, light), (168, 96, accent),
    (72, 128, accent), (104, 128, accent), (136, 128, accent), (168, 128, accent),
    (104, 160, teal), (136, 160, teal),
    (104, 192, teal), (136, 192, teal),
]
for x, y, color in blocks:
    d.rectangle([x, y, x + 31, y + 31], fill=color)

img.save(
    r"C:\Users\52777\Desktop\PixelArtStudio\launcher\PixelArtStudio.ico",
    format="ICO",
    sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)
print("icon written")
