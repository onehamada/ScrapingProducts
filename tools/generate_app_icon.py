from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT_DIR / "assets"
ICON_PATH = ASSETS_DIR / "marketplace-search.ico"
PNG_PATH = ASSETS_DIR / "marketplace-search.png"
SIZE = 256


def draw_icon() -> Image.Image:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    shadow_color = (7, 24, 61, 120)
    background_color = (15, 76, 129, 255)
    background_glow = (28, 124, 177, 255)
    panel_color = (246, 249, 252, 255)
    panel_bar_color = (61, 132, 194, 255)
    accent_color = (255, 179, 71, 255)
    accent_soft = (255, 211, 140, 255)
    detail_color = (154, 196, 228, 255)

    draw.rounded_rectangle((22, 26, 238, 242), radius=56, fill=shadow_color)
    draw.rounded_rectangle((16, 16, 240, 240), radius=56, fill=background_color)
    draw.pieslice((32, 8, 248, 224), start=210, end=360, fill=background_glow)

    draw.rounded_rectangle((48, 56, 176, 170), radius=24, fill=panel_color)
    draw.rounded_rectangle((48, 56, 176, 92), radius=24, fill=panel_bar_color)
    draw.rectangle((48, 74, 176, 92), fill=panel_bar_color)

    draw.ellipse((62, 66, 74, 78), fill=panel_color)
    draw.ellipse((80, 66, 92, 78), fill=panel_color)
    draw.ellipse((98, 66, 110, 78), fill=panel_color)

    draw.rounded_rectangle((66, 112, 148, 126), radius=7, fill=accent_color)
    draw.rounded_rectangle((66, 138, 132, 150), radius=6, fill=detail_color)
    draw.rounded_rectangle((66, 158, 120, 170), radius=6, fill=detail_color)

    draw.ellipse((118, 118, 210, 210), outline=accent_color, width=14)
    draw.ellipse((138, 138, 190, 190), fill=accent_soft)
    draw.line((184, 184, 222, 222), fill=accent_color, width=16)
    draw.line((188, 188, 222, 222), fill=accent_color, width=10)

    return image


def main() -> int:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    image = draw_icon()
    image.save(PNG_PATH)
    image.save(
        ICON_PATH,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Icone salvo em: {ICON_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
