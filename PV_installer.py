import requests
from bs4 import BeautifulSoup
import csv
import time

BASE_URL = "https://www.enfsolar.com"
START_PAGE = 1
END_PAGE = 69

OUTPUT_FILE = "germany_installers.csv"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

results = []
seen = set()

for page in range(START_PAGE, END_PAGE + 1):
    if page == 1:
        url = f"{BASE_URL}/directory/installer/Germany"
    else:
        url = f"{BASE_URL}/directory/installer/Germany?page={page}"

    print(f"Fetching page {page}: {url}")

    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    tbody = soup.find("tbody")
    if not tbody:
        print("No tbody found on this page")
        continue

    for a in tbody.find_all("a", class_="mkjs-a", href=True):
        name = a.text.strip()
        link = a["href"].strip()

        # Ensure full URL
        if link.startswith("/"):
            link = BASE_URL + link

        key = (name, link)
        if key not in seen:
            seen.add(key)
            results.append([name, link])

    time.sleep(1)  # polite delay

print(f"Total installers collected: {len(results)}")

with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["name", "url"])
    writer.writerows(results)

print(f"Saved to {OUTPUT_FILE}")
