from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import pandas as pd
import pickle
import time
import os
from pathlib import Path
import unicodedata

chrome_options = Options()
chrome_options.add_argument('--disable-blink-features=AutomationControlled')
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option('useAutomationExtension', False)

driver = webdriver.Chrome(options=chrome_options)

url = "https://baseball.fantasysports.yahoo.com/b1/59082/draftanalysis?pos=ALL"
SCRIPT_DIR = Path(__file__).resolve().parent
COOKIE_FILE = SCRIPT_DIR / "yahoo_cookies.pkl"


def wait_for_rows(driver, timeout=30):
    """Wait until draft-analysis rows are visible (table or grid layouts)."""
    row_selectors = [
        "table tbody tr",
        "[role='rowgroup'] [role='row']",
        "div[role='row']"
    ]
    end_time = time.time() + timeout
    while time.time() < end_time:
        for selector in row_selectors:
            rows = driver.find_elements(By.CSS_SELECTOR, selector)
            rows = [r for r in rows if r.is_displayed()]
            if rows:
                return rows
        time.sleep(0.5)
    raise Exception("Timed out waiting for Yahoo player rows to load")


def is_login_page(driver):
    current_url = driver.current_url.lower()
    page_text = driver.page_source.lower()
    return "login.yahoo.com" in current_url or ("sign in" in page_text and "yahoo" in page_text)


def save_cookies(driver):
    pickle.dump(driver.get_cookies(), open(COOKIE_FILE, 'wb'))
    print(f"Saved cookies to {COOKIE_FILE}")


def load_cookies(driver):
    if not COOKIE_FILE.exists():
        return

    driver.get("https://baseball.fantasysports.yahoo.com")
    raw_cookies = pickle.load(open(COOKIE_FILE, 'rb'))
    loaded = 0

    for cookie in raw_cookies:
        c = dict(cookie)
        # Selenium expects int expiry when present.
        if 'expiry' in c:
            try:
                c['expiry'] = int(c['expiry'])
            except Exception:
                c.pop('expiry', None)
        # Avoid domain collisions; let browser infer for current host.
        c.pop('domain', None)

        try:
            driver.add_cookie(c)
            loaded += 1
        except Exception:
            continue

    print(f"Loaded {loaded} cookies from {COOKIE_FILE}")


def wait_for_manual_login(driver, timeout=240):
    print("Yahoo login detected. Complete login in the browser window.")
    end_time = time.time() + timeout
    while time.time() < end_time:
        if not is_login_page(driver):
            print("Login complete. Continuing scrape...")
            return
        time.sleep(2)
    raise Exception("Login was not completed before timeout.")


def safe_text(cells, idx):
    return cells[idx].text.strip() if idx < len(cells) else ""


def normalize_player_name(name):
    normalized = unicodedata.normalize('NFKD', name)
    return ''.join(ch for ch in normalized if not unicodedata.combining(ch)).strip()

load_cookies(driver)

driver.get(url)

print("Waiting for page to load...")
time.sleep(3)
if is_login_page(driver):
    wait_for_manual_login(driver)

save_cookies(driver)

players_data = []
target_players = 350
page_num = 1

