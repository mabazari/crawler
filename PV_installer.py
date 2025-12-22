from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import csv
import time
import random

# ================= CONFIG =================
BASE_URL = "https://www.enfsolar.com"
START_PAGE = 1
END_PAGE = 3  # test first few pages
OUTPUT_FILE = "germany_installers.csv"
COOKIE_FILE = "www.enfsolar.com_cookies.txt"  # Netscape format cookie file
PAGE_DELAY_MIN = 5
PAGE_DELAY_MAX = 8

# ================= FUNCTION TO READ COOKIES =================
def read_netscape_cookies(file_path):
    cookies = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#") or not line:
                continue
            # Netscape cookie format:
            # domain, flag, path, secure, expiration, name, value
            parts = line.split("\t")
            if len(parts) != 7:
                continue
            domain, flag, path, secure, expiry, name, value = parts
            cookie = {
                "name": name,
                "value": value,
                "domain": domain,
                "path": path,
            }
            if secure.upper() == "TRUE":
                cookie["secure"] = True
            cookies.append(cookie)
    return cookies

# ================= CHROME SETUP =================
chrome_options = Options()
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
# chrome_options.add_argument("--headless=new")  # optional

driver = webdriver.Chrome(options=chrome_options)

results = []
seen = set()

try:
    # Step 1: Open the base URL to initialize session
    driver.get(BASE_URL)
    time.sleep(3)

    # Step 2: Read cookies from file and add to Selenium
    cookies = read_netscape_cookies(COOKIE_FILE)
    for cookie in cookies:
        driver.add_cookie(cookie)

    # Step 3: Scrape pages
    for page in range(START_PAGE, END_PAGE + 1):
        if page == 1:
            url = f"{BASE_URL}/directory/installer/Germany"
        else:
            url = f"{BASE_URL}/directory/installer/Germany?page={page}"

        print(f"Fetching page {page}: {url}")
        driver.get(url)
        time.sleep(random.uniform(PAGE_DELAY_MIN, PAGE_DELAY_MAX))

        soup = BeautifulSoup(driver.page_source, "html.parser")
        tbody = soup.find("tbody")
        if not tbody:
            print("❌ No tbody found — stopping")
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
