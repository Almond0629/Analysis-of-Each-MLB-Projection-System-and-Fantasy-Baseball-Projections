from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.common.exceptions import TimeoutException
import pandas as pd
import time
import unicodedata


chrome_options = Options()
chrome_options.add_argument('--disable-blink-features=AutomationControlled')

driver = webdriver.Chrome(options=chrome_options)

# Projection systems
projection_systems = [
    ('ZIPS',         'zips'),
    ('ZiPS_DC',      'zipsdc'),
    ('Steamer',      'steamer'),
    ('DC',           'fangraphsdc'),
    ('ATC',          'atc'),
    ('THE_BAT',      'thebat'),
    ('THE_BAT_X',    'thebatx'),
    ('OOPSY',        'oopsy')
]

# Advanced stats to scrape from the Advanced tab (in this order)
ADVANCED_STATS = ['K/9', 'BB/9', 'WHIP', 'K%', 'BB%']

TOP_N = 240
TOP_N_BY_SYSTEM = {
    'zips': 360
}
WAYBACK_BASE = "https://web.archive.org/web"
TARGET_TIMESTAMP = "20250309215547"
WAYBACK_CALENDAR_URL = "https://web.archive.org/web/20250815000000*/https://www.fangraphs.com/projections"

def normalize_player_name(name):
    if not name:
        return name
    normalized = unicodedata.normalize('NFKD', name)
    return ''.join(ch for ch in normalized if not unicodedata.combining(ch)).strip()

def get_top_n(proj_type):
    return TOP_N_BY_SYSTEM.get(proj_type, TOP_N)

def build_live_projection_url(proj_type):
    return f"https://www.fangraphs.com/projections?type={proj_type}&stats=rel&pos=all&team=0&players=0&lg=all&z=1741513688&pageitems=30&statgroup=standard&fantasypreset=dashboard"

def wayback_url(timestamp, live_url):
    return f"{WAYBACK_BASE}/{timestamp}/{live_url}"

def open_wayback_snapshot():
    """Open the calendar page, click Mar 9, 2025, then click 21:55:47 snapshot."""
    print("\n[Wayback Navigation]")
    print(f"Opening calendar page: {WAYBACK_CALENDAR_URL}")
    driver.get(WAYBACK_CALENDAR_URL)

    try:
        day_link = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//a[contains(@href,'/web/20250309/https://www.fangraphs.com/projections') and normalize-space()='9']"
                )
            )
        )
        driver.execute_script("arguments[0].click();", day_link)
        print("Clicked March 9, 2025 day link")
        time.sleep(2)
    except TimeoutException:
        print("Could not click calendar day link; falling back to direct timestamp URL.")

    # In many Wayback views, clicking the day immediately opens a replay page
    # (not the timeline panel with per-second links). Handle that first.
    if "fangraphs.com/projections" in driver.current_url:
        print("Day click already landed on target snapshot replay page.")
        print(f"Reached snapshot URL: {driver.current_url}")
        return

    try:
        snapshot_link = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//a[contains(@href,'/web/20250309215547/https://www.fangraphs.com/projections') or normalize-space()='21:55:47']"
                )
            )
        )
        driver.execute_script("arguments[0].click();", snapshot_link)
        print("Clicked snapshot 21:55:47")
    except TimeoutException:
        fallback = "https://web.archive.org/web/20250309215547/https://www.fangraphs.com/projections"
        print(f"Snapshot link not clickable in timeline UI; opening direct URL: {fallback}")
        driver.get(fallback)

    # Do not require exact timestamp in URL; Wayback may redirect to nearby captures.
    WebDriverWait(driver, 30).until(
        lambda d: "fangraphs.com/projections" in d.current_url
    )
    print(f"Reached archived projections URL: {driver.current_url}")

def set_page_size_infinity():
    try:
        select_element = driver.find_element(By.CSS_SELECTOR, "select")
        select = Select(select_element)
        select.select_by_value("2000000000")
        print("  Set page size to Infinity")
        time.sleep(15)
        return True
    except Exception as e:
        print(f"  Could not set page size: {e}")
        return False

