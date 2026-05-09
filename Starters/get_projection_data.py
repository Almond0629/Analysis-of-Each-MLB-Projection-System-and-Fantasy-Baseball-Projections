from pybaseball import *
import pandas as pd
import math
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


def get_g_ip_tbf_from_atc_for_fantasy_names(
    relievers_xlsx_path='/Users/almond/Desktop/Baseball/Projection_model/Relievers/Fantasy/2026/2026_Fantasy_Hitters.xlsx',
    atc_csv_path='/Users/almond/Desktop/Baseball/Projection_model/Relievers/ATC/2026_ATC_Projections.csv'
):
    rel_df = pd.read_excel(relievers_xlsx_path, usecols=['Name']).copy()
    atc_df = pd.read_csv(atc_csv_path, usecols=['Name', 'G', 'IP', 'TBF']).copy()

    rel_df['Name_key'] = rel_df['Name'].map(normalize_name)
    atc_df['Name_key'] = atc_df['Name'].map(normalize_name)
    atc_df['G'] = pd.to_numeric(atc_df['G'], errors='coerce')
    atc_df['IP'] = pd.to_numeric(atc_df['IP'], errors='coerce')
    atc_df['TBF'] = pd.to_numeric(atc_df['TBF'], errors='coerce')

    # Keep one AB/PA pair per normalized name to avoid duplicate-index mapping errors.
    atc_lookup = atc_df.groupby('Name_key', as_index=True)[['G', 'IP', 'TBF']].mean()
    rel_df['G'] = rel_df['Name_key'].map(atc_lookup['G'])
    rel_df['IP'] = rel_df['Name_key'].map(atc_lookup['IP'])
    rel_df['TBF'] = rel_df['Name_key'].map(atc_lookup['TBF'])

    return rel_df.drop(columns=['Name','Name_key'])


