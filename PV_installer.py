from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import csv
import time
import random

# ================= CONFIG =================

BASE_URL = "https://www.enfsolar.com"
START_PAGE = 1
END_PAGE = 69

OUTPUT_FILE = "germany_installers.csv"

# 🔴 CHANGE THESE TO YOUR SYSTEM
CHROME_USER_DATA_DIR = r"C:\Users\MS\AppData\Local\Google\Chrome\User Data"
CHROME_PROFILE_DIR = "Default"

# ==========================================

chrome_options = Options()
chrome_options.add_argument(f"--user-data-dir={CHROME_USER_DATA_DIR}")
chrome_options.add_argument(f"--profile-directory={CHROME_PROFILE_DIR}")

# Reduce automation fingerprints
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("--start-maximized")

driver = webdriver.Chrome(options=chrome_options)

results = []
seen = set()

try:
    for page in range(START_PAGE, END_PAGE + 1):
        if page == 1:
            url = f"{BASE_URL}/directory/installer/Germany"
        else:
            url = f"{BASE_URL}/directory/installer/Germany?page={page}"

        print(f"Fetching page {page}: {url}")
        driver.get(url)

        # Let Cloudflare + JS settle
        time.sleep(random.uniform(3.5, 5.5))

        soup = BeautifulSoup(driver.page_source, "html.parser")

        tbody = soup.find("tbody")
        if not tbody:
            print("❌ No tbody found — stopping")
            break

        for a in tbody.find_all("a", class_="mkjs-a", href=True):
            name = a.get_text(strip=True)
            link = a["href"].strip()

            if link.startswith("/"):
                link = BASE_URL + link

            key = (name, link)
            if key not in seen:
                seen.add(key)
                results.append([name, link])

        # Human-like delay between pages
        time.sleep(random.uniform(2.5, 4.0))

finally:
    driver.quit()

print(f"Total installers collected: {len(results)}")

with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["name", "url"])
    writer.writerows(results)

print(f"Saved to {OUTPUT_FILE}")
