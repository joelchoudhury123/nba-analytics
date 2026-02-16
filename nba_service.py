"""
NBA API - using nba_api library (easier than direct requests)
"""

from nba_api.stats.static import players
from nba_api.stats.endpoints import commonplayerinfo, playercareerstats
import time

class NBAStatsAPI:
    
    def __init__(self):
        # the nba_api library handles headers and rate limiting for us
        pass
    
    def search_players(self, player_name):
        """search for NBA players by name"""
        try:
            # get all players
            all_players = players.get_players()
            
            # filter by search term
            results = []
            search_lower = player_name.lower()
            
            for player in all_players:
                if search_lower in player['full_name'].lower():
                    results.append({
                        'id': str(player['id']),
                        'name': player['full_name'],
                        'is_active': player['is_active']
                    })
            
            return results[:10]  # limit to 10 results
            
        except Exception as e:
            print(f"Error searching players: {e}")
            return []
    
    def get_player_info(self, player_id):
        """get player info"""
        try:
            # call the API
            player_info = commonplayerinfo.CommonPlayerInfo(player_id=player_id)
            data = player_info.get_normalized_dict()
            info = data['CommonPlayerInfo'][0]
            
            time.sleep(0.6)  # wait to avoid rate limit
            
            return {
                'id': str(info['PERSON_ID']),
                'name': info['DISPLAY_FIRST_LAST'],
                'team': info['TEAM_NAME'] or 'Free Agent',
                'team_abbreviation': info['TEAM_ABBREVIATION'] or 'FA',
                'jersey': info['JERSEY'] or 'N/A',
                'position': info['POSITION'] or 'N/A',
                'height': info['HEIGHT'] or 'N/A',
                'weight': info['WEIGHT'] or 'N/A',
                'birthdate': info['BIRTHDATE'] or 'N/A',
                'school': info['SCHOOL'] or 'N/A',
                'country': info['COUNTRY'] or 'USA',
                'draft_year': info['DRAFT_YEAR'] or 'Undrafted',
                'draft_round': info['DRAFT_ROUND'] or 'N/A',
                'draft_number': info['DRAFT_NUMBER'] or 'N/A'
            }
            
        except Exception as e:
            print(f"Error getting player info: {e}")
            return None
    
    def get_player_stats(self, player_id):
        """get player stats"""
        try:
            # get career stats
            career = playercareerstats.PlayerCareerStats(player_id=player_id)
            data = career.get_normalized_dict()
            
            time.sleep(0.6)  # wait to avoid rate limit
            
            # get most recent season
            if not data['SeasonTotalsRegularSeason']:
                return None
            
            stats = data['SeasonTotalsRegularSeason'][0]
            
            # calculate per game averages
            games = stats['GP'] if stats['GP'] > 0 else 1
            
            return {
                'season': stats['SEASON_ID'],
                'team': stats['TEAM_ABBREVIATION'],
                'games_played': stats['GP'],
                'minutes': round(stats['MIN'] / games, 1),
                'points': round(stats['PTS'] / games, 1),
                'rebounds': round(stats['REB'] / games, 1),
                'assists': round(stats['AST'] / games, 1),
                'steals': round(stats['STL'] / games, 1),
                'blocks': round(stats['BLK'] / games, 1),
                'fg_pct': round(stats['FG_PCT'] * 100, 1) if stats['FG_PCT'] else 0,
                'fg3_pct': round(stats['FG3_PCT'] * 100, 1) if stats['FG3_PCT'] else 0,
                'ft_pct': round(stats['FT_PCT'] * 100, 1) if stats['FT_PCT'] else 0,
            }
            
        except Exception as e:
            print(f"Error getting player stats: {e}")
            return None
    
    def get_player_complete_data(self, player_id):
        """get all player data"""
        player_info = self.get_player_info(player_id)
        if not player_info:
            return None
        
        player_stats = self.get_player_stats(player_id)
        
        return {
            'info': player_info,
            'stats': player_stats
        }