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

# stats = batting_stats(start_season=2023, qual=1)
# a = stats.iloc[:, [2,6,9,10,11,12]]
# print (a.to_string())
# a.to_csv('aSLG/aSLG.csv')

def data(num, bbe, year):
    df = pd.read_csv(bbe)
    new_df = pd.DataFrame()
    names, col = [], []
    start = 0
    end = num
    for i in range(0, 8):
        start += num*i
        end += num*i
        for j in range(start, end):
            if end==num:
                names.append(df.iloc[j, 0])
                col.append(df.iloc[j, 5])
            else:
                col.append(df.iloc[j, 5])
        new_df[f'{i}'] = col
        col = []
        start = 0
        end = num
    new_df.insert(0, 'Name', names)
    print (new_df)
    new_df.to_csv(year)

def hr_data(num, hr, year):
    df = pd.read_csv(hr)
    col = []
    for i in range(0, num):
        hr_pct = df.iloc[i, 1]/df.iloc[i, 2]
        col.append(hr_pct)
    bbe_df = pd.read_csv(year)
    bbe_df['HR%'] = col
    bbe_df.to_csv(year)

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


def spray_angle(x, y):
    angle = math.atan((x - 130) / (213 - y))  # Using an equation I found online to calculate the spray angle
    return math.degrees(angle)

class Statcast:
    def __init__(self, stat):
        self.stat = stat

    def optimal_pull_FB(self):
        stat_df = self.stat[['game_date','stand','bb_type','hit_distance_sc','launch_speed','launch_angle','hc_x','hc_y']]
        bbe = len(stat_df)
        stat_df = stat_df[stat_df.hit_distance_sc >= 200]
        stat_df = stat_df[stat_df.launch_angle >= 22]
        stat_df = stat_df[stat_df.launch_angle <= 42]
        cnt = 0
        for i in range(len(stat_df)):
            stand = stat_df.iat[i, 1]
            hc_x = stat_df.iat[i, 6]
            hc_y = stat_df.iat[i, 7]
            spray = spray_angle(hc_x, hc_y)
            # print (f'{stat_df.iat[i, 0]} {stat_df.iat[i, 3]} {stat_df.iat[i, 4]}')
            if stand == 'L' and spray >= 13:
                cnt += 1
            elif stand == 'R' and spray <= -15:
                cnt += 1
        return cnt, cnt/bbe

    def ninetyFivePctEV(self):
        stat_df = self.stat[['game_date', 'stand', 'bb_type', 'launch_speed', 'launch_angle', 'hc_x', 'hc_y']]
        EV = []
        for i in range(len(stat_df)):
            EV.append(stat_df.iat[i, 3])
        num = int(round(len(EV) * 0.05 + 1, 0))
        EV.sort(reverse=True)
        EV = EV[:len(EV) - (len(EV) - num)]
        NinetyFiveEV = mean(EV)
        return round(NinetyFiveEV, 2)
    
def get_statcast_stats(df, year):
    full_year_data = statcast_batter_exitvelo_barrels(year, 125)
    full_year_data['Name'] = full_year_data['last_name, first_name'].apply(format_name_to_fangraphs)
    full_year_data['Name'] = full_year_data['Name'].apply(normalize_name)

    stats = ['avg_hit_angle','anglesweetspotpercent','ev50','fbld','ev95percent','brl_percent']
    for stat in stats:
        df[stat] = None
    for i, name in enumerate(df['Name']):
        matched = full_year_data[full_year_data['Name'] == name]
        if not matched.empty:
            for stat in stats:
                df.at[i, stat] = matched.iloc[0][stat]
        else:
            print('No match')
    return df

def get_self_made_statcast_stats(df, year):
    df['Optimal_Pulled_Flyball%'] = None
    df['95%_EV'] = None
    for i, name in enumerate(df['Name']):
        key = find_player(name)
        if key != None:
            stats_df = statcast_batter(f'{year}-03-28', f'{year}-10-08', player_id=key)
            stats_df = stats_df.dropna(subset=['bb_type','launch_speed'])
            statcast_stats = Statcast(stats_df)
            OPFB, OPFB_pct = statcast_stats.optimal_pull_FB()
            df.at[i, 'Optimal_Pulled_Flyball%'] = OPFB_pct
            NineFiveEV = statcast_stats.ninetyFivePctEV()
            df.at[i, '95%_EV'] = NineFiveEV
    return df