def set_pitchers_rp_filters():
    """On archived Fangraphs page, click Pitchers and set Position to RP."""
    try:
        print("  Setting filters: Pitchers -> RP")

        # Click Pitchers tab/button.
        clicked_pitchers = False
        pitchers_xpaths = [
            "//a[normalize-space()='Pitchers']",
            "//button[normalize-space()='Pitchers']",
            "//label[normalize-space()='Pitchers']",
            "//*[contains(@class,'tab') and normalize-space()='Pitchers']"
        ]
        for xp in pitchers_xpaths:
            elems = driver.find_elements(By.XPATH, xp)
            for elem in elems:
                if elem.is_displayed():
                    driver.execute_script("arguments[0].click();", elem)
                    clicked_pitchers = True
                    break
            if clicked_pitchers:
                break
        if clicked_pitchers:
            time.sleep(2)
            print("  Clicked Pitchers")
        else:
            print("  Could not explicitly click Pitchers (continuing)")

        # Set Position to RP (select or custom dropdown).
        rp_set = False
        try:
            selects = driver.find_elements(By.TAG_NAME, "select")
            for sel in selects:
                options = sel.find_elements(By.TAG_NAME, "option")
                for opt in options:
                    if opt.text.strip() == "RP":
                        Select(sel).select_by_visible_text("RP")
                        rp_set = True
                        break
                if rp_set:
                    break
        except Exception:
            pass

        if not rp_set:
            # Fallback for custom dropdown controls.
            try:
                pos_controls = driver.find_elements(
                    By.XPATH,
                    "//*[contains(translate(normalize-space(.),'POSITION','position'),'position')]"
                )
                for ctrl in pos_controls:
                    if ctrl.is_displayed():
                        driver.execute_script("arguments[0].click();", ctrl)
                        time.sleep(0.5)
                        rp_option = driver.find_element(By.XPATH, "//*[normalize-space()='RP']")
                        driver.execute_script("arguments[0].click();", rp_option)
                        rp_set = True
                        break
            except Exception:
                pass

        if rp_set:
            print("  Set Position to RP")
        else:
            print("  Could not explicitly set Position to RP (continuing)")

        time.sleep(3)
        return True
    except Exception as e:
        print(f"  Error setting Pitchers/RP filters: {e}")
        return False

def navigate_archived_projection_to_rp(proj_name, proj_type):
    """Navigate archived UI: Pitchers -> projection system -> RP."""
    try:
        print("  Navigating archived UI: Pitchers -> Projection -> RP")

        # 1) Click Pitchers
        pitchers_link = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//a[contains(@href,'stats=pit') and normalize-space()='Pitchers']"
                )
            )
        )
        driver.execute_script("arguments[0].click();", pitchers_link)
        time.sleep(2)
        print("  Clicked Pitchers")

        # 2) Click projection system by projection type (e.g., type=zipsdc).
        # Wayback-rewritten hrefs are inconsistent, so scan links manually.
        WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((By.TAG_NAME, "a"))
        )
        anchors = driver.find_elements(By.TAG_NAME, "a")
        target = None
        proj_name_variants = {
            'ZiPS_DC': ['zips dc', 'zipsdc'],
            'THE_BAT_X': ['the bat x', 'thebatx'],
            'THE_BAT': ['the bat', 'thebat'],
            'DC': ['dc', 'depth charts']
        }
        name_variants = proj_name_variants.get(proj_name, [proj_name.lower().replace('_', ' ')])

        for a in anchors:
            href = (a.get_attribute("href") or "").lower()
            text = (a.text or "").strip().lower()
            if not href:
                continue
            if f"type={proj_type}" in href:
                target = a
                break
            if any(v in text for v in name_variants):
                target = a
                break

        if not target:
            print("  Could not find projection link by href/text. Sample links:")
            for a in anchors[:20]:
                print(f"    text='{(a.text or '').strip()}' href='{(a.get_attribute('href') or '')[:140]}'")
            return False

        driver.execute_script("arguments[0].scrollIntoView(true);", target)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", target)
        time.sleep(2)
        print(f"  Clicked projection system: {proj_name} ({proj_type}) -> {(target.get_attribute('href') or '')[:120]}")

        # 3) Click RP in Position dropdown
        # If RP is already selected, continue.
        rp_selected = driver.find_elements(
            By.XPATH,
            "//div[contains(@class,'fg-selection-box__label')]//span[normalize-space()='RP']"
        )
        if rp_selected:
            print("  RP already selected")
            return True

        # Open a selection box (Position filter control).
        labels = driver.find_elements(By.XPATH, "//div[contains(@class,'fg-selection-box__label')]")
        opened = False
        for label in labels:
            try:
                if label.is_displayed():
                    driver.execute_script("arguments[0].click();", label)
                    opened = True
                    time.sleep(0.5)
                    break
            except Exception:
                continue
        if not opened:
            print("  Could not open position dropdown")
            return False

        rp_option = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//*[normalize-space()='RP' and (self::div or self::span or self::li)]"
                )
            )
        )
        driver.execute_script("arguments[0].click();", rp_option)
        time.sleep(2)
        print("  Selected RP")
        return True

    except Exception as e:
        print(f"  Archived UI navigation failed for {proj_name}: {e}")
        return False

