"""
NBA API - gets player data from the official NBA stats website
"""

import requests
import time

class NBAStatsAPI:
    
    def __init__(self):
        # NBA API base URL
        self.base_url = "https://stats.nba.com/stats"
        
        # these headers make the API think we're a real browser
        # without them, the requests get blocked
        self.headers = {
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://www.nba.com/'
        }
    
    def search_players(self, player_name):
        """search for NBA players by name"""
        
        # build the API request
        url = f"{self.base_url}/commonallplayers"
        params = {
            'LeagueID': '00',  # NBA league
            'Season': '2024-25',
            'IsOnlyCurrentSeason': '1'
        }
        
        try:
            # make the request
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            data = response.json()
            
            # the API returns data in a weird format, need to parse it
            headers = data['resultSets'][0]['headers']
            rows = data['resultSets'][0]['rowSet']
            
            # filter to find players matching the search
            results = []
            for row in rows:
                player = dict(zip(headers, row))
                # check if search term is in player name
                if player_name.lower() in player['DISPLAY_FIRST_LAST'].lower():
                    results.append({
                        'id': player['PERSON_ID'],
                        'name': player['DISPLAY_FIRST_LAST'],
                        'is_active': player['ROSTERSTATUS'] == 1
                    })
            
            time.sleep(0.6)  # wait a bit so we don't spam the API
            return results
            
        except:
            print("couldn't fetch players")
            return []
    
    def get_player_info(self, player_id):
        """get a player's basic info like height, team, etc"""
        
        url = f"{self.base_url}/commonplayerinfo"
        params = {'PlayerID': player_id}
        
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            data = response.json()
            
            # parse the response
            headers = data['resultSets'][0]['headers']
            row = data['resultSets'][0]['rowSet'][0]
            info = dict(zip(headers, row))
            
            # return only the data we need
            return {
                'id': info['PERSON_ID'],
                'name': f"{info['FIRST_NAME']} {info['LAST_NAME']}",
                'team': info['TEAM_NAME'],
                'team_abbreviation': info['TEAM_ABBREVIATION'],
                'jersey': info['JERSEY'],
                'position': info['POSITION'],
                'height': info['HEIGHT'],
                'weight': info['WEIGHT'],
                'birthdate': info['BIRTHDATE'],
                'school': info['SCHOOL'],
                'country': info['COUNTRY'],
                'draft_year': info['DRAFT_YEAR'],
                'draft_round': info['DRAFT_ROUND'],
                'draft_number': info['DRAFT_NUMBER']
            }
            
        except:
            print(f"couldn't get info for player {player_id}")
            return None
    
    def get_player_stats(self, player_id):
        """get a player's season stats - points, rebounds, assists, etc"""
        
        url = f"{self.base_url}/playercareerstats"
        params = {
            'PlayerID': player_id,
            'PerMode': 'PerGame'  # averages per game
        }
        
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            data = response.json()
            
            headers = data['resultSets'][0]['headers']
            rows = data['resultSets'][0]['rowSet']
            
            if not rows:
                return None
            
            # get most recent season (first row)
            stats = dict(zip(headers, rows[0]))
            
            # organize the stats we care about
            return {
                'season': stats['SEASON_ID'],
                'team': stats['TEAM_ABBREVIATION'],
                'games_played': stats['GP'],
                'minutes': round(stats['MIN'], 1),
                'points': round(stats['PTS'], 1),
                'rebounds': round(stats['REB'], 1),
                'assists': round(stats['AST'], 1),
                'steals': round(stats['STL'], 1),
                'blocks': round(stats['BLK'], 1),
                'fg_pct': round(stats['FG_PCT'] * 100, 1) if stats['FG_PCT'] else 0,
                'fg3_pct': round(stats['FG3_PCT'] * 100, 1) if stats['FG3_PCT'] else 0,
                'ft_pct': round(stats['FT_PCT'] * 100, 1) if stats['FT_PCT'] else 0,
            }
            
        except:
            print(f"couldn't get stats for player {player_id}")
            return None
    
    def get_player_complete_data(self, player_id):
        """get everything about a player - info and stats together"""
        
        # get the info first
        player_info = self.get_player_info(player_id)
        if not player_info:
            return None
        
        # then get the stats
        player_stats = self.get_player_stats(player_id)
        
        # combine them
        return {
            'info': player_info,
            'stats': player_stats
        }