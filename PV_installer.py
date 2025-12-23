from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pathlib import Path
from bs4 import BeautifulSoup
import csv
import time
import random

# ================= CONFIG =================
BASE_URL = "https://www.enfsolar.com"
START_PAGE = 1
END_PAGE = 69  # test first few pages
OUTPUT_FILE = "germany_installers.csv"
PAGE_DELAY_BASE = 0.8
PAGE_DELAY_JITTER = 0.7
CHROMEDRIVER_PATH = Path("drivers/chromedriver.exe")
DEBUGGER_ADDRESS = "127.0.0.1:9222"
BLOCK_PHRASE = "Why have I been blocked?"
SCROLL_STEPS_MIN = 4
SCROLL_STEPS_MAX = 8
SCROLL_PAUSE_MIN = 0.3
SCROLL_PAUSE_MAX = 0.9

# ================= HUMAN-LIKE SCROLL =================
def human_scroll(driver):
    try:
        height = driver.execute_script("return document.body.scrollHeight || 0")
    except Exception:
        return

    if not height:
        return

    steps = random.randint(2, max(2, SCROLL_STEPS_MAX))
    for step in range(1, steps + 1):
        y = int(height * step / steps)
        try:
            driver.execute_script("window.scrollTo(0, arguments[0]);", y)
        except Exception:
            break
        time.sleep(random.uniform(SCROLL_PAUSE_MIN, SCROLL_PAUSE_MAX))

    try:
        driver.execute_script("window.scrollTo(0, 0);")
    except Exception:
        pass

def sleep_with_jitter(base_delay, jitter):
    base = max(0.0, base_delay)
    extra = max(0.0, jitter)
    delay = base + random.uniform(0.0, extra)
    if delay:
        time.sleep(delay)

def is_blocked(page_source):
    return BLOCK_PHRASE in page_source

# ================= CHROME SETUP =================
chrome_options = Options()
chrome_options.add_experimental_option("debuggerAddress", DEBUGGER_ADDRESS)

driver = webdriver.Chrome(
    service=Service(str(CHROMEDRIVER_PATH)),
    options=chrome_options
)

results = []
seen = set()
blocked_page = None

try:
    # Step 1: Scrape pages using the already-open browser session
    for page in range(START_PAGE, END_PAGE + 1):
        if page == 1:
            url = f"{BASE_URL}/directory/installer/Germany"
        else:
            url = f"{BASE_URL}/directory/installer/Germany?page={page}"

        print(f"Fetching page {page}: {url}")
        driver.get(url)
        sleep_with_jitter(PAGE_DELAY_BASE, PAGE_DELAY_JITTER)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "tbody"))
        )
        human_scroll(driver)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        if is_blocked(driver.page_source):
            blocked_page = page
            print(f"Blocked on page {page}. Saving current results.")
            break
        tbody = soup.find("tbody")
        if not tbody:
            print("No tbody found - stopping")
            break

        for a in tbody.find_all("a", class_="mkjs-a", href=True):
            name = a.get_text(strip=True)
            link = a["href"]
            if link.startswith("/"):
                link = BASE_URL + link
            key = (name, link)
            if key not in seen:
                seen.add(key)
                results.append([name, link])

finally:
    driver.quit()

print(f"Total installers collected: {len(results)}")
with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["name", "url"])
    writer.writerows(results)

print(f"Saved to {OUTPUT_FILE}")
if blocked_page is not None:
    print(f"Stopped at page {blocked_page}. Resume from this page later.")