def find_player_table():
    """Find the main player projection table on the page."""
    tables = driver.find_elements(By.TAG_NAME, "table")
    player_table = None

    for tbl in tables:
        try:
            tbody = tbl.find_element(By.TAG_NAME, "tbody")
            rows = tbody.find_elements(By.TAG_NAME, "tr")

            if len(rows) > 5:
                for check_row in rows[:5]:
                    player_links = check_row.find_elements(By.CSS_SELECTOR, "a[href*='playerid']")
                    if player_links:
                        player_table = tbl
                        break
                if player_table:
                    break
        except:
            continue

    # Fallback
    if not player_table:
        for tbl in tables:
            try:
                tbody = tbl.find_element(By.TAG_NAME, "tbody")
                rows = tbody.find_elements(By.TAG_NAME, "tr")
                if len(rows) > 0:
                    first_row_text = rows[0].text[:150]
                    if any(name in first_row_text.lower() for name in ['duran', 'jax', 'miller', 'smith', 'taylor']):
                        player_table = tbl
                        break
            except:
                continue

    return player_table

def log_source_row_availability(proj_name, proj_type, url):
    """Log table/row availability for a projection URL before scraping."""
    print("  [Availability Check]")
    print(f"  URL: {url}")

    tables = driver.find_elements(By.TAG_NAME, "table")
    print(f"  Tables found: {len(tables)}")

    player_table = find_player_table()
    if not player_table:
        print(f"  Source rows available: NO ({proj_name}/{proj_type})")
        return 0

    try:
        tbody = player_table.find_element(By.TAG_NAME, "tbody")
        rows = tbody.find_elements(By.TAG_NAME, "tr")
        player_link_rows = 0
        for row in rows[: min(len(rows), 25)]:
            links = row.find_elements(By.CSS_SELECTOR, "a[href*='playerid']")
            if links:
                player_link_rows += 1

        print(f"  Source rows available: YES ({proj_name}/{proj_type})")
        print(f"  Row count in detected table: {len(rows)}")
        print(f"  Rows with player links (first 25 rows): {player_link_rows}")
        return len(rows)
    except Exception as e:
        print(f"  Source rows check failed ({proj_name}/{proj_type}): {e}")
        return 0

def scrape_full_standard_table(top_n):
    """Scrape all columns from the standard table dynamically.
    Returns list of dicts ordered as on page, keyed by player name."""
    records = []

    try:
        player_table = find_player_table()

        if not player_table:
            print("  ✗ Could not find player table")
            return records

        # Get all column headers dynamically
        headers = player_table.find_elements(By.TAG_NAME, "th")
        col_map = {}  # data-stat -> display name
        for th in headers:
            stat = th.get_attribute('data-stat')
            if stat:
                col_map[stat] = stat

        print(f"  Found columns: {list(col_map.keys())}")

        tbody = player_table.find_element(By.TAG_NAME, "tbody")
        rows = tbody.find_elements(By.TAG_NAME, "tr")
        print(f"  Found {len(rows)} total rows, scraping top {top_n}...")

        for row in rows[:top_n]:
            try:
                # Get player name
                player_name = None
                try:
                    name_link = row.find_element(By.CSS_SELECTOR, "a[href*='playerid']")
                    player_name = name_link.text.strip()
                except:
                    try:
                        name_cell = row.find_element(By.CSS_SELECTOR, "td[data-stat='Name']")
                        player_name = name_cell.text.strip()
                    except:
                        pass

                if not player_name:
                    continue

                # Scrape every td with a data-stat attribute
                record = {}
                cells = row.find_elements(By.TAG_NAME, "td")
                for cell in cells:
                    stat = cell.get_attribute('data-stat')
                    if stat:
                        record[stat] = cell.text.strip()

                # Keep normalized name in-place on Name column.
                record['Name'] = normalize_player_name(player_name)
                records.append(record)

            except:
                continue

        print(f"  ✓ Scraped {len(records)} players from Standard tab")

    except Exception as e:
        print(f"  Error scraping standard table: {e}")
        import traceback
        traceback.print_exc()

    return records

def click_advanced_tab():
    """Click the Advanced tab."""
    try:
        # Try by class name
        advanced_tabs = driver.find_elements(By.CSS_SELECTOR, "a.FGControlTab_fg-control-tab__ydGw5")
        for tab in advanced_tabs:
            if 'Advanced' in tab.text:
                driver.execute_script("arguments[0].scrollIntoView(true);", tab)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", tab)
                print("  Clicked Advanced tab")
                time.sleep(5)
                return True

        # Fallback: find by text
        tabs = driver.find_elements(By.XPATH, "//a[text()='Advanced']")
        if tabs:
            driver.execute_script("arguments[0].click();", tabs[0])
            print("  Clicked Advanced tab (fallback)")
            time.sleep(5)
            return True

        print("  ✗ Could not find Advanced tab")
        return False

    except Exception as e:
        print(f"  Error clicking Advanced tab: {e}")
        return False

