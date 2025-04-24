import zlib
import base64
from io import BytesIO
from PIL import ImageDraw, Image


class ImageHelper:


    @staticmethod
    def png_draw_rectangle(png: bytes, x: float, y: float, width: float, height: float, color: str = "red", border: int = 5) -> bytes:
        image = Image.open(BytesIO(png))
        draw = ImageDraw.Draw(image)
        draw.rectangle((x, y, x + width, y + height), outline=color, width=border)
        image_bytes = BytesIO()
        image.save(image_bytes, format="PNG")
        return image_bytes.getvalue()


    @staticmethod
    def base64comppng_draw_rectangle(b64comppng: str, x: float, y: float, width: float, height: float, color: str = "red", border: int = 5) -> str:
        image = Image.open(BytesIO(zlib.decompress(base64.b64decode(b64comppng))))
        draw = ImageDraw.Draw(image)
        draw.rectangle((x, y, x + width, y + height), outline=color, width=border)
        image_bytes = BytesIO()
        image.save(image_bytes, format="PNG")
        return base64.b64encode(zlib.compress(image_bytes.getvalue(), 9)).decode()

    @staticmethod
    def crop_screenshot(png: bytes, x: float, y: float, width: float, height: float) -> bytes:
        """
        Crop a screenshot to the specified region.
        
        Args:
            png: The screenshot as bytes
            x: The x-coordinate of the top-left corner
            y: The y-coordinate of the top-left corner
            width: The width of the region to crop
            height: The height of the region to crop
            
        Returns:
            The cropped screenshot as bytes
        """
        image = Image.open(BytesIO(png))
        
        # If we're not actually cropping (requesting the whole image), just return the original
        if x == 0 and y == 0 and width >= image.width and height >= image.height:
            return png
            
        # Ensure the crop region is within the image bounds
        x = max(0, min(x, image.width - 1))
        y = max(0, min(y, image.height - 1))
        width = max(1, min(width, image.width - x))
        height = max(1, min(height, image.height - y))
        
        # Crop the image
        cropped = image.crop((x, y, x + width, y + height))
        
        # Convert back to bytes
        image_bytes = BytesIO()
        cropped.save(image_bytes, format="PNG")
        return image_bytes.getvalue()