def get_fangraphs_stats(df, year):
    full_year_data = batting_stats(year, qual=125)

    # O-Swing%, Z-Swing%, Swing%, O-Contact%, Z-Contact%, Contact%, Zone%, F-Strike%, SwStr%, CStr%, CSW%
    stats = ['O-Swing%', 'Z-Swing%', 'Swing%', 'O-Contact%', 'Z-Contact%', 'Contact%', 'Zone%', 'F-Strike%', 'SwStr%', 'CStr%', 'CSW%']
    for stat in stats:
        df[stat] = None
    for i, name in enumerate(df['Name']):
        matched = full_year_data[full_year_data['Name'] == name]
        if not matched.empty:
            for stat in stats:
                df.at[i, stat] = matched.iloc[0][stat]
        else:
            print('No match')
    for stat in stats:
        df[stat] = pd.to_numeric(df[stat], errors='coerce') * 100
    return df


projection_models = ['ATC','DC','OOPSY','Steamer','THE_BAT','THE_BAT_X','ZIPS','ZIPS_DC']
base_dir = Path(__file__).resolve().parent

def projection_file_path(model, year=2025):
    return base_dir / model / f'{year}_{model}_Projections.csv'

def drop_rows_with_missing_pa(df, missing_value=999):
    return df[df['PA'] != missing_value]

def calculate_pa_based_stat_percentages(years=(2023, 2024, 2025), projection_systems=None):
    if projection_systems is None:
        projection_systems = projection_models

    excluded_stats = {'#', 'Name', 'Team', 'G', 'AB', 'PA', 'AVG', 'OBP', 'SLG', 'OPS', 'BABIP', 'K%', 'BB%'}
    excluded_real_stats = {f'real_{stat}' for stat in excluded_stats if stat != '#'}
    excluded_real_stats.add('real_PA')
    excluded_stats.add('HIP')
    excluded_real_stats.add('real_HIP')
    use_hip_denominator_stats = {'1B', '2B', '3B'}

    for year in years:
        for projection_system in projection_systems:
            path = projection_file_path(projection_system, year=year)
            if not path.exists():
                print(f'{projection_system} {year}: missing file, skipping -> {path}')
                continue

            df = pd.read_csv(path)
            if 'PA' not in df.columns:
                print(f'{projection_system} {year}: missing PA column, skipping')
                continue

            # Add HIP / real_HIP before percentage calculations.
            h = pd.to_numeric(df['H'], errors='coerce') if 'H' in df.columns else pd.Series(np.nan, index=df.index)
            hr = pd.to_numeric(df['HR'], errors='coerce') if 'HR' in df.columns else pd.Series(np.nan, index=df.index)
            real_h = pd.to_numeric(df['real_H'], errors='coerce') if 'real_H' in df.columns else pd.Series(np.nan, index=df.index)
            real_hr = pd.to_numeric(df['real_HR'], errors='coerce') if 'real_HR' in df.columns else pd.Series(np.nan, index=df.index)

            df['HIP'] = h - hr
            df['real_HIP'] = real_h - real_hr

            # Reposition HIP right after PA and real_HIP right after real_PA.
            cols = [c for c in df.columns if c not in {'HIP', 'real_HIP'}]
            if 'PA' in cols:
                pa_idx = cols.index('PA')
                cols.insert(pa_idx + 1, 'HIP')
            else:
                cols.append('HIP')

            if 'real_PA' in cols:
                real_pa_idx = cols.index('real_PA')
                cols.insert(real_pa_idx + 1, 'real_HIP')
            else:
                cols.append('real_HIP')

            df = df[cols]

            pa = pd.to_numeric(df['PA'], errors='coerce').replace(0, np.nan)
            real_pa = None
            if 'real_PA' in df.columns:
                real_pa = pd.to_numeric(df['real_PA'], errors='coerce').replace(0, np.nan)
            hip = pd.to_numeric(df['HIP'], errors='coerce').replace(0, np.nan) if 'HIP' in df.columns else None
            real_hip = pd.to_numeric(df['real_HIP'], errors='coerce').replace(0, np.nan) if 'real_HIP' in df.columns else None

            for col in df.columns:
                if col.startswith('Unnamed'):
                    continue
                if col in excluded_stats:
                    continue
                if col.startswith('real_'):
                    if col in excluded_real_stats:
                        continue
                    base_stat = col.removeprefix('real_')
                    if base_stat in use_hip_denominator_stats and real_hip is not None:
                        denom = real_hip
                    else:
                        denom = real_pa if real_pa is not None else pa
                else:
                    if col in use_hip_denominator_stats and hip is not None:
                        denom = hip
                    else:
                        denom = pa

                df[col] = pd.to_numeric(df[col], errors='coerce') / denom

            df.to_csv(path, index=False)
            print(f'Updated PA-based percentages: {path}')