try:
    while len(players_data) < target_players:
        print(f"\n{'='*60}")
        print(f"Scraping page {page_num}...")
        print(f"{'='*60}")
        
        rows = wait_for_rows(driver, timeout=30)
        print(f"Found {len(rows)} rows on this page")
        
        page_players = 0
        
        for idx, row in enumerate(rows):
            try:
                cells = row.find_elements(By.TAG_NAME, "td")
                if not cells:
                    cells = row.find_elements(By.CSS_SELECTOR, "[role='cell']")
                
                if len(cells) < 2:
                    continue
                
                cell_0_text = cells[0].text.strip()
                
                if not cell_0_text:
                    continue
                
                parts = cell_0_text.split('\n')
                player_name = normalize_player_name(parts[0]) if len(parts) > 0 else ""
                team_pos = parts[1] if len(parts) > 1 else ""
                
                if not player_name:
                    continue
                
                rank = safe_text(cells, 1)
                pos_rank = safe_text(cells, 2)
                cer = safe_text(cells, 3)
                pct_drafted = safe_text(cells, 4)
                preseason_adp = safe_text(cells, 5)
                all_drafts_adp = safe_text(cells, 6)
                last_7_days = safe_text(cells, 7)
                
                players_data.append({
                    'Player': player_name,
                    'Team_Position': team_pos,
                    'Rank': rank,
                    'Pos_Rank': pos_rank,
                    'CER': cer,
                    'Pct_Drafted': pct_drafted,
                    'Preseason_ADP': preseason_adp,
                    'All_Drafts_ADP': all_drafts_adp,
                    'Last_7_Days': last_7_days
                })
                
                page_players += 1
                    
            except Exception as e:
                continue
        
        print(f"Scraped {page_players} players from this page")
        print(f"Total players so far: {len(players_data)}")
        
        if len(players_data) >= target_players:
            print(f"\nReached target of {target_players} players!")
            break
        
        # Scroll to bottom to make sure pagination is visible
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        if is_login_page(driver):
            wait_for_manual_login(driver, timeout=300)
            driver.get(url)
            rows = wait_for_rows(driver, timeout=30)
            print(f"Re-loaded page after login, rows found: {len(rows)}")
        
        # Try multiple methods to find and click Next button
        clicked = False
        
        # Method 1: Find all buttons with caret-right SVG that are NOT disabled
        try:
            buttons = driver.find_elements(By.XPATH, "//button[.//svg[@data-icon='caret-right']]")
            for button in buttons:
                if not button.get_attribute('disabled'):
                    print("Found enabled Next button (Method 1)")
                    driver.execute_script("arguments[0].scrollIntoView(true);", button)
                    time.sleep(0.5)
                    button.click()
                    clicked = True
                    break
        except Exception as e:
            print(f"Method 1 failed: {e}")
        
        # Method 2: Use JavaScript to click
        if not clicked:
            try:
                script = """
                var buttons = document.querySelectorAll('button[role="presentation"]');
                for (var i = 0; i < buttons.length; i++) {
                    var svg = buttons[i].querySelector('svg[data-icon="caret-right"]');
                    if (svg && !buttons[i].disabled) {
                        buttons[i].click();
                        return true;
                    }
                }
                return false;
                """
                result = driver.execute_script(script)
                if result:
                    print("Clicked Next button (Method 2 - JavaScript)")
                    clicked = True
            except Exception as e:
                print(f"Method 2 failed: {e}")
        
        # Method 3: Find by class and role
        if not clicked:
            try:
                buttons = driver.find_elements(By.CSS_SELECTOR, "button[role='presentation']")
                for button in buttons:
                    svg = button.find_elements(By.TAG_NAME, "svg")
                    if svg and 'caret-right' in svg[0].get_attribute('data-icon') if svg[0].get_attribute('data-icon') else '':
                        if not button.get_attribute('disabled'):
                            print("Found Next button (Method 3)")
                            button.click()
                            clicked = True
                            break
            except Exception as e:
                print(f"Method 3 failed: {e}")

        # Method 4: aria-label based next button
        if not clicked:
            try:
                buttons = driver.find_elements(By.XPATH, "//button[contains(translate(@aria-label,'NEXT','next'),'next')]")
                for button in buttons:
                    if button.is_displayed() and not button.get_attribute('disabled'):
                        driver.execute_script("arguments[0].click();", button)
                        print("Clicked Next button (Method 4 - aria-label)")
                        clicked = True
                        break
            except Exception as e:
                print(f"Method 4 failed: {e}")
        
        if clicked:
            print("Successfully clicked Next button")
            time.sleep(3)
            page_num += 1
        else:
            print("\nCould not find or click Next button. Reached last page.")
            break
    
except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()

driver.quit()

if len(players_data) > 0:
    df = pd.DataFrame(players_data)
    df = df.head(target_players)
    
    print(f"\n{'='*60}")
    print(f"SCRAPING COMPLETE")
    print(f"{'='*60}")
    print(f"\nTotal players scraped: {len(df)}")
    print("\nFirst 10 players:")
    print(df.head(10))
    print("\nLast 10 players:")
    print(df.tail(10))
    
    df.to_csv('./Hitters/yahoo_adp_data.csv', index=False)
    print(f"\nSaved {len(df)} players to yahoo_adp_data.csv")
else:
    print("\nNo data scraped")
