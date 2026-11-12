import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent  # the project folder
load_dotenv(ROOT / ".env")

# --- from .env ---
DATABASE_URL = os.getenv("DATABASE_URL", "")
PRODUCTS_PER_CATEGORY = int(os.getenv("PRODUCTS_PER_CATEGORY", "150"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# --- constants ---
CATEGORIES = [
    "laptop", "smartphone", "tablet", "headphones", "tv",                   # Amazon + notebookcheck
    "smartwatch", "wearable", "audio", "mini_pc", "desktop",                # notebookcheck only
    "monitor", "camera", "handheld", "e_reader",
]
MIN_DESCRIPTION_LENGTH = 20

# --- folders and files ---
SCHEMA_FILE = ROOT / "db" / "schema.sql"  # table definition
DATA_DIR = ROOT / "data"                  # exported products for collaborators

# --- Amazon Reviews 2023 dataset (Hugging Face, free, no key) ---
AMAZON_BASE_URL = (
    "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023"
    "/resolve/main/raw/meta_categories"
)
# our category -> (file to read, Amazon category path it must start with)
AMAZON_CATEGORY_RULES = {
    "laptop": ("meta_Electronics.jsonl", "Electronics > Computers & Accessories > Computers & Tablets > Laptops"),
    "tablet": ("meta_Electronics.jsonl", "Electronics > Computers & Accessories > Computers & Tablets > Tablets"),
    "tv": ("meta_Electronics.jsonl", "Electronics > Television & Video > Televisions"),
    "headphones": ("meta_Electronics.jsonl", "Electronics > Headphones, Earbuds & Accessories > Headphones & Earbuds"),
    "smartphone": ("meta_Cell_Phones_and_Accessories.jsonl", "Cell Phones & Accessories > Cell Phones"),
}
# safety stop: never read more than this many lines of one file
MAX_LINES_PER_FILE = 2_000_000

# --- notebookcheck.net (web scraping; robots.txt allows these pages) ---
# our category -> listing page. Order matters: a review listed under several tags
# is kept under the FIRST one (e.g. Mac mini -> mini_pc, not desktop).
# To add a device type: find its tag on https://www.notebookcheck.net/Topics.92152.0.html
_TOPIC = "https://www.notebookcheck.net/Topics.92152.0.html?tag="
NOTEBOOKCHECK_LISTINGS = {
    "laptop": "https://www.notebookcheck.net/Laptop.315784.0.html",
    "smartphone": "https://www.notebookcheck.net/Smartphone.305158.0.html",
    "tablet": _TOPIC + "11",
    "smartwatch": _TOPIC + "25",
    "wearable": _TOPIC + "75",      # fitness trackers, smart rings
    "audio": _TOPIC + "102",        # headphones/earbuds are detected by name -> "headphones"
    "mini_pc": _TOPIC + "161",      # incl. Mac mini
    "desktop": _TOPIC + "20",
    "monitor": _TOPIC + "92",
    "camera": _TOPIC + "175",
    "handheld": _TOPIC + "265",     # gaming handhelds
    "e_reader": _TOPIC + "254",     # E-Ink
}
NOTEBOOKCHECK_DELAY_SECONDS = 2.0                          # wait between requests (be polite)
NOTEBOOKCHECK_MAX_LISTING_PAGES = 40                       # safety stop per listing (50 articles/page)
NOTEBOOKCHECK_CACHE_DIR = DATA_DIR / "raw" / "notebookcheck"  # downloaded review pages (not committed)
USER_AGENT = "ShopBot-ResearchBot/0.1 (academic information-retrieval project)"

# --- Kaggle "Amazon Sales Dataset" (karkavelrajaj, Amazon India, CC BY-NC-SA 4.0) ---
# Download:  kaggle datasets download -d karkavelrajaj/amazon-sales-dataset -p data/raw/kaggle --unzip
KAGGLE_AMAZON_IN_FILE = DATA_DIR / "raw" / "kaggle" / "amazon.csv"
# Amazon.in category path prefix -> our category (rows that match nothing are skipped)
KAGGLE_AMAZON_IN_CATEGORY_RULES = [
    ("Electronics|Mobiles&Accessories|Smartphones&BasicMobiles|Smartphones", "smartphone"),
    ("Electronics|WearableTechnology|SmartWatches", "smartwatch"),
    ("Electronics|HomeTheater,TV&Video|Televisions", "tv"),
    ("Electronics|Headphones,Earbuds&Accessories|Headphones", "headphones"),
    ("Electronics|HomeAudio|Speakers", "audio"),
    ("Computers&Accessories|Accessories&Peripherals|Audio&VideoAccessories|PCSpeakers", "audio"),
    ("Computers&Accessories|Laptops", "laptop"),
    ("Computers&Accessories|Tablets", "tablet"),
    ("Computers&Accessories|Monitors", "monitor"),
]
# Prices are in Indian rupees. The data was scraped in January 2023, when $1 was about 82.8 INR.
INR_PER_USD = 82.8
MAX_REVIEW_TEXT_CHARS = 1500  # each row holds ~8 reviews; keep an excerpt