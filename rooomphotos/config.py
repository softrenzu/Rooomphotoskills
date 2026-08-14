from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformPreset:
    name: str
    width: int
    height: int | None
    quality: int = 92
    crop: bool = False


PLATFORMS = {
    "master": PlatformPreset("共通_マスター", 2400, None, 94, False),
    "airbnb": PlatformPreset("Airbnb", 2048, 1365, 93, True),
    "booking": PlatformPreset("Booking", 2400, None, 94, False),
    "spacemarket": PlatformPreset("スペースマーケット", 1920, 1080, 92, True),
    "instabase": PlatformPreset("インスタベース", 1570, 880, 92, True),
}

CATEGORY_PROMPTS = {
    "living": "a bright wide photo of a living room or lounge in a rental property",
    "bedroom": "a clear wide photo of a bedroom and beds in a rental property",
    "kitchen": "a clear photo of a kitchen or kitchenette in a rental property",
    "bathroom": "a clear photo of a bathroom shower or bathtub in a rental property",
    "toilet": "a clear photo of a toilet room in a rental property",
    "entrance": "a clear photo of the entrance doorway hallway or access to a rental property",
    "exterior": "a clear photo of the exterior building facade of a rental property",
    "workspace": "a clear photo of a desk workspace meeting room or work area",
    "amenity": "a clear photo of useful amenities appliances equipment or facilities",
    "view": "a clear photo of the view balcony terrace garden or surrounding scenery",
    "layout": "a floor plan or room layout diagram",
}

JUNK_PROMPTS = {
    "screenshot": "a phone screenshot app screen website screenshot or social media screenshot",
    "document": "a document receipt form text page sign poster or mostly text image",
    "people": "a portrait selfie or photo mainly showing a person",
    "qr": "a QR code barcode contact information advertisement or promotional graphic",
}

CATEGORY_QUOTAS = {
    "living": 4,
    "bedroom": 3,
    "kitchen": 2,
    "bathroom": 2,
    "toilet": 1,
    "entrance": 1,
    "exterior": 2,
    "workspace": 2,
    "amenity": 4,
    "view": 2,
    "layout": 1,
}

MIN_WIDTH = 1024
MIN_HEIGHT = 683
MIN_SHARPNESS = 35.0
PHASH_DISTANCE = 7
CLIP_DUPLICATE_SIMILARITY = 0.965
JUNK_CONFIDENCE_MARGIN = 0.03
