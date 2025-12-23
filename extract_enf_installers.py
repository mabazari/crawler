#!/usr/bin/env python3
import argparse
import csv
import http.cookiejar
import os
import random
import sys
import time
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener


DEFAULT_BASE_URL = "https://www.enfsolar.com/directory/installer/Germany?page={page}"
DEFAULT_HOME_URL = "https://www.enfsolar.com/"
DEFAULT_COOKIE_FILE = "www.enfsolar.com_cookies.txt"
DEFAULT_OUTPUT = "enf_germany_installers.csv"
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 "
    "Firefox/121.0",
]
DEFAULT_UA = USER_AGENTS[0]


class InstallerLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return

        attr_map = dict(attrs)
        href = attr_map.get("href")
        if not href:
            return

        # Company links have mkjs-a and a data-company-id attribute.
        cls = attr_map.get("class", "")
        if "mkjs-a" not in cls.split():
            return
        if "data-company-id" not in attr_map:
            return

        self.links.append(href)


def is_blocked(html, status_code):
    if status_code in (403, 429, 503):
        return True
    if not html:
        return True
    text = html.lower()
    if "cloudflare" in text and (
        "just a moment" in text
        or "checking your browser" in text
        or "attention required" in text
    ):
        return True
    if "verify you are human" in text or "captcha" in text:
        return True
    return False


def sleep_with_jitter(base_delay, jitter):
    base = max(0.0, base_delay)
    extra = max(0.0, jitter)
    delay = base + random.uniform(0.0, extra)
    if delay:
        time.sleep(delay)


def make_opener():
    jar = http.cookiejar.CookieJar()
    return build_opener(HTTPCookieProcessor(jar)), jar


def load_cookie_jar(cookie_file):
    jar = http.cookiejar.MozillaCookieJar()
    try:
        jar.load(cookie_file, ignore_discard=True, ignore_expires=True)
    except FileNotFoundError:
        return None
    except Exception as exc:
        raise RuntimeError(f"Failed to load cookie file: {exc}") from exc
    return jar


def fetch_html_urllib(url, opener, headers, timeout, retries, retry_delay, retry_jitter):
    last_error = None
    for attempt in range(retries + 1):
        req = Request(url, headers=headers)
        try:
            with opener.open(req, timeout=timeout) as resp:
                status = resp.getcode()
                html = resp.read().decode("utf-8", errors="ignore")
            return html, status, is_blocked(html, status)
        except HTTPError as err:
            status = err.code
            body = ""
            try:
                body = err.read().decode("utf-8", errors="ignore")
            except Exception:
                body = ""
            if status in (403, 429, 503):
                return body, status, True
            last_error = err
        except URLError as err:
            last_error = err

        if attempt < retries:
            sleep_with_jitter(retry_delay, retry_jitter)

    if last_error:
        raise last_error
    return "", None, True


def create_webdriver(
    user_agent,
    headless,
    user_data_dir,
    profile_directory,
    browser,
    debugger_address,
):
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        from selenium.webdriver.edge.options import Options as EdgeOptions
    except Exception as exc:
        raise RuntimeError(
            "Selenium is not available. Install it with: pip install selenium"
        ) from exc

    options_list = []
    chrome_options = ChromeOptions()
    if debugger_address:
        chrome_options.add_experimental_option("debuggerAddress", debugger_address)
    else:
        chrome_options.add_argument("--window-size=1280,900")
        chrome_options.add_argument("--lang=en-US")
        if user_agent:
            chrome_options.add_argument(f"--user-agent={user_agent}")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        if user_data_dir:
            chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
        if profile_directory:
            chrome_options.add_argument(f"--profile-directory={profile_directory}")
        if headless:
            chrome_options.add_argument("--headless=new")
    options_list.append(("chrome", chrome_options))

    edge_options = EdgeOptions()
    if debugger_address:
        edge_options.add_experimental_option("debuggerAddress", debugger_address)
    else:
        edge_options.add_argument("--window-size=1280,900")
        edge_options.add_argument("--lang=en-US")
        if user_agent:
            edge_options.add_argument(f"--user-agent={user_agent}")
        edge_options.add_argument("--disable-blink-features=AutomationControlled")
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        edge_options.add_experimental_option("useAutomationExtension", False)
        if user_data_dir:
            edge_options.add_argument(f"--user-data-dir={user_data_dir}")
        if profile_directory:
            edge_options.add_argument(f"--profile-directory={profile_directory}")
        if headless:
            edge_options.add_argument("--headless=new")
    options_list.append(("edge", edge_options))

    last_error = None
    for browser_name, options in options_list:
        if browser in ("chrome", "edge") and browser != browser_name:
            continue
        try:
            if browser_name == "chrome":
                return webdriver.Chrome(options=options)
            return webdriver.Edge(options=options)
        except Exception as exc:
            last_error = exc

    raise RuntimeError(f"Failed to start Selenium driver: {last_error}")


