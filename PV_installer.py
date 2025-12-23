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
PAGE_DELAY_MIN = 5
PAGE_DELAY_MAX = 8
CHROMEDRIVER_PATH = Path("drivers/chromedriver.exe")
DEBUGGER_ADDRESS = "127.0.0.1:9222"
SCROLL_STEPS_MIN = 4
SCROLL_STEPS_MAX = 8
SCROLL_PAUSE_MIN = 0.3
SCROLL_PAUSE_MAX = 0.9

# ================= HUMAN-LIKE SCROLL =================
def human_scroll(driver):
    steps = random.randint(SCROLL_STEPS_MIN, SCROLL_STEPS_MAX)
    for _ in range(steps):
        scroll_by = random.randint(250, 700)
        driver.execute_script("window.scrollBy(0, arguments[0]);", scroll_by)
        time.sleep(random.uniform(SCROLL_PAUSE_MIN, SCROLL_PAUSE_MAX))

# ================= CHROME SETUP =================
chrome_options = Options()
chrome_options.add_experimental_option("debuggerAddress", DEBUGGER_ADDRESS)

driver = webdriver.Chrome(
    service=Service(str(CHROMEDRIVER_PATH)),
    options=chrome_options
)

results = []
seen = set()

try:
    # Step 1: Scrape pages using the already-open browser session
    for page in range(START_PAGE, END_PAGE + 1):
        if page == 1:
            url = f"{BASE_URL}/directory/installer/Germany"
        else:
            url = f"{BASE_URL}/directory/installer/Germany?page={page}"

        print(f"Fetching page {page}: {url}")
        driver.get(url)
        time.sleep(random.uniform(PAGE_DELAY_MIN, PAGE_DELAY_MAX))
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "tbody"))
        )
        human_scroll(driver)

        soup = BeautifulSoup(driver.page_source, "html.parser")
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
