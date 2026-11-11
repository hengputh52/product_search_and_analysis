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
CATEGORIES = ["laptop", "smartphone", "headphones", "tv", "tablet"]
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