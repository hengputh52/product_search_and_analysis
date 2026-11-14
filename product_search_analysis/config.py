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
    "laptop", "smartphone", "tablet", "headphones", "tv",                   
    "smartwatch", "wearable", "audio", "mini_pc", "desktop",                
    "monitor", "camera", "handheld", "e_reader",
    "powerbank", "speaker", "keyboard", "charger",                          
    "computer", "gaming" , "apple", "computer-accessories", "computer-components" , "printer",
    "tablet-case", "phone-case", "earphones", "earbuds", "adapter-cable", "watch-straps",
    "wireless-charger", "watch-straps"                                          
]
MIN_DESCRIPTION_LENGTH = 20


SCHEMA_FILE = ROOT / "db" / "schema.sql"
DATA_DIR = ROOT / "data"
INDEX_DIR = DATA_DIR / "index"            # saved search index (gitignored, rebuilt from the DB)
INDEX_FILE = INDEX_DIR / "inverted_index.pkl"

# --- ranking & retrieval (search/) ---
EMBEDDINGS_FILE = INDEX_DIR / "embeddings.npz"   # dense vectors (gitignored, rebuilt from the DB)
# Small, fast English model (384-dim vectors); runs fine on a laptop CPU.
# Changing the model? Rebuild the embeddings (python -m product_search_analysis.search.dense).
DENSE_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
# Some models expect a prefix, e.g. intfloat/e5-*: "query: " / "passage: ". MiniLM needs none.
DENSE_QUERY_PREFIX = ""
DENSE_DOCUMENT_PREFIX = ""
DENSE_BATCH_SIZE = 64          # products encoded at once while building embeddings
BM25_K1 = 1.5                  # how quickly repeated words stop adding score (term-frequency saturation)
BM25_B = 0.75                  # how much long product texts are penalised (0 = not at all, 1 = fully)
RRF_K = 60                     # Reciprocal Rank Fusion constant (60 is the value from the original paper)
HYBRID_METHODS = ["bm25", "dense"]   # which registered methods "hybrid" fuses (any 2 or more)
HYBRID_WEIGHTS = None          # None = equal; or one weight per HYBRID_METHODS entry, e.g. [1.0, 2.0]
HYBRID_CANDIDATES = 100        # top results taken from each method before fusing them
DEFAULT_TOP_K = 10
# Product columns returned with every search result (must be columns of the products table).
# Add one here, rebuild the index, and it appears in retrieve() / search_boolean() results.
SEARCH_RESULT_FIELDS = ["title", "brand", "category", "price", "rating", "source", "source_url"]
BENCHMARK_DIR = DATA_DIR / "benchmark"
BENCHMARK_QUERIES_FILE = ROOT / "product_search_analysis" / "search" / "benchmark_queries.json"


AMAZON_BASE_URL = (
    "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023"
    "/resolve/main/raw/meta_categories"
)

AMAZON_CATEGORY_RULES = {
    "laptop": ("meta_Electronics.jsonl", "Electronics > Computers & Accessories > Computers & Tablets > Laptops"),
    "tablet": ("meta_Electronics.jsonl", "Electronics > Computers & Accessories > Computers & Tablets > Tablets"),
    "tv": ("meta_Electronics.jsonl", "Electronics > Television & Video > Televisions"),
    "headphones": ("meta_Electronics.jsonl", "Electronics > Headphones, Earbuds & Accessories > Headphones & Earbuds"),
    "smartphone": ("meta_Cell_Phones_and_Accessories.jsonl", "Cell Phones & Accessories > Cell Phones"),
}

MAX_LINES_PER_FILE = 2_000_000


AMAZON_WEB_SEARCHES = {
    # "smartphone": "https://www.amazon.com/s?k=cell+phones&rh=n%3A7072561011",
    # "powerbank": "https://www.amazon.com/s?k=power+bank",
    # "speaker": "https://www.amazon.com/s?k=speakers",
    "keyboard": "https://www.amazon.com/s?k=keyboard",

}
AMAZON_WEB_MAX_PAGES = 20       
AMAZON_WEB_DELAY_SECONDS = 2.0   

AMAZON_WEB_COOKIES = {"i18n-prefs": "USD", "lc-main": "en_US"}
KHR_PER_USD = 4000.0


ALIBABA_SEARCHES = {
    # "keyboard": (
    #     "https://www.alibaba.com/search/page?spm=a2700.product_home_fy25.home_login_first_screen_fy23_pc_search_bar.keydown__Enter&SearchScene=proSearch&SearchText=keyboard&pro=true&from=pcHomeContent"
    # ),
    # "powerbank": ("https://www.alibaba.com/search/page?spm=a2700.prosearch.the-new-header_fy23_pc_search_bar.keydown__Enter&SearchScene=proSearch&SearchText=powerbank&pro=true&from=pcHomeContent")
    "charger": ("https://www.alibaba.com/search/page?spm=a2700.prosearch.the-new-header_fy23_pc_search_bar.keydown__Enter&SearchScene=proSearch&SearchText=charger&pro=true&from=pcHomeContent")
}

ALIBABA_MAX_PAGES = 10         
ALIBABA_MAX_SCROLLS = 10        
ALIBABA_DELAY_SECONDS = 3.0     



PTC_COMPUTER_LISTINGS = {
    # "computer": "https://ptc-computer.com.kh/parent_category/computer",
    # "gaming": "https://ptc-computer.com.kh/parent_category/computer---gaming-xk0jn",
    # "apple": "https://ptc-computer.com.kh/parent_category/apple-wknsu",
    # "monitor": "https://ptc-computer.com.kh/parent_category/monitor",
    # "computer-accessories": "https://ptc-computer.com.kh/parent_category/computer-accessories",
    # "computer-components": "https://ptc-computer.com.kh/parent_category/computer-components",
    "printer": "https://ptc-computer.com.kh/parent_category/printer-and-cartdridges",
}
PTC_COMPUTER_MAX_PAGES = 50
PTC_COMPUTER_DELAY_SECONDS = 2.0


ANGKOR_MEAS_LISTINGS = {
    # "smartphone": "https://angkormeas.com/cate/smartphone/",
    # "tablet": "https://angkormeas.com/cate/tablet/",
    "smartwatch": "https://angkormeas.com/cate/watch/",
    "computer": "https://angkormeas.com/cate/computer/",
    "tablet-case": "https://angkormeas.com/cate/accessories/ipad-tables-case/",
    "phone-case": "https://angkormeas.com/cate/accessories/phone-case/",
    "earphones": "https://angkormeas.com/cate/accessories/earphones/",
    "headphones": "https://angkormeas.com/cate/accessories/headphone/",
    "speaker": "https://angkormeas.com/cate/accessories/speakers/",
    "earbuds": "https://angkormeas.com/cate/accessories/earbuds/",
    "adapter-cable": "https://angkormeas.com/cate/accessories/adapter-cable/",
    "watch-straps": "https://angkormeas.com/cate/accessories/watch-straps/",
    "powerbank": "https://angkormeas.com/cate/accessories/power-bankbatery/",
    "wireless-charger": "https://angkormeas.com/cate/accessories/wireless-charger/",
}
ANGKOR_MEAS_MAX_PAGES = 50
ANGKOR_MEAS_DELAY_SECONDS = 2.0


SUNSIMEXCO_LISTINGS = {
    "tv": "https://sunsimexco.com.kh/products?category=tv-projector",
    "speaker": "https://sunsimexco.com.kh/products?category=home-audio-video",
}
SUNSIMEXCO_MAX_PAGES = 50           
SUNSIMEXCO_DELAY_SECONDS = 2.0       


_TOPIC = "https://www.notebookcheck.net/Topics.92152.0.html?tag="
NOTEBOOKCHECK_LISTINGS = {
    "laptop": "https://www.notebookcheck.net/Laptop.315784.0.html",
    "smartphone": "https://www.notebookcheck.net/Smartphone.305158.0.html",
    "tablet": _TOPIC + "11",
    "smartwatch": _TOPIC + "25",
    "wearable": _TOPIC + "75",      
    "audio": _TOPIC + "102",        
    "mini_pc": _TOPIC + "161",      
    "desktop": _TOPIC + "20",
    "monitor": _TOPIC + "92",
    "camera": _TOPIC + "175",
    "handheld": _TOPIC + "265",     
    "e_reader": _TOPIC + "254",     
}
NOTEBOOKCHECK_DELAY_SECONDS = 2.0                          
NOTEBOOKCHECK_MAX_LISTING_PAGES = 40                       
NOTEBOOKCHECK_CACHE_DIR = DATA_DIR / "raw" / "notebookcheck"  
USER_AGENT = "ShopBot-ResearchBot/0.1 (academic information-retrieval project)"
USD_PER_EUR = 1.1081


KAGGLE_AMAZON_IN_FILE = DATA_DIR / "raw" / "kaggle" / "amazon.csv"
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

INR_PER_USD = 82.8
MAX_REVIEW_TEXT_CHARS = 1500  