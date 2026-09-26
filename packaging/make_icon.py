"""Renders the ApplyPilot app icon (teal tile, dark sparkle) as .ico and .png. Requires Pillow."""
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).parent
SIZE = 1024


def sparkle(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float, fill: str) -> None:
    """Four-point star with concave sides."""
    points = []
    for i in range(8):
        import math

        angle = math.pi / 4 * i - math.pi / 2
        radius = r if i % 2 == 0 else r * 0.28
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    draw.polygon(points, fill=fill)


def render() -> Image.Image:
    tile = Image.new("RGBA", (SIZE, SIZE))
    gradient = Image.new("RGBA", (SIZE, SIZE))
    top, bottom = (101, 230, 189), (179, 255, 228)
    px = gradient.load()
    for y in range(SIZE):
        for x in range(SIZE):
            t = (x + y) / (2 * SIZE)
            px[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)) + (255,)
    mask = Image.new("L", (SIZE, SIZE))
    ImageDraw.Draw(mask).rounded_rectangle((40, 40, SIZE - 40, SIZE - 40), radius=230, fill=255)
    tile.paste(gradient, mask=mask)
    draw = ImageDraw.Draw(tile)
    ink = "#06100d"
    sparkle(draw, SIZE * 0.45, SIZE * 0.55, SIZE * 0.30, ink)
    sparkle(draw, SIZE * 0.73, SIZE * 0.27, SIZE * 0.12, ink)
    sparkle(draw, SIZE * 0.76, SIZE * 0.72, SIZE * 0.07, ink)
    return tile


if __name__ == "__main__":
    icon = render()
    icon.resize((256, 256), Image.LANCZOS).save(HERE / "applypilot.png")
    icon.save(HERE / "applypilot.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("wrote", HERE / "applypilot.ico")