def humanize_browser(driver, min_wait, max_wait, scroll_steps):
    if min_wait or max_wait:
        time.sleep(random.uniform(min_wait, max_wait))

    if scroll_steps <= 0:
        return

    try:
        height = driver.execute_script("return document.body.scrollHeight || 0")
    except Exception:
        return

    if not height:
        return

    steps = random.randint(2, max(2, scroll_steps))
    for step in range(1, steps + 1):
        y = int(height * step / steps)
        try:
            driver.execute_script("window.scrollTo(0, arguments[0]);", y)
        except Exception:
            break
        time.sleep(random.uniform(0.2, 0.6))

    try:
        driver.execute_script("window.scrollTo(0, 0);")
    except Exception:
        pass


def wait_for_table(driver, wait_seconds):
    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        WebDriverWait(driver, wait_seconds).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.enf-list-table"))
        )
        return True
    except Exception:
        return False


def apply_cookies_to_driver(driver, cookie_jar, base_url):
    if not cookie_jar:
        return 0

    driver.get(base_url)
    added = 0
    for cookie in cookie_jar:
        cookie_dict = {
            "name": cookie.name,
            "value": cookie.value,
            "path": cookie.path or "/",
        }
        domain = cookie.domain.lstrip(".") if cookie.domain else ""
        if domain:
            cookie_dict["domain"] = domain
        if cookie.expires:
            cookie_dict["expiry"] = int(cookie.expires)
        if cookie.secure:
            cookie_dict["secure"] = True
        try:
            driver.add_cookie(cookie_dict)
            added += 1
        except Exception:
            continue

    try:
        driver.refresh()
    except Exception:
        pass
    return added


def try_manual_unblock(driver, manual_retries, manual_wait):
    attempts = max(0, manual_retries)
    for attempt in range(attempts + 1):
        if not is_blocked(driver.page_source, None):
            return False
        print(
            "Blocked page detected (attempt "
            f"{attempt + 1}/{attempts + 1}). "
            "Solve the challenge in the browser, then press Enter.",
            file=sys.stderr,
        )
        input()
        if manual_wait > 0:
            time.sleep(manual_wait)
    return is_blocked(driver.page_source, None)


def go_next_page(driver):
    try:
        from selenium.webdriver.common.by import By

        next_icon = driver.find_element(By.CSS_SELECTOR, "ul.pagination i.fa-chevron-right")
        next_link = next_icon.find_element(By.XPATH, "./ancestor::a[1]")
        next_link.click()
        return True
    except Exception:
        pass

    try:
        from selenium.webdriver.common.by import By

        active = driver.find_element(By.CSS_SELECTOR, "ul.pagination li.active")
        next_link = active.find_element(By.XPATH, "following-sibling::li/a[1]")
        next_link.click()
        return True
    except Exception:
        return False


def fetch_html_selenium(
    url,
    driver,
    wait_seconds,
    humanize,
    min_wait,
    max_wait,
    scroll_steps,
    manual,
    manual_retries,
    manual_wait,
    navigate,
):
    if navigate:
        driver.get(url)
    if manual:
        if try_manual_unblock(driver, manual_retries, manual_wait):
            return driver.page_source, True

    wait_for_table(driver, wait_seconds)

    if humanize:
        humanize_browser(driver, min_wait, max_wait, scroll_steps)

    html = driver.page_source
    blocked = is_blocked(html, None)
    if blocked and manual:
        if try_manual_unblock(driver, manual_retries, manual_wait):
            return driver.page_source, True
        wait_for_table(driver, wait_seconds)
        if humanize:
            humanize_browser(driver, min_wait, max_wait, scroll_steps)
        html = driver.page_source
        blocked = is_blocked(html, None)
    return html, blocked


def extract_links(html):
    parser = InstallerLinkParser()
    parser.feed(html)
    return parser.links


