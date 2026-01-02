"""Base plugin class and output types for TRMNL plugins."""

import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class PluginOutput:
    """Result from plugin execution."""

    # Image paths
    bmp_path: Optional[Path] = None
    png_path: Optional[Path] = None

    # Image data (alternative to paths)
    image: Optional[Image.Image] = None

    # Metadata
    plugin_name: str = ""
    generated_at: datetime = field(default_factory=datetime.now)
    content_hash: str = ""

    # Error state
    error: Optional[str] = None
    is_cached: bool = False

    def has_image(self) -> bool:
        """Check if output contains an image."""
        return self.image is not None or self.bmp_path is not None


class PluginBase(ABC):
    """Abstract base class for all TRMNL plugins.

    Plugins must inherit from this class and implement the `run` method.
    Set `AUTO_REGISTER = True` to enable auto-discovery.
    """

    # Plugin identity
    BASENAME: str = "plugin"
    DISPLAY_NAME: str = "Plugin"

    # Registration settings
    AUTO_REGISTER: bool = True
    SET_PRIMARY: bool = False
    REGISTRY_ORDER: int = 100

    # Refresh settings
    REFRESH_INTERVAL: int = 120  # seconds

    # Output settings
    OUTPUT_SUBDIR: Optional[str] = None  # Subdirectory in generated/

    # Display settings
    WIDTH: int = 800
    HEIGHT: int = 480

    def __init__(self) -> None:
        """Initialize plugin."""
        self._logger = logging.getLogger(f"plugin.{self.BASENAME}")

    @property
    def name(self) -> str:
        """Plugin name (alias for BASENAME)."""
        return self.BASENAME

    @property
    def display_name(self) -> str:
        """Human-readable plugin name."""
        return self.DISPLAY_NAME

    @abstractmethod
    async def run(self, **kwargs) -> Optional[PluginOutput]:
        """Execute plugin logic and generate output.

        Args:
            **kwargs: Additional arguments including:
                - output_dir: Path to output directory
                - config: Server configuration

        Returns:
            PluginOutput with generated image, or None on failure.
        """
        pass

    def get_content_ttl(self) -> int:
        """Return content TTL in seconds.

        Override to customize cache duration.
        """
        return self.REFRESH_INTERVAL

    def get_output_dir(self, base_dir: Path) -> Path:
        """Get output directory for this plugin."""
        if self.OUTPUT_SUBDIR:
            output_dir = base_dir / self.OUTPUT_SUBDIR
        else:
            output_dir = base_dir / self.BASENAME
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def prepare_image(self, image: Image.Image) -> Image.Image:
        """Apply e-ink optimizations to image.

        Args:
            image: Input image (any mode)

        Returns:
            Optimized grayscale image
        """
        # Convert to grayscale if needed
        if image.mode != "L":
            image = image.convert("L")

        # Ensure correct dimensions
        if image.size != (self.WIDTH, self.HEIGHT):
            image = image.resize((self.WIDTH, self.HEIGHT), Image.Resampling.LANCZOS)

        return image

    def _apply_ordered_dithering(self, image: Image.Image) -> Image.Image:
        """Apply ordered (Bayer) dithering to convert grayscale to 1-bit.

        Uses a 4x4 Bayer matrix for threshold patterns.

        Args:
            image: Grayscale image (mode "L")

        Returns:
            1-bit image (mode "1")
        """
        # 4x4 Bayer matrix (normalized to 0-255 range)
        bayer_matrix = np.array([
            [0, 8, 2, 10],
            [12, 4, 14, 6],
            [3, 11, 1, 9],
            [15, 7, 13, 5],
        ], dtype=np.float32) * (255 / 16)

        # Convert image to numpy array
        img_array = np.array(image, dtype=np.float32)

        # Tile the Bayer matrix to match image dimensions
        height, width = img_array.shape
        tiled_matrix = np.tile(
            bayer_matrix,
            (height // 4 + 1, width // 4 + 1)
        )[:height, :width]

        # Apply threshold: pixel > threshold becomes white
        result = (img_array > tiled_matrix).astype(np.uint8) * 255

        return Image.fromarray(result, mode="L").convert("1")

    def _convert_to_1bit(
        self, image: Image.Image, dithering_mode: str = "none"
    ) -> Image.Image:
        """Convert grayscale image to 1-bit with specified dithering.

        Args:
            image: Grayscale image (mode "L")
            dithering_mode: One of "none", "floyd_steinberg", "ordered"

        Returns:
            1-bit image (mode "1")
        """
        if dithering_mode == "floyd_steinberg":
            return image.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
        elif dithering_mode == "ordered":
            return self._apply_ordered_dithering(image)
        else:  # "none" or any other value
            return image.convert("1", dither=Image.Dither.NONE)

    def save_assets(
        self,
        image: Image.Image,
        output_dir: Path,
        filename_base: str = "screen",
        dithering_mode: str = "none",
    ) -> PluginOutput:
        """Save image as BMP and PNG assets.

        Args:
            image: Image to save (will be prepared first)
            output_dir: Directory to save files
            filename_base: Base filename (without extension)
            dithering_mode: Dithering algorithm for BMP conversion
                - "none": Simple threshold (sharp edges, may show banding)
                - "floyd_steinberg": Error diffusion (smooth gradients)
                - "ordered": Bayer dithering (patterned, predictable)

        Returns:
            PluginOutput with file paths and metadata
        """
        # Prepare image
        prepared = self.prepare_image(image)

        # Calculate content hash
        content_hash = hashlib.md5(prepared.tobytes()).hexdigest()[:16]

        # Save grayscale PNG (for preview)
        png_path = output_dir / f"{filename_base}.png"
        prepared.save(png_path, "PNG")

        # Convert to 1-bit with dithering and save BMP (for TRMNL firmware)
        bmp_image = self._convert_to_1bit(prepared, dithering_mode)
        bmp_path = output_dir / f"{filename_base}.bmp"
        bmp_image.save(bmp_path, "BMP")

        self._logger.debug(
            f"Saved assets: {bmp_path}, {png_path} (dithering: {dithering_mode})"
        )

        return PluginOutput(
            bmp_path=bmp_path,
            png_path=png_path,
            image=prepared,
            plugin_name=self.BASENAME,
            content_hash=content_hash,
        )

    @staticmethod
    def load_font(
        size: int,
        font_dir: Path,
        preferred: list[str] = None,
    ):
        """Load a font with fallbacks.

        Args:
            size: Font size in pixels
            font_dir: Directory containing font files
            preferred: List of preferred font filenames

        Returns:
            ImageFont instance
        """
        from PIL import ImageFont

        # Default font preferences
        if preferred is None:
            preferred = [
                "DejaVuSans.ttf",
                "DejaVuSans-Bold.ttf",
                "arial.ttf",
                "Arial.ttf",
            ]

        # Try preferred fonts
        for font_name in preferred:
            font_path = font_dir / font_name
            if font_path.exists():
                try:
                    return ImageFont.truetype(str(font_path), size)
                except Exception as e:
                    logger.debug(f"Could not load font {font_path}: {e}")

        # Try system fonts
        try:
            return ImageFont.truetype("DejaVuSans.ttf", size)
        except Exception:
            pass

        try:
            return ImageFont.truetype("arial.ttf", size)
        except Exception:
            pass

        # Fall back to default font
        logger.warning(f"No TrueType font found, using default bitmap font")
        return ImageFont.load_default()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.BASENAME})>"
