from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from pathlib import Path
import csv
import time
import random

# ================= CONFIG =================
CSV_FILE = "germany_installers.csv"
CHROMEDRIVER_PATH = Path("drivers/chromedriver.exe")
DEBUGGER_ADDRESS = "127.0.0.1:9222"

DELAY_MIN = 1.2
DELAY_MAX = 2.2
BLOCK_PHRASE = "Why have I been blocked?"

# ================= HELPERS =================
def human_delay():
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

def is_blocked(html):
    return BLOCK_PHRASE in html

# ================= LOAD CSV =================
with open(CSV_FILE, newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

# Ensure required columns exist
for r in rows:
    r.setdefault("location", "")
    r.setdefault("telephone", "")
    r.setdefault("website", "")
    r.setdefault("status", "")

# ================= CHROME SETUP =================
chrome_options = Options()
chrome_options.add_experimental_option("debuggerAddress", DEBUGGER_ADDRESS)

driver = webdriver.Chrome(
    service=Service(str(CHROMEDRIVER_PATH)),
    options=chrome_options
)

try:
    for idx, row in enumerate(rows):
        if row["status"] == "DONE":
            continue

        name = row["name"]
        url = row["url"]

        print(f"[{idx}] Processing: {name}")
        driver.get(url)

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        human_delay()

        html = driver.page_source
        if is_blocked(html):
            print("⚠️ BLOCKED — stopping safely")
            break

        soup = BeautifulSoup(html, "html.parser")

        # ========= WEBSITE =========
        web = soup.find("a", itemprop="url", href=True)
        row["website"] = web["href"].strip() if web else ""

        # ========= TELEPHONE =========
        tel_td = soup.find("td", itemprop="telephone")
        if tel_td:
            tel_a = tel_td.find("a", href=True)
            row["telephone"] = tel_a.get_text(strip=True) if tel_a else ""
        else:
            row["telephone"] = ""

        # ========= ADDRESS (comma-safe) =========
        addr_td = soup.find("td", itemprop="address")
        if addr_td:
            location = " ".join(addr_td.get_text().split())
            location = location.replace(",", " -")
            row["location"] = location
        else:
            row["location"] = ""

        row["status"] = "DONE"

        # 🔒 SAVE AFTER EACH ROW
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

        human_delay()

finally:
    driver.quit()

print("✅ Finished safely — resume anytime")
