import requests
from bs4 import BeautifulSoup
import csv
import time

BASE_URL = "https://www.enfsolar.com"
START_PAGE = 1
END_PAGE = 69

OUTPUT_FILE = "germany_installers.csv"

session = requests.Session()

session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.enfsolar.com/",
    "Upgrade-Insecure-Requests": "1"
})

results = []
seen = set()

for page in range(START_PAGE, END_PAGE + 1):
    if page == 1:
        url = f"{BASE_URL}/directory/installer/Germany"
    else:
        url = f"{BASE_URL}/directory/installer/Germany?page={page}"

    print(f"Fetching page {page}: {url}")

    response = session.get(url, timeout=20)

    if response.status_code != 200:
        print(f"Skipped page {page} (status {response.status_code})")
        continue

    soup = BeautifulSoup(response.text, "html.parser")

    tbody = soup.find("tbody")
    if not tbody:
        print("No tbody found on this page")
        continue

    for a in tbody.find_all("a", class_="mkjs-a", href=True):
        name = a.get_text(strip=True)
        link = a["href"].strip()

        if link.startswith("/"):
            link = BASE_URL + link

        key = (name, link)
        if key not in seen:
            seen.add(key)
            results.append([name, link])

    time.sleep(1.2)  # important: avoid triggering protection

print(f"Total installers collected: {len(results)}")

with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["name", "url"])
    writer.writerows(results)

print(f"Saved to {OUTPUT_FILE}")
