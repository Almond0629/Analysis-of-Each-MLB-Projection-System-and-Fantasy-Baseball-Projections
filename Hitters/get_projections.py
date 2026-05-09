from pybaseball import *
import pandas as pd
from statistics import mean
import numpy as np
import unicodedata
from unidecode import unidecode
from pathlib import Path

'''
      batting_stats index:
      Season, Name, Team: 1~3
      G, AB, PA, H: 5~8, 2B: 10, HR: 12, AVG: 24, BB%: 35, K%: 36
      OBP, SLG, OPS, ISO, BABIP: 38~42
      LD%, GB%, FB%: 44~46
      
      Others:
      a = stats[0:15] is a Pandas Dataframe
      to_numpy() converts into a 2D Numpy array
'''
def find_player(name):
    name = name.split(' ', 1)
    player = playerid_lookup(name[1], name[0])
    if len(player) == 0: # check if player name is correct
        find_player = playerid_lookup(name[1], name[0], fuzzy=True)
        for j in range(len(find_player)):
            if find_player.iloc[j, 7] == 2022 or find_player.iloc[j, 7] == 2023 or find_player.iloc[j, 7] == 2024:
                return find_player.at[j, 'key_mlbam']
    if len(player) == 1:
        return player.at[0, 'key_mlbam']
    
def calculate_stats(df):
    df['OBP'] = (df['H'] + df['BB'] + df['HBP']) / (df['AB'] + df['BB'] + df['HBP'] + df['SF'])
    df['SLG'] = (df['1B'] + 2*df['2B'] + 3*df['3B'] + 4*df['HR']) / df['AB']
    df['OPS'] = df['OBP'] + df['SLG']
    df['BABIP'] = (df['H'] - df['HR']) / (df['AB'] - df['SO'] - df['HR'] + df['SF'])
    df['K%'] = df['SO'] / df['PA']
    df['BB%'] = df['BB'] / df['PA']
    df['K%'] = pd.to_numeric(df['K%'], errors='coerce') * 100
    df['BB%'] = pd.to_numeric(df['BB%'], errors='coerce') * 100
    return df

def scale_stats(df):
    columns_to_scale = df.columns.to_list()[4:22]   # ~NSB
    df['scaling_ratio'] = df['real_PA'] / df['PA']
    for col in columns_to_scale:
        df[col] = df[col] * df['scaling_ratio']
    df.drop(columns=['scaling_ratio'], inplace=True)
    return df

def format_name_to_fangraphs(name):
    if ',' in name:
        last, first = name.split(', ')
        return f'{first} {last}'
    return name

def normalize_name(name):
    return unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('utf-8')


def get_ab_pa_from_atc_for_fantasy_names(
    hitters_xlsx_path=None,
    atc_csv_path=None
):
    base_dir = Path(__file__).resolve().parent
    if hitters_xlsx_path is None:
        hitters_xlsx_path = base_dir / 'Fantasy' / '2026' / '2026_Fantasy_Hitters.xlsx'
    if atc_csv_path is None:
        atc_csv_path = base_dir / 'ATC' / '2026_ATC_Projections.csv'

    hitters_df = pd.read_excel(hitters_xlsx_path, usecols=['Name']).copy()
    atc_df = pd.read_csv(atc_csv_path, usecols=['Name', 'AB', 'PA']).copy()

    hitters_df['Name_key'] = hitters_df['Name'].map(normalize_name)
    atc_df['Name_key'] = atc_df['Name'].map(normalize_name)
    atc_df['AB'] = pd.to_numeric(atc_df['AB'], errors='coerce')
    atc_df['PA'] = pd.to_numeric(atc_df['PA'], errors='coerce')

    # Keep one AB/PA pair per normalized name to avoid duplicate-index mapping errors.
    atc_lookup = atc_df.groupby('Name_key', as_index=True)[['AB', 'PA']].mean()
    hitters_df['AB'] = hitters_df['Name_key'].map(atc_lookup['AB'])
    hitters_df['PA'] = hitters_df['Name_key'].map(atc_lookup['PA'])

    return hitters_df.drop(columns=['Name','Name_key'])