def scrape_advanced_stats(top_n):
    """Scrape only ADVANCED_STATS from the advanced tab.
    Returns dict: { player_name: { stat: value } }"""
    adv_data = {}

    try:
        player_table = find_player_table()

        if not player_table:
            print("  ✗ Could not find player table on Advanced tab")
            return adv_data

        tbody = player_table.find_element(By.TAG_NAME, "tbody")
        rows = tbody.find_elements(By.TAG_NAME, "tr")
        print(f"  Found {len(rows)} rows on Advanced tab")

        for row in rows[:top_n]:
            try:
                player_name = None
                try:
                    name_link = row.find_element(By.CSS_SELECTOR, "a[href*='playerid']")
                    player_name = name_link.text.strip()
                except:
                    try:
                        name_cell = row.find_element(By.CSS_SELECTOR, "td[data-stat='Name']")
                        player_name = name_cell.text.strip()
                    except:
                        pass

                if not player_name:
                    continue

                adv_record = {}
                for stat in ADVANCED_STATS:
                    try:
                        cell = row.find_element(By.CSS_SELECTOR, f"td[data-stat='{stat}']")
                        adv_record[stat] = cell.text.strip()
                    except:
                        adv_record[stat] = None

                adv_data[normalize_player_name(player_name)] = adv_record

            except:
                continue

        print(f"  ✓ Scraped advanced stats for {len(adv_data)} players")

    except Exception as e:
        print(f"  Error scraping advanced stats: {e}")

    return adv_data


# Navigate Wayback UI once to ensure the target snapshot is reachable.
open_wayback_snapshot()

# Process one projection system at a time
for proj_name, proj_type in projection_systems:
    print(f"\n{'='*60}")
    print(f"Scraping {proj_name}...")
    print(f"{'='*60}")

    try:
        top_n = get_top_n(proj_type)
        # Always start each projection from the same archived projections page,
        # then use UI navigation to choose Pitchers -> Projection -> RP.
        url = "https://web.archive.org/web/20250309215547/https://www.fangraphs.com/projections"
        driver.get(url)
        time.sleep(8)
        if not navigate_archived_projection_to_rp(proj_name, proj_type):
            print(f"  ⚠ Could not navigate archived filters for {proj_name}. Skipping.")
            continue

        available_rows = log_source_row_availability(proj_name, proj_type, url)
        if available_rows == 0:
            print(f"  ⚠ No source rows detected for {proj_name}. Skipping scrape.")
            continue
        print(f"  Using archive snapshot: {url}")

        # Set page to Infinity
        set_page_size_infinity()

        # --- Scrape Standard tab (full table) ---
        print("\n  [Standard Tab]")
        standard_records = scrape_full_standard_table(top_n)

        if not standard_records:
            print(f"  ✗ No standard data scraped for {proj_name}, skipping...")
            continue

        # Build DataFrame from standard tab
        proj_df = pd.DataFrame(standard_records)
        if 'Name' in proj_df.columns:
            proj_df['Name'] = proj_df['Name'].map(normalize_player_name)
        elif 'Player' in proj_df.columns:
            proj_df['Name'] = proj_df['Player'].map(normalize_player_name)
        else:
            proj_df['Name'] = ''

        # Ensure only one normalized name column in output.
        if 'Player' in proj_df.columns:
            proj_df = proj_df.drop(columns=['Player'])

        # --- Click Advanced tab and scrape ---
        print("\n  [Advanced Tab]")
        clicked = click_advanced_tab()

        if clicked:
            adv_data = scrape_advanced_stats(top_n)

            # Merge advanced stats into proj_df in specified order
            for stat in ADVANCED_STATS:
                proj_df[stat] = proj_df['Name'].map(
                    lambda p: adv_data.get(p, {}).get(stat)
                )

            print(f"  Merged advanced stats: {ADVANCED_STATS}")
        else:
            print("  ⚠ Skipping advanced stats")

        # Add ranking index at the front of Name.
        proj_df['#'] = range(1, len(proj_df) + 1)
        cols = list(proj_df.columns)
        cols.remove('#')
        cols.insert(cols.index('Name'), '#')
        proj_df = proj_df[cols]

    except Exception as e:
        print(f"  Error processing {proj_name}: {e}")
        import traceback
        traceback.print_exc()
        continue

    # Save to CSV
    filename = f"./{proj_name}/2025_{proj_name}_Projections.csv"
    proj_df.to_csv(filename, index=False)
    print(f"\n  ✓ Saved {len(proj_df)} players to {filename}")
    print(f"  Columns: {list(proj_df.columns)}")

driver.quit()
print(f"\n{'='*60}")
print("All projection systems scraped and saved!")
print("="*60)