def create_projections(df, year=2026):
    base_dir = Path(__file__).resolve().parent

    def load_projection(proj):
        proj_path = base_dir / proj / f'{year}_{proj}_Projections.csv'
        proj_df = pd.read_csv(proj_path)
        proj_df['Name_key'] = proj_df['Name'].map(normalize_name)
        proj_df['W%'] = proj_df['W'] / proj_df['G'].replace(0, np.nan)
        proj_df['L%'] = proj_df['L'] / proj_df['G'].replace(0, np.nan)
        proj_df['QS%'] = proj_df['QS'] / proj_df['G'].replace(0, np.nan)
        proj_df['SV%'] = proj_df['SV'] / proj_df['G'].replace(0, np.nan)
        proj_df['HLD%'] = proj_df['HLD'] / proj_df['G'].replace(0, np.nan)
        proj_df['BS%'] = proj_df['BS'] / proj_df['G'].replace(0, np.nan)
        proj_df['H%'] = proj_df['H'] / proj_df['TBF'].replace(0, np.nan)
        proj_df['R%'] = proj_df['R'] / proj_df['TBF'].replace(0, np.nan)
        proj_df['ER%'] = proj_df['ER'] / proj_df['TBF'].replace(0, np.nan)
        proj_df['HR%'] = proj_df['HR'] / proj_df['TBF'].replace(0, np.nan)
        proj_df['IBB%'] = proj_df['IBB'] / proj_df['TBF'].replace(0, np.nan)
        proj_df['HBP%'] = proj_df['HBP'] / proj_df['TBF'].replace(0, np.nan)
        proj_df['K%'] = proj_df['SO'] / proj_df['TBF'].replace(0, np.nan)
        proj_df['BB%'] = proj_df['BB'] / proj_df['TBF'].replace(0, np.nan)
        return proj_df

    atc_df = load_projection('ATC')
    tb_df = load_projection('THE_BAT')
    tbx_df = load_projection('THE_BAT_X')
    steamer_df = load_projection('Steamer')
    zips_df = load_projection('ZIPS')
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

    atc_w = series_by_name(steamer_df, 'W%')
    tb_w = series_by_name(tb_df, 'W%')
    zips_w = series_by_name(zips_df, 'W%')

    atc_l = series_by_name(atc_df, 'L%')
    tb_l = series_by_name(tb_df, 'L%')
    steamer_l = series_by_name(steamer_df, 'L%')

    atc_qs = series_by_name(atc_df, 'QS%')
    tb_qs = series_by_name(tb_df, 'QS%')
    tbx_qs = series_by_name(tbx_df, 'QS%')
    steamer_qs = series_by_name(steamer_df, 'QS%')
    dc_qs = series_by_name(dc_df, 'QS%')
    oopsy_qs = series_by_name(oopsy_df, 'QS%')

    tb_h = series_by_name(tb_df, 'H%')
    steamer_h = series_by_name(steamer_df, 'H%')
    dc_h = series_by_name(dc_df, 'H%')

    steamer_r = series_by_name(steamer_df, 'R%')
    dc_r = series_by_name(dc_df, 'R%')
    oopsy_r = series_by_name(oopsy_df, 'R%')

    steamer_er = series_by_name(steamer_df, 'ER%')
    zips_dc_er = series_by_name(zips_dc_df, 'ER%')
    dc_er = series_by_name(zips_df, 'ER%')

    atc_hr = series_by_name(atc_df, 'HR%')
    tb_hr = series_by_name(tb_df, 'HR%')
    dc_hr = series_by_name(dc_df, 'HR%')

    atc_ibb = series_by_name(atc_df, 'IBB%')
    steamer_ibb = series_by_name(steamer_df, 'IBB%')

    atc_hbp = series_by_name(atc_df, 'HBP%')
    tb_hbp = series_by_name(tb_df, 'HBP%')
    steamer_hbp = series_by_name(steamer_df, 'HBP%')

    tb_k = series_by_name(tb_df, 'K%')
    steamer_k = series_by_name(steamer_df, 'K%')
    zips_dc_k = series_by_name(zips_dc_df, 'K%')

    atc_bb = series_by_name(atc_df, 'BB%')
    tb_bb = series_by_name(tb_df, 'BB%')
    steamer_bb = series_by_name(steamer_df, 'BB%')

    key_df['W%'] = key_df['Name_key'].map(atc_w) * 0.333 + key_df['Name_key'].map(tb_w) * 0.333 + key_df['Name_key'].map(zips_w) * 0.333
    key_df['L%'] = key_df['Name_key'].map(atc_l) * 0.333 + key_df['Name_key'].map(tb_l) * 0.333 + key_df['Name_key'].map(steamer_l) * 0.333
    key_df['QS%'] = (key_df['Name_key'].map(atc_qs) + key_df['Name_key'].map(tb_qs) + key_df['Name_key'].map(tbx_qs) + key_df['Name_key'].map(steamer_qs) + key_df['Name_key'].map(dc_qs) + key_df['Name_key'].map(oopsy_qs)) / 6
    key_df['H%'] = key_df['Name_key'].map(tb_h) * 0.333 + key_df['Name_key'].map(steamer_h) * 0.333 + key_df['Name_key'].map(dc_h) * 0.333
    key_df['R%'] = key_df['Name_key'].map(steamer_r) * 0.333+ key_df['Name_key'].map(dc_r) * 0.333 + key_df['Name_key'].map(oopsy_r) * 0.333
    key_df['ER%'] = key_df['Name_key'].map(steamer_er) * 0.333 + key_df['Name_key'].map(zips_dc_er) * 0.333 + key_df['Name_key'].map(dc_er) * 0.333
    key_df['HR%'] = key_df['Name_key'].map(atc_hr) * 0.333 + key_df['Name_key'].map(tb_hr) * 0.333 + key_df['Name_key'].map(dc_hr) * 0.333
    key_df['IBB%'] = key_df['Name_key'].map(atc_ibb) * 0.5 + key_df['Name_key'].map(steamer_ibb) * 0.5
    key_df['HBP%'] = key_df['Name_key'].map(atc_hbp) * 0.333 + key_df['Name_key'].map(tb_hbp) * 0.333 + key_df['Name_key'].map(steamer_hbp) * 0.333
    key_df['K%'] = key_df['Name_key'].map(tb_k) * 0.3 + key_df['Name_key'].map(steamer_k) * 0.2 + key_df['Name_key'].map(zips_dc_k) * 0.5
    key_df['BB%'] = key_df['Name_key'].map(atc_bb) * 0.3 + key_df['Name_key'].map(tb_bb) * 0.5 + key_df['Name_key'].map(steamer_bb) * 0.2

    return key_df.drop(columns=['Name_key'])




# base_dir = Path(__file__).resolve().parent
# adp_path = f'./yahoo_adp_data.csv'
# player_list = pd.read_csv(adp_path, usecols=['Player', 'Team', 'Position']).rename(columns={'Player': 'Name'})

# # Remove extra spaces around position values.
# player_list['Position'] = player_list['Position'].astype(str).str.strip()
# player_list = player_list[player_list['Position'].isin(['SP','SP,RP'])].copy()
# player_list.loc[player_list['Name'] == 'Shohei Ohtani (Pitcher)', 'Name'] = 'Shohei Ohtani'
# player_list['Name'] = player_list['Name'].map(normalize_name)

# rel_df = create_projections(player_list, year=2026)
# missing_rows = rel_df[rel_df.isna().any(axis=1)]
# if not missing_rows.empty:
#     print("Players with missing projected values:")
#     for name in missing_rows['Name'].dropna().tolist():
#         print(name)
# rel_df.to_csv(f'./Starters/Fantasy/2026/2026_Fantasy_Starters.csv', index=False)

rel_df = get_g_ip_tbf_from_atc_for_fantasy_names(relievers_xlsx_path='/Users/almond/Desktop/Baseball/Projection_model/Starters/Fantasy/2026/2026_Fantasy_Starters.xlsx',
    atc_csv_path='/Users/almond/Desktop/Baseball/Projection_model/Starters/ATC/2026_ATC_Projections.csv')
print(rel_df.to_string())

# print (find_player_name('guerrero jr.','vladimir'))
# á
# é
# í
# ó
# ú
