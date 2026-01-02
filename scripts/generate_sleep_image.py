#!/usr/bin/env python3
"""Generate sleep mode image for TRMNL display.

Creates an 800x480 image with the cardinal cat centered and
"heretic.giglabo.com" text below it.

Generates both PNG (for preview) and BMP (1-bit for TRMNL device).
"""

import io
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw, ImageFont


# Display dimensions (TRMNL e-ink)
WIDTH = 800
HEIGHT = 480

# Colors for e-ink
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


def load_svg_as_image(svg_path: Path, target_height: int) -> Image.Image:
    """Load SVG and convert to PIL Image, scaling to target height."""
    # Read SVG content
    svg_content = svg_path.read_bytes()

    # Get original dimensions from SVG (400x500)
    original_width = 400
    original_height = 500

    # Calculate scale to fit target height while maintaining aspect ratio
    scale = target_height / original_height
    new_width = int(original_width * scale)
    new_height = target_height

    # Convert SVG to PNG bytes
    png_bytes = cairosvg.svg2png(
        bytestring=svg_content,
        output_width=new_width,
        output_height=new_height,
    )

    # Load as PIL Image
    return Image.open(io.BytesIO(png_bytes))


def find_font(size: int) -> ImageFont.FreeTypeFont:
    """Find and load a suitable font."""
    project_root = Path(__file__).parent.parent
    fonts_dir = project_root / "assets" / "fonts"

    # Try project fonts first
    font_names = ["Block-Bold.ttf", "Block-Regular.ttf", "DejaVuSans-Bold.ttf"]
    for name in font_names:
        font_path = fonts_dir / name
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size)

    # Try system fonts
    system_fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "DejaVuSans-Bold.ttf",
        "arial.ttf",
    ]
    for font_path in system_fonts:
        try:
            return ImageFont.truetype(font_path, size)
        except OSError:
            continue

    # Fallback to default
    return ImageFont.load_default()


def generate_sleep_image(
    svg_path: Path,
    output_dir: Path,
    filename_base: str = "sleep-image",
    text: str = "heretic.giglabo.com",
) -> None:
    """Generate the sleep mode image in PNG and BMP formats."""
    # Create white background
    image = Image.new("RGB", (WIDTH, HEIGHT), WHITE)
    draw = ImageDraw.Draw(image)

    # Load and scale the SVG - leave more space for larger text
    cat_max_height = HEIGHT - 100
    cat_image = load_svg_as_image(svg_path, cat_max_height)

    # Center the cat horizontally, position higher (negative margin from center)
    cat_x = (WIDTH - cat_image.width) // 2
    cat_y = -15  # Move cat up (closer to top edge)

    # Paste cat image (handle transparency if present)
    if cat_image.mode == "RGBA":
        image.paste(cat_image, (cat_x, cat_y), cat_image)
    else:
        image.paste(cat_image, (cat_x, cat_y))

    # Add text below the cat - bigger font
    font = find_font(42)

    # Calculate text position (centered, at bottom with margin)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    text_x = (WIDTH - text_width) // 2
    text_y = HEIGHT - text_height - 25  # 25px from bottom

    draw.text((text_x, text_y), text, font=font, fill=BLACK)

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save PNG (for preview)
    png_path = output_dir / f"{filename_base}.png"
    image.save(png_path, "PNG", optimize=True)
    print(f"Generated PNG: {png_path}")

    # Convert to grayscale then 1-bit BMP (for TRMNL device)
    grayscale = image.convert("L")
    bmp_image = grayscale.convert("1", dither=Image.Dither.NONE)
    bmp_path = output_dir / f"{filename_base}.bmp"
    bmp_image.save(bmp_path, "BMP")
    print(f"Generated BMP: {bmp_path}")


def main() -> None:
    """Main entry point."""
    project_root = Path(__file__).parent.parent

    svg_path = project_root / "images" / "cardinal_cat.svg"
    output_dir = project_root / "web"

    if not svg_path.exists():
        raise FileNotFoundError(f"SVG not found: {svg_path}")

    generate_sleep_image(svg_path, output_dir)


if __name__ == "__main__":
    main()