def main():
    parser = argparse.ArgumentParser(
        description="Extract ENF Solar installer links for Germany."
    )
    parser.add_argument("--start", type=int, default=1, help="Start page.")
    parser.add_argument("--end", type=int, default=69, help="End page.")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Base URL template with {page} placeholder.",
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="CSV output path.")
    parser.add_argument(
        "--cookie-file",
        default="",
        help="Path to Netscape cookie file (e.g. www.enfsolar.com_cookies.txt).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.8,
        help="Base delay between pages in seconds.",
    )
    parser.add_argument(
        "--jitter",
        type=float,
        default=0.7,
        help="Extra random delay added to base delay.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Retries per page when a request fails.",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=2.0,
        help="Base delay between retries.",
    )
    parser.add_argument(
        "--retry-jitter",
        type=float,
        default=1.0,
        help="Extra random delay added to retry delay.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="Timeout per request in seconds.",
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "urllib", "selenium"],
        default="auto",
        help="Fetch mode: urllib, selenium, or auto fallback.",
    )
    parser.add_argument(
        "--browser",
        choices=["auto", "chrome", "edge"],
        default="auto",
        help="Selenium browser choice.",
    )
    parser.add_argument(
        "--debugger-address",
        default="",
        help="Attach to an existing Chrome/Edge with --remote-debugging-port.",
    )
    parser.add_argument(
        "--user-agent",
        default="",
        help="Override the User-Agent header.",
    )
    parser.add_argument(
        "--accept-language",
        default="en-US,en;q=0.9",
        help="Accept-Language header value.",
    )
    parser.add_argument(
        "--headless",
        dest="headless",
        action="store_true",
        help="Run Selenium in headless mode.",
    )
    parser.add_argument(
        "--no-headless",
        dest="headless",
        action="store_false",
        help="Run Selenium with a visible browser.",
    )
    parser.set_defaults(headless=True)
    parser.add_argument(
        "--selenium-wait",
        type=float,
        default=12.0,
        help="Seconds to wait for the table when using Selenium.",
    )
    parser.add_argument(
        "--user-data-dir",
        default="",
        help="Chrome/Edge user data dir to reuse a real profile.",
    )
    parser.add_argument(
        "--profile-directory",
        default="",
        help="Profile directory name inside user data (e.g. Default, Profile 1).",
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Pause when blocked so you can solve in the browser.",
    )
    parser.add_argument(
        "--manual-retries",
        type=int,
        default=2,
        help="How many times to pause for manual solving when blocked.",
    )
    parser.add_argument(
        "--manual-wait",
        type=float,
        default=1.5,
        help="Seconds to wait after manual solving before rechecking.",
    )
    parser.add_argument(
        "--humanize",
        dest="humanize",
        action="store_true",
        help="Add small waits and scrolls while using Selenium.",
    )
    parser.add_argument(
        "--no-humanize",
        dest="humanize",
        action="store_false",
        help="Disable human-like waits and scrolling.",
    )
    parser.set_defaults(humanize=True)
    parser.add_argument(
        "--human-min-wait",
        type=float,
        default=0.6,
        help="Minimum wait time after page load in Selenium.",
    )
    parser.add_argument(
        "--human-max-wait",
        type=float,
        default=1.8,
        help="Maximum wait time after page load in Selenium.",
    )
    parser.add_argument(
        "--paginate",
        action="store_true",
        help="Use Selenium to click the Next button instead of direct URL loads.",
    )
    parser.add_argument(
        "--scroll-steps",
        type=int,
        default=4,
        help="Max scroll steps for Selenium humanization.",
    )

    args = parser.parse_args()

    random.seed()
    cookie_file = args.cookie_file.strip()
    if not cookie_file and os.path.isfile(DEFAULT_COOKIE_FILE):
        cookie_file = DEFAULT_COOKIE_FILE

    cookie_jar = None
    if cookie_file:
        cookie_jar = load_cookie_jar(cookie_file)
        if not cookie_jar:
            print(
                f"Cookie file not found: {cookie_file}. Continuing without cookies.",
                file=sys.stderr,
            )
    explicit_ua = args.user_agent.strip()
    if explicit_ua:
        urllib_user_agent = explicit_ua
    elif cookie_file:
        urllib_user_agent = DEFAULT_UA
    else:
        urllib_user_agent = random.choice(USER_AGENTS)
    if explicit_ua:
        selenium_user_agent = explicit_ua
    elif args.debugger_address:
        selenium_user_agent = ""
    elif args.user_data_dir:
        selenium_user_agent = ""
    elif cookie_file:
        selenium_user_agent = DEFAULT_UA
    else:
        selenium_user_agent = urllib_user_agent
    headers = {
        "User-Agent": urllib_user_agent,
        "Accept-Language": args.accept_language,
        "Referer": "https://www.enfsolar.com/",
    }
    opener, opener_jar = make_opener()
    if cookie_jar:
        for c in cookie_jar:
            opener_jar.set_cookie(c)

    seen = set()
    rows = []
    driver = None
    use_selenium = args.mode == "selenium"
    cookies_applied = False
    selenium_page = None

    try:
        for page in range(args.start, args.end + 1):
            url = args.base_url.format(page=page)
            if not use_selenium:
                try:
                    html, status, blocked = fetch_html_urllib(
                        url,
                        opener,
                        headers,
                        args.timeout,
                        args.retries,
                        args.retry_delay,
                        args.retry_jitter,
                    )
                except Exception as exc:
                    if args.mode == "auto":
                        print(
                            f"Request failed for page {page}: {exc}. "
                            "Switching to Selenium.",
                            file=sys.stderr,
                        )
                        use_selenium = True
                        driver = create_webdriver(
                            selenium_user_agent,
                            args.headless,
                            args.user_data_dir,
                            args.profile_directory,
                            args.browser,
                            args.debugger_address,
                        )
                        if cookie_jar and not cookies_applied:
                            applied = apply_cookies_to_driver(
                                driver, cookie_jar, DEFAULT_HOME_URL
                            )
                            cookies_applied = True
                            if applied:
                                print(
                                    f"Loaded {applied} cookies into Selenium.",
                                    file=sys.stderr,
                                )
                        navigate = True
                        html, blocked = fetch_html_selenium(
                            url,
                            driver,
                            args.selenium_wait,
                            args.humanize,
                            args.human_min_wait,
                            args.human_max_wait,
                            args.scroll_steps,
                            args.manual,
                            args.manual_retries,
                            args.manual_wait,
                            navigate,
                        )
                        selenium_page = page
                    else:
                        raise

                if blocked and args.mode == "auto":
                    print(
                        f"Blocked on page {page} (status {status}). "
                        "Switching to Selenium.",
                        file=sys.stderr,
                    )
                    use_selenium = True
                    driver = create_webdriver(
                        selenium_user_agent,
                        args.headless,
                        args.user_data_dir,
                        args.profile_directory,
                        args.browser,
                        args.debugger_address,
                    )
                    if cookie_jar and not cookies_applied:
                        applied = apply_cookies_to_driver(
                            driver, cookie_jar, DEFAULT_HOME_URL
                        )
                        cookies_applied = True
                        if applied:
                            print(
                                f"Loaded {applied} cookies into Selenium.",
                                file=sys.stderr,
                            )
                    navigate = True
                    html, blocked = fetch_html_selenium(
                        url,
                        driver,
                        args.selenium_wait,
                        args.humanize,
                        args.human_min_wait,
                        args.human_max_wait,
                        args.scroll_steps,
                        args.manual,
                        args.manual_retries,
                        args.manual_wait,
                        navigate,
                    )
                    selenium_page = page
                elif blocked:
                    raise RuntimeError(
                        f"Blocked on page {page} (status {status}). "
                        "Try --mode selenium."
                    )
            else:
                if driver is None:
                    driver = create_webdriver(
                        selenium_user_agent,
                        args.headless,
                        args.user_data_dir,
                        args.profile_directory,
                        args.browser,
                        args.debugger_address,
                    )
                if cookie_jar and not cookies_applied:
                    applied = apply_cookies_to_driver(
                        driver, cookie_jar, DEFAULT_HOME_URL
                    )
                    cookies_applied = True
                    if applied:
                        print(
                            f"Loaded {applied} cookies into Selenium.",
                            file=sys.stderr,
                        )
                navigate = True
                if args.paginate and selenium_page is not None and page == selenium_page + 1:
                    if go_next_page(driver):
                        navigate = False
                html, blocked = fetch_html_selenium(
                    url,
                    driver,
                    args.selenium_wait,
                    args.humanize,
                    args.human_min_wait,
                    args.human_max_wait,
                    args.scroll_steps,
                    args.manual,
                    args.manual_retries,
                    args.manual_wait,
                    navigate,
                )
                selenium_page = page
                if blocked:
                    if args.manual:
                        raise RuntimeError(
                            f"Blocked on page {page} even after manual attempts. "
                            "Try --user-data-dir or increase --delay/--jitter."
                        )
                    raise RuntimeError(
                        f"Blocked on page {page}. "
                        "Try --manual and/or --user-data-dir."
                    )

            links = extract_links(html)
            for link in links:
                full = urljoin("https://www.enfsolar.com", link)
                if full in seen:
                    continue
                seen.add(full)
                rows.append([full])

            sleep_with_jitter(args.delay, args.jitter)
    finally:
        if driver is not None:
            driver.quit()

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["href"])
        writer.writerows(rows)

    print(f"Wrote {len(rows)} links to {args.output}")


if __name__ == "__main__":
    main()
