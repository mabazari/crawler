import requests
from bs4 import BeautifulSoup
import csv
import time
import random

BASE_URL = "https://www.enfsolar.com"
START_PAGE = 1
END_PAGE = 69

COOKIES_FILE = "www.enfsolar.com_cookies.txt"
OUTPUT_FILE = "germany_installers.csv"

session = requests.Session()

# Browser-like headers (MUST match browser that generated cookies)
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.enfsolar.com/",
    "Connection": "keep-alive",
})

# -------------------------------
# Load Netscape-format cookies
# -------------------------------
def load_netscape_cookies(session, filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            parts = line.split("\t")
            if len(parts) != 7:
                continue

            domain, flag, path, secure, expiry, name, value = parts

            session.cookies.set(
                name=name,
                value=value,
                domain=domain,
                path=path,
                secure=(secure.upper() == "TRUE")
            )

# Load cookies into session
load_netscape_cookies(session, COOKIES_FILE)

print("Cookies loaded into session")

results = []
seen = set()

for page in range(START_PAGE, END_PAGE + 1):
    if page == 1:
        url = f"{BASE_URL}/directory/installer/Germany"
    else:
        url = f"{BASE_URL}/directory/installer/Germany?page={page}"

    print(f"Fetching page {page}: {url}")

    response = session.get(url, timeout=25)

    if response.status_code != 200:
        print(f"Blocked on page {page} (status {response.status_code})")
        print("STOP: refresh cookies and resume later")
        break

    soup = BeautifulSoup(response.text, "html.parser")

    tbody = soup.find("tbody")
    if not tbody:
        print("No tbody found — stopping")
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

    # VERY important to avoid 429 / 403
    time.sleep(random.uniform(4.0, 6.5))

print(f"Collected installers: {len(results)}")

with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["name", "url"])
    writer.writerows(results)

print(f"Saved to {OUTPUT_FILE}")
