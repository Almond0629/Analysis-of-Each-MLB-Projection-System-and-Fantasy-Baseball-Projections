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

def to_numeric_series(series):
    if isinstance(series, pd.DataFrame):
        # Handle duplicate column names by using the first matching column.
        series = series.iloc[:, 0]
    cleaned = (
        series.astype(str)
        .str.replace('%', '', regex=False)
        .str.replace(',', '', regex=False)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors='coerce')

def build_real_pitching_lookup(year):
    real_df = pitching_stats(year, qual=0).copy()
    real_df['Name_norm'] = real_df['Name'].apply(normalize_name)
    return real_df

def series_by_name(real_df, col):
    if col not in real_df.columns:
        return pd.Series(dtype='float64')
    name_series = real_df['Name_norm']
    if isinstance(name_series, pd.DataFrame):
        name_series = name_series.iloc[:, 0]

    value_series = real_df[col]
    if isinstance(value_series, pd.DataFrame):
        value_series = value_series.iloc[:, 0]

    temp = pd.DataFrame({'Name_norm': name_series, col: value_series}).dropna(subset=['Name_norm']).copy()
    temp[col] = to_numeric_series(temp[col])
    # Convert percentage stats to same format used in projection files (0-100 scale).
    if col in {'K%', 'BB%'}:
        temp.loc[temp[col] <= 1, col] = temp.loc[temp[col] <= 1, col] * 100.0
    return temp.groupby('Name_norm', as_index=True)[col].mean()

def add_real_stats_columns(df, real_df, projected_stats):
    stat_fallbacks = {
        'TBF': ['BF'],
        'K/9': ['K/9', 'K/BB'],  # keep K/9 first if available
        'BB/9': ['BB/9']
    }

    for stat in projected_stats:
        candidates = [stat] + stat_fallbacks.get(stat, [])
        real_series = pd.Series(dtype='float64')
        for candidate in candidates:
            real_series = series_by_name(real_df, candidate)
            if not real_series.empty:
                break
        df[f'real_{stat}'] = df['Name_norm'].map(real_series)
    return df

def scale_stats_to_real_pa(df, projected_stats):
    # Use PA when available; otherwise fallback to TBF for pitcher files.
    if 'PA' in df.columns and 'real_PA' in df.columns:
        denom = to_numeric_series(df['PA'])
        numer = to_numeric_series(df['real_PA'])
    elif 'TBF' in df.columns and 'real_TBF' in df.columns:
        denom = to_numeric_series(df['TBF'])
        numer = to_numeric_series(df['real_TBF'])
        # Expose real_PA as requested when pitcher files have TBF instead.
        if 'real_PA' not in df.columns:
            df['real_PA'] = numer
    else:
        return df

    ratio = numer / denom.replace(0, np.nan)

    non_scaling_stats = {'ERA', 'WHIP', 'K/9', 'BB/9', 'K%', 'BB%', 'PA', 'TBF'}
    for stat in projected_stats:
        if stat in non_scaling_stats or stat not in df.columns:
            continue
        df[stat] = to_numeric_series(df[stat]) * ratio
    return df

def drop_players_not_found(df):
    """Delete players that were not matched to real-stat rows."""
    if 'real_PA' in df.columns:
        found_mask = to_numeric_series(df['real_PA']).notna()
    elif 'real_TBF' in df.columns:
        found_mask = to_numeric_series(df['real_TBF']).notna()
    else:
        return df

    missing = df.loc[~found_mask, 'Name'].dropna().tolist()
    if missing:
        print(f"Removing {len(missing)} players not found in real stats:")
        for name in missing:
            print(f"  {name}")

    return df.loc[found_mask].copy()

def drop_players_below_real_ip(df, min_real_ip=15):
    if 'real_IP' not in df.columns:
        return df

    real_ip = to_numeric_series(df['real_IP'])
    keep_mask = real_ip >= min_real_ip
    removed = df.loc[~keep_mask, 'Name'].dropna().tolist()
    if removed:
        print(f"Removing {len(removed)} players with real_IP < {min_real_ip}:")
        for name in removed:
            print(f"  {name}")
    return df.loc[keep_mask].copy()