# for model in projection_models:
#     path = f'./Hitters/{model}/2025_{model}_Projections.csv'
#     path_df = pd.read_csv(path)

#     # Get rid of accents in names and get real life stats
#     path_df['Name'] = path_df['Name'].apply(normalize_name)
#     path_df.to_csv(path, index=False)

#     path_df = calculate_stats(path_df)
#     path_df.to_csv(path, index=False)
#     new_df = path_df.copy()
#     get_stats = path_df.columns.to_list()[4:]
#     get_stats = [col for col in get_stats if col != 'NSB']
#     year = 2025
#     data_df = batting_stats(year, qual=100)
#     different_names = []
#     cnt = 0
#     for stat in get_stats:
#         stat_list = []
#         for name in path_df['Name']:
#             try:
#                 idx = data_df.index[data_df['Name'] == name].tolist()[0]
#                 stat_list.append(data_df.loc[idx][stat])
#             except:
#                 if cnt < 1:
#                     different_names.append(name)
#                 stat_list.append(999)
#         cnt += 1
#         df = pd.DataFrame(stat_list, columns=[f'real_{stat}'])
#         new_df = pd.concat([new_df, df], axis=1)
#     new_df = new_df[new_df['real_PA'] >= 200]
#     new_df['real_K%'] = pd.to_numeric(new_df['real_K%'], errors='coerce') * 100
#     new_df['real_BB%'] = pd.to_numeric(new_df['real_BB%'], errors='coerce') * 100
#     new_df.to_csv(path, header=True, index=False)

#     # Scale the stats to real_PA
#     new_df = scale_stats(new_df)
#     new_df.to_csv(path, index=False)

# for model in projection_models:
#     print(model)
#     path = projection_file_path(model, year=2025)
#     path_df = pd.read_csv(path)
#     path_df = drop_rows_with_missing_pa(path_df, missing_value=999)
#     path_df.to_csv(path)

calculate_pa_based_stat_percentages(years=(2023, 2024, 2025), projection_systems=projection_models)

# name = 'Will Smith'
# key = find_player(name)
# stats_df = statcast_batter('2022-03-28', '2022-10-08', player_id=622110)
# stats_df = stats_df.dropna(subset=['bb_type','launch_speed'])
# statcast_stats = Statcast(stats_df)
# OPFB, OPFB_pct = statcast_stats.optimal_pull_FB()
# print(OPFB, OPFB_pct)
# nineFiveEV = statcast_stats.ninetyFivePctEV()
# print(nineFiveEV)

# path_df = get_statcast_stats(path_df, year)
# path_df = get_self_made_statcast_stats(path_df, year)
# path_df = get_fangraphs_stats(path_df, year)
# print(path_df)
# path_df.to_csv(path, index=False)


# print (find_player_name('guerrero jr.','vladimir'))
# á
# é
# í
# ó
# ú
