from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
import pandas as pd
import time
import unicodedata


chrome_options = Options()
chrome_options.add_argument('--disable-blink-features=AutomationControlled')

driver = webdriver.Chrome(options=chrome_options)

# Projection systems
projection_systems = [
    ('THE_BAT_X',    'thebatx')
]

# Advanced stats to scrape from the Advanced tab (in this order)
ADVANCED_STATS = ['K/9', 'BB/9', 'WHIP', 'K%', 'BB%']
FANTASY_STATS = ['QS']

TOP_N = 240
TOP_N_BY_SYSTEM = {
    'zips': 360
}

def normalize_player_name(name):
    if not name:
        return name
    normalized = unicodedata.normalize('NFKD', name)
    return ''.join(ch for ch in normalized if not unicodedata.combining(ch)).strip()

def get_top_n(proj_type):
    return TOP_N_BY_SYSTEM.get(proj_type, TOP_N)

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
                    if any(name in first_row_text.lower() for name in ['skubal', 'skenes', 'crochet']):
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

def click_fantasy_tab():
    """Click the Fantasy tab."""
    try:
        # Try by class name
        fantasy_tabs = driver.find_elements(By.CSS_SELECTOR, "a.FGControlTab_fg-control-tab__ydGw5")
        for tab in fantasy_tabs:
            if 'Fantasy' in tab.text:
                driver.execute_script("arguments[0].scrollIntoView(true);", tab)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", tab)
                print("  Clicked Fantasy tab")
                time.sleep(5)
                return True

        # Fallback: find by text
        tabs = driver.find_elements(By.XPATH, "//a[text()='Fantasy']")
        if tabs:
            driver.execute_script("arguments[0].click();", tabs[0])
            print("  Clicked Fantasy tab (fallback)")
            time.sleep(5)
            return True

        print("  ✗ Could not find Fantasy tab")
        return False

    except Exception as e:
        print(f"  Error clicking Fantasy tab: {e}")
        return False

def scrape_fantasy_stats(top_n):
    """Scrape only FANTASY_STATS from the fantasy tab.
    Returns dict: { player_name: { stat: value } }"""
    fantasy_data = {}

    try:
        player_table = find_player_table()

        if not player_table:
            print("  ✗ Could not find player table on Fantasy tab")
            return fantasy_data

        tbody = player_table.find_element(By.TAG_NAME, "tbody")
        rows = tbody.find_elements(By.TAG_NAME, "tr")
        print(f"  Found {len(rows)} rows on Fantasy tab")

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

                fantasy_record = {}
                for stat in FANTASY_STATS:
                    try:
                        cell = row.find_element(By.CSS_SELECTOR, f"td[data-stat='{stat}']")
                        fantasy_record[stat] = cell.text.strip()
                    except:
                        fantasy_record[stat] = None

                fantasy_data[normalize_player_name(player_name)] = fantasy_record

            except:
                continue

        print(f"  ✓ Scraped fantasy stats for {len(fantasy_data)} players")

    except Exception as e:
        print(f"  Error scraping fantasy stats: {e}")

    return fantasy_data

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


# Process one projection system at a time
for proj_name, proj_type in projection_systems:
    print(f"\n{'='*60}")
    print(f"Scraping {proj_name}...")
    print(f"{'='*60}")

    try:
        top_n = get_top_n(proj_type)
        url = f"https://www.fangraphs.com/projections?type={proj_type}&stats=sta&pos=all&team=0&players=0&lg=all&z=1772077514&pageitems=30&statgroup=standard&fantasypreset=dashboard"
        driver.get(url)
        time.sleep(8)

        available_rows = log_source_row_availability(proj_name, proj_type, url)
        if available_rows == 0:
            print(f"  ⚠ No source rows detected for {proj_name}. Skipping scrape.")
            continue

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
            advanced_data = scrape_advanced_stats(top_n)

            # Merge advanced stats into proj_df in specified order
            for stat in ADVANCED_STATS:
                proj_df[stat] = proj_df['Name'].map(
                    lambda p: advanced_data.get(p, {}).get(stat)
                )

            print(f"  Merged advanced stats: {ADVANCED_STATS}")
        else:
            print("  ⚠ Skipping advanced stats")

        # --- Click Fantasy tab and scrape ---
        print("\n  [Fantasy Tab]")
        clicked = click_fantasy_tab()

        if clicked:
            fantasy_data = scrape_fantasy_stats(top_n)

            # Merge fantasy stats into proj_df in specified order
            for stat in FANTASY_STATS:
                proj_df[stat] = proj_df['Name'].map(
                    lambda p: fantasy_data.get(p, {}).get(stat)
                )

            print(f"  Merged fantasy stats: {FANTASY_STATS}")
        else:
            print("  ⚠ Skipping fantasy stats")

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
    filename = f"./Starters/{proj_name}/2026_{proj_name}_Projections.csv"
    proj_df.to_csv(filename, index=False)
    print(f"\n  ✓ Saved {len(proj_df)} players to {filename}")
    print(f"  Columns: {list(proj_df.columns)}")

driver.quit()
print(f"\n{'='*60}")
print("All projection systems scraped and saved!")
print("="*60)