def create_projections(df, year=2026):
    base_dir = Path(__file__).resolve().parent

    def load_projection(proj):
        proj_path = base_dir / proj / f'{year}_{proj}_Projections.csv'
        proj_df = pd.read_csv(proj_path)
        proj_df['Name_key'] = proj_df['Name'].map(normalize_name)
        proj_df['HIP'] = proj_df['H'] - proj_df['HR']
        proj_df['1B%'] = proj_df['1B'] / proj_df['HIP'].replace(0, np.nan)
        proj_df['2B%'] = proj_df['2B'] / proj_df['HIP'].replace(0, np.nan)
        proj_df['3B%'] = proj_df['3B'] / proj_df['HIP'].replace(0, np.nan)
        proj_df['HR%'] = proj_df['HR'] / proj_df['PA'].replace(0, np.nan)
        proj_df['R%'] = proj_df['R'] / proj_df['PA'].replace(0, np.nan)
        proj_df['RBI%'] = proj_df['RBI'] / proj_df['PA'].replace(0, np.nan)
        proj_df['IBB%'] = proj_df['IBB'] / proj_df['PA'].replace(0, np.nan)
        proj_df['HBP%'] = proj_df['HBP'] / proj_df['PA'].replace(0, np.nan)
        proj_df['SF%'] = proj_df['SF'] / proj_df['PA'].replace(0, np.nan)
        proj_df['SH%'] = proj_df['SH'] / proj_df['PA'].replace(0, np.nan)
        proj_df['SB%'] = proj_df['SB'] / proj_df['PA'].replace(0, np.nan)
        proj_df['CS%'] = proj_df['CS'] / proj_df['PA'].replace(0, np.nan)
        return proj_df

    atc_df = load_projection('ATC')
    tb_df = load_projection('THE_BAT')
    tbx_df = load_projection('THE_BAT_X')
    steamer_df = load_projection('Steamer')
    zips_dc_df = load_projection('ZIPS_DC')
    dc_df = load_projection('DC')
    oopsy_df = load_projection('OOPSY')

    key_df = df.copy()
    key_df['Name_key'] = key_df['Name'].map(normalize_name)

    def series_by_name(source_df, col):
        # Projection files can contain duplicate names; collapse to one value per key for safe mapping.
        series_df = source_df[['Name_key', col]].dropna(subset=['Name_key']).copy()
        # Some columns (e.g., K%, BB%) are stored as strings like "24.7%".
        series_df[col] = (
            series_df[col]
            .astype(str)
            .str.replace('%', '', regex=False)
            .str.replace(',', '', regex=False)
            .str.strip()
        )
        series_df[col] = pd.to_numeric(series_df[col], errors='coerce')
        if col in {'K%', 'BB%'}:
            # Convert percentages like 24.7 to rates like 0.247.
            series_df.loc[series_df[col] > 1, col] = series_df.loc[series_df[col] > 1, col] / 100.0
        deduped = series_df.groupby('Name_key', as_index=True)[col].mean()
        return deduped

    atc_babip = series_by_name(atc_df, 'BABIP')
    tb_babip = series_by_name(tb_df, 'BABIP')
    tbx_babip = series_by_name(tbx_df, 'BABIP')

    tbx_k = series_by_name(tbx_df, 'K%')
    steamer_k = series_by_name(steamer_df, 'K%')
    dc_k = series_by_name(dc_df, 'K%')

    atc_bb = series_by_name(atc_df, 'BB%')
    tbx_bb = series_by_name(tbx_df, 'BB%')

    atc_hr = series_by_name(atc_df, 'HR%')
    tbx_hr = series_by_name(tbx_df, 'HR%')

    atc_1b = series_by_name(atc_df, '1B%')
    tbx_1b = series_by_name(tbx_df, '1B%')

    atc_2b = series_by_name(atc_df, '2B%')
    tbx_2b = series_by_name(tbx_df, '2B%')

    atc_3b = series_by_name(atc_df, '3B%')
    tb_3b = series_by_name(tb_df, '3B%')
    steamer_3b = series_by_name(steamer_df, '3B%')

    tbx_r = series_by_name(tbx_df, 'R%')

    atc_rbi = series_by_name(atc_df, 'RBI%')

    atc_ibb = series_by_name(atc_df, 'IBB%')
    tbx_ibb = series_by_name(tbx_df, 'IBB%')
    zips_dc_ibb = series_by_name(zips_dc_df, 'IBB%')
    dc_ibb = series_by_name(dc_df, 'IBB%')

    atc_hbp = series_by_name(atc_df, 'HBP%')
    tb_hbp = series_by_name(tb_df, 'HBP%')

    tb_sf = series_by_name(tb_df, 'SF%')
    tbx_sf = series_by_name(tbx_df, 'SF%')

    atc_sh = series_by_name(atc_df, 'SH%')
    zips_dc_sh = series_by_name(zips_dc_df, 'SH%')

    atc_sb = series_by_name(atc_df, 'SB%')
    oopsy_sb = series_by_name(oopsy_df, 'SB%')

    atc_cs = series_by_name(atc_df, 'CS%')
    steamer_cs = series_by_name(steamer_df, 'CS%')

    key_df['BABIP'] = key_df['Name_key'].map(atc_babip) * 0.25 + key_df['Name_key'].map(tb_babip) * 0.1 + key_df['Name_key'].map(tbx_babip) * 0.65
    key_df['K%'] = key_df['Name_key'].map(tbx_k) * 0.25 + key_df['Name_key'].map(steamer_k) * 0.15 + key_df['Name_key'].map(dc_k) * 0.6
    key_df['BB%'] = key_df['Name_key'].map(atc_bb) * 0.3 + key_df['Name_key'].map(tbx_bb) * 0.7
    key_df['HR%'] = key_df['Name_key'].map(atc_hr) * 0.1 + key_df['Name_key'].map(tbx_hr) * 0.9
    key_df['1B%'] = key_df['Name_key'].map(atc_1b) * 0.15 + key_df['Name_key'].map(tbx_1b) * 0.85
    key_df['2B%'] = key_df['Name_key'].map(atc_2b) * 0.25 + key_df['Name_key'].map(tbx_2b) * 0.75
    key_df['3B%'] = key_df['Name_key'].map(atc_3b) * 0.6 + key_df['Name_key'].map(tb_3b) * 0.15 + key_df['Name_key'].map(steamer_3b) * 0.25
    key_df['R%'] = key_df['Name_key'].map(tbx_r)
    key_df['RBI%'] = key_df['Name_key'].map(atc_rbi)
    key_df['IBB%'] = key_df['Name_key'].map(atc_ibb) * 0.1 + key_df['Name_key'].map(tbx_ibb) * 0.15 + key_df['Name_key'].map(zips_dc_ibb) * 0.25 + key_df['Name_key'].map(dc_ibb) * 0.5
    key_df['HBP%'] = key_df['Name_key'].map(atc_hbp) * 0.1 + key_df['Name_key'].map(tb_hbp) * 0.9
    key_df['SF%'] = key_df['Name_key'].map(tb_sf) * 0.75 + key_df['Name_key'].map(tbx_sf) * 0.25
    key_df['SH%'] = key_df['Name_key'].map(atc_sh) * 0.9 + key_df['Name_key'].map(zips_dc_sh) * 0.1
    key_df['SB%'] = key_df['Name_key'].map(atc_sb) * 0.75 + key_df['Name_key'].map(oopsy_sb) * 0.25
    key_df['CS%'] = key_df['Name_key'].map(atc_cs) * 0.75 + key_df['Name_key'].map(steamer_cs) * 0.25
    key_df['NSB%'] = key_df['SB%'] - key_df['CS%']

    return key_df.drop(columns=['Name_key'])




base_dir = Path(__file__).resolve().parent
adp_path = '/Users/almond/Desktop/Baseball/Projection_model/yahoo_adp_data.csv'
player_list = pd.read_csv(adp_path, usecols=['Player', 'Team', 'Position']).rename(columns={'Player': 'Name'})

# Remove extra spaces around position values.
player_list['Position'] = player_list['Position'].astype(str).str.strip()
player_list = player_list[~player_list['Position'].isin(['SP', 'RP', 'SP,RP'])].copy()
player_list.loc[player_list['Name'] == 'Shohei Ohtani (Batter)', 'Name'] = 'Shohei Ohtani'
player_list['Name'] = player_list['Name'].map(normalize_name)

hitters_df = create_projections(player_list, year=2026)
missing_rows = hitters_df[hitters_df.isna().any(axis=1)]
if not missing_rows.empty:
    print("Players with missing projected values:")
    for name in missing_rows['Name'].dropna().tolist():
        print(name)
hitters_df.to_csv(base_dir / '2026_Fantasy_Hitters.csv', index=False)

hitter_df = get_ab_pa_from_atc_for_fantasy_names()
print(hitter_df.to_string())

# print (find_player_name('guerrero jr.','vladimir'))
# á
# é
# í
# ó
# ú