def ensure_k_bb_percent_columns(df):
    if 'K%' not in df.columns and {'SO', 'TBF'}.issubset(df.columns):
        so = pd.to_numeric(df['SO'], errors='coerce')
        tbf = pd.to_numeric(df['TBF'], errors='coerce').replace(0, np.nan)
        df['K%'] = (so / tbf) * 100.0

    if 'BB%' not in df.columns and {'BB', 'TBF'}.issubset(df.columns):
        bb = pd.to_numeric(df['BB'], errors='coerce')
        tbf = pd.to_numeric(df['TBF'], errors='coerce').replace(0, np.nan)
        df['BB%'] = (bb / tbf) * 100.0

    if 'real_K%' not in df.columns and {'real_SO', 'real_TBF'}.issubset(df.columns):
        so = pd.to_numeric(df['real_SO'], errors='coerce')
        tbf = pd.to_numeric(df['real_TBF'], errors='coerce').replace(0, np.nan)
        df['real_K%'] = (so / tbf) * 100.0

    if 'real_BB%' not in df.columns and {'real_BB', 'real_TBF'}.issubset(df.columns):
        bb = pd.to_numeric(df['real_BB'], errors='coerce')
        tbf = pd.to_numeric(df['real_TBF'], errors='coerce').replace(0, np.nan)
        df['real_BB%'] = (bb / tbf) * 100.0

    return df

def convert_stats_to_percentages(df, projected_stats):
    by_g_stats = {'W', 'L', 'QS', 'SV', 'HLD', 'BS'}
    non_scaling_stats = {'SO', 'BB', 'ERA', 'WHIP', 'K/9', 'BB/9', 'K%', 'BB%', 'IP', 'TBF', 'G', 'GS'}

    g = to_numeric_series(df['G']) if 'G' in df.columns else pd.Series(np.nan, index=df.index)
    real_g = to_numeric_series(df['real_G']) if 'real_G' in df.columns else pd.Series(np.nan, index=df.index)
    tbf = to_numeric_series(df['TBF']) if 'TBF' in df.columns else pd.Series(np.nan, index=df.index)
    real_tbf = to_numeric_series(df['real_TBF']) if 'real_TBF' in df.columns else pd.Series(np.nan, index=df.index)

    for stat in projected_stats:
        real_stat = f'real_{stat}'
        if stat not in df.columns or real_stat not in df.columns:
            continue
        if stat in non_scaling_stats:
            continue

        if stat in by_g_stats:
            df[stat] = to_numeric_series(df[stat]) / g.replace(0, np.nan)
            df[stat] *= 100
            df[real_stat] = to_numeric_series(df[real_stat]) / real_g.replace(0, np.nan)
            df[real_stat] *= 100
        else:
            df[stat] = to_numeric_series(df[stat]) / tbf.replace(0, np.nan)
            df[stat] *= 100
            df[real_stat] = to_numeric_series(df[real_stat]) / real_tbf.replace(0, np.nan)
            df[real_stat] *= 100

    return df



projection_models = ['ATC','DC','OOPSY','Steamer','THE_BAT','THE_BAT_X','ZIPS','ZIPS_DC']
base_dir = Path(__file__).resolve().parent
year = 2025
real_pitching_df = build_real_pitching_lookup(year)

for model in projection_models:
    path = base_dir / model / f'{year}_{model}_Projections.csv'
    if not path.exists():
        print(f"{model}: file not found, skipping -> {path}")
        continue

    print(model)
    df = pd.read_csv(path)
    df['Name'] = df['Name'].apply(normalize_name)
    df['Name_norm'] = df['Name']

    projected_stats = [
        c for c in df.columns
        if c not in {'#', 'Name', 'Team', 'Name_norm'} and not c.startswith('real_')
    ]
    df = ensure_k_bb_percent_columns(df)
    df = add_real_stats_columns(df, real_pitching_df, projected_stats)
    df = convert_stats_to_percentages(df, projected_stats)
    df = drop_players_not_found(df)
    df = drop_players_below_real_ip(df, min_real_ip=15)

    # Keep clean output.
    df = df.drop(columns=['Name_norm'])
    df.to_csv(path, index=False)

# print (find_player_name('guerrero jr.','vladimir'))
# á
# é
# í
# ó
# ú
