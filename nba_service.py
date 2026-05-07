"""
handles all the nba api calls and stat calculations
using the nba_api library because it wraps the official stats.nba.com endpoints
and handles headers/rate limiting for us
"""

from nba_api.stats.static import players
from nba_api.stats.endpoints import commonplayerinfo, playercareerstats, playergamelog
import time

from nba_api.stats.library.http import NBAStatsHTTP


NBAStatsHTTP.headers = {
   'Host': 'stats.nba.com',
   'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
   'Accept': 'application/json, text/plain, */*',
   'Accept-Language': 'en-US,en;q=0.9',
   'Origin': 'https://www.nba.com',
   'Referer': 'https://www.nba.com/',
   'Connection': 'keep-alive',
}

class NBAStatsAPI:
 
    def __init__(self):
        pass
 
    def search_players(self, player_name):
        # get_players() returns every player in nba history as a list of dicts
        try:
            all_players = players.get_players()
            results = []
            search_lower = player_name.lower()
            for player in all_players:
                if search_lower in player['full_name'].lower():
                    status = 'Active' if player['is_active'] else 'Retired'
                    results.append({
                        'id': str(player['id']),
                        'name': player['full_name'],
                        'is_active': player['is_active'],
                        'status': status
                    })
            return results[:10]
        except Exception as e:
            print(f"Error searching players: {e}")
            return []
 
    def get_player_info(self, player_id):
        # commonplayerinfo gives us bio stuff - team, position, height, draft info etc
        try:
            player_info = commonplayerinfo.CommonPlayerInfo(player_id=player_id)
            data = player_info.get_normalized_dict()
            info = data['CommonPlayerInfo'][0]
            time.sleep(0.6)
            return {
                'id': str(info['PERSON_ID']),
                'name': info['DISPLAY_FIRST_LAST'],
                'team': info['TEAM_NAME'] or 'Free Agent',
                'team_abbreviation': info['TEAM_ABBREVIATION'] or 'FA',
                'jersey': info['JERSEY'] or 'N/A',
                'position': info['POSITION'] or 'N/A',
                'height': info['HEIGHT'] or 'N/A',
                'weight': info['WEIGHT'] or 'N/A',
                'birthdate': self._format_date(info['BIRTHDATE']) if info['BIRTHDATE'] else 'N/A',
                'school': info['SCHOOL'] or 'N/A',
                'country': info['COUNTRY'] or 'USA',
                'draft_year': info['DRAFT_YEAR'] or 'Undrafted',
                'draft_round': info['DRAFT_ROUND'] or 'N/A',
                'draft_number': info['DRAFT_NUMBER'] or 'N/A'
            }
        except Exception as e:
            print(f"Error getting player info: {e}")
            return None
 
    def _calculate_advanced_stats(self, season_row):
        """
        calculates advanced stats from the raw season totals
        no extra api calls needed - everything comes from the career stats endpoint
        """
        gp   = season_row.get('GP', 0) or 0
        min_ = season_row.get('MIN', 0) or 0
        pts  = season_row.get('PTS', 0) or 0
        fgm  = season_row.get('FGM', 0) or 0
        fga  = season_row.get('FGA', 0) or 0
        fg3m = season_row.get('FG3M', 0) or 0
        fg3a = season_row.get('FG3A', 0) or 0
        ftm  = season_row.get('FTM', 0) or 0
        fta  = season_row.get('FTA', 0) or 0
        reb  = season_row.get('REB', 0) or 0
        ast  = season_row.get('AST', 0) or 0
        stl  = season_row.get('STL', 0) or 0
        blk  = season_row.get('BLK', 0) or 0
        tov  = season_row.get('TOV', 0) or 0
 
        ts_denominator = 2 * (fga + 0.44 * fta)
        ts_pct = round((pts / ts_denominator) * 100, 1) if ts_denominator > 0 else 0.0
        efg_pct = round(((fgm + 0.5 * fg3m) / fga) * 100, 1) if fga > 0 else 0.0
        ftr = round((fta / fga), 3) if fga > 0 else 0.0
        three_par = round((fg3a / fga) * 100, 1) if fga > 0 else 0.0
        per36_pts = round((pts  / min_) * 36, 1) if min_ > 0 else 0.0
        per36_reb = round((reb  / min_) * 36, 1) if min_ > 0 else 0.0
        per36_ast = round((ast  / min_) * 36, 1) if min_ > 0 else 0.0
        per36_stl = round((stl  / min_) * 36, 1) if min_ > 0 else 0.0
        per36_blk = round((blk  / min_) * 36, 1) if min_ > 0 else 0.0
        per36_tov = round((tov  / min_) * 36, 1) if min_ > 0 else 0.0
        ast_tov = round(ast / tov, 2) if tov > 0 else float(ast)
        stock = round((stl + blk) / gp, 1) if gp > 0 else 0.0
 
        return {
            'ts_pct': ts_pct, 'efg_pct': efg_pct, 'ftr': ftr, 'three_par': three_par,
            'per36_pts': per36_pts, 'per36_reb': per36_reb, 'per36_ast': per36_ast,
            'per36_stl': per36_stl, 'per36_blk': per36_blk, 'per36_tov': per36_tov,
            'ast_tov': ast_tov, 'stock': stock,
        }
 
    def _build_season_dict(self, stats):
        # takes a raw season row and builds the dict we send to the frontend
        games = stats['GP'] if stats['GP'] > 0 else 1
        basic = {
            'season':       stats['SEASON_ID'],
            'team':         stats['TEAM_ABBREVIATION'],
            'games_played': stats['GP'],
            'minutes':      round(stats['MIN']  / games, 1),
            'points':       round(stats['PTS']  / games, 1),
            'fgm':          round(stats['FGM']  / games, 1),
            'fga':          round(stats['FGA']  / games, 1),
            'fg_pct':       round(stats['FG_PCT']  * 100, 1) if stats['FG_PCT']  else 0,
            'fg3m':         round(stats['FG3M'] / games, 1),
            'fg3a':         round(stats['FG3A'] / games, 1),
            'fg3_pct':      round(stats['FG3_PCT'] * 100, 1) if stats['FG3_PCT'] else 0,
            'ftm':          round(stats['FTM']  / games, 1),
            'fta':          round(stats['FTA']  / games, 1),
            'ft_pct':       round(stats['FT_PCT']  * 100, 1) if stats['FT_PCT']  else 0,
            'rebounds':     round(stats['REB']  / games, 1),
            'oreb':         round(stats['OREB'] / games, 1),
            'dreb':         round(stats['DREB'] / games, 1),
            'assists':      round(stats['AST']  / games, 1),
            'steals':       round(stats['STL']  / games, 1),
            'blocks':       round(stats['BLK']  / games, 1),
            'turnovers':    round(stats['TOV']  / games, 1) if stats.get('TOV') else 0.0,
            'fouls':        round(stats['PF']   / games, 1) if stats.get('PF')  else 0.0,
        }
        advanced = self._calculate_advanced_stats(stats)
        return {**basic, 'advanced': advanced}
 
    def get_player_stats(self, player_id):
        # just the most recent regular season for the initial page load
        try:
            career = playercareerstats.PlayerCareerStats(player_id=player_id)
            data = career.get_normalized_dict()
            time.sleep(0.6)
            if not data['SeasonTotalsRegularSeason']:
                return None
            return self._build_season_dict(data['SeasonTotalsRegularSeason'][-1])
        except Exception as e:
            print(f"Error getting player stats: {e}")
            return None
 
    def get_player_all_seasons(self, player_id):
        # all regular seasons, newest first
        try:
            career = playercareerstats.PlayerCareerStats(player_id=player_id)
            data = career.get_normalized_dict()
            time.sleep(0.6)
            if not data['SeasonTotalsRegularSeason']:
                return []
            return [self._build_season_dict(s) for s in reversed(data['SeasonTotalsRegularSeason'])]
        except Exception as e:
            print(f"Error getting all seasons: {e}")
            return []
 
    def get_player_all_playoff_seasons(self, player_id):
        # same endpoint but reads the postseason totals instead
        try:
            career = playercareerstats.PlayerCareerStats(player_id=player_id)
            data = career.get_normalized_dict()
            time.sleep(0.6)
            if not data['SeasonTotalsPostSeason']:
                return []
            return [self._build_season_dict(s) for s in reversed(data['SeasonTotalsPostSeason'])]
        except Exception as e:
            print(f"Error getting playoff seasons: {e}")
            return []
 
    def get_player_game_log(self, player_id, season, season_type='Regular Season'):
        """
        gets every game a player played in a given season
        season_type is either 'Regular Season' or 'Playoffs'
        returns a list of individual game dicts, oldest game first
        """
        try:
            log = playergamelog.PlayerGameLog(
                player_id=player_id,
                season=season,
                season_type_all_star=season_type
            )
            data = log.get_normalized_dict()
            time.sleep(0.6)
 
            games = data.get('PlayerGameLog', [])
            if not games:
                return []
 
            result = []
            for g in games:
                # game date comes as 'OCT 28, 2015' - store it as-is for display
                # matchup is like 'LAL vs. GSW' or 'LAL @ GSW'
                matchup = g.get('MATCHUP', '')
 
                # figure out the opponent abbreviation from the matchup string
                # format is either 'TEAM vs. OPP' or 'TEAM @ OPP'
                if ' vs. ' in matchup:
                    opponent = matchup.split(' vs. ')[1]
                elif ' @ ' in matchup:
                    opponent = matchup.split(' @ ')[1]
                else:
                    opponent = 'N/A'
 
                # home/away - @ means away, vs. means home
                location = 'Away' if '@ ' in matchup else 'Home'
 
                result.append({
                    'game_id':  g.get('Game_ID', ''),
                    'date':     g.get('GAME_DATE', ''),
                    'matchup':  matchup,
                    'opponent': opponent,
                    'location': location,
                    'wl':       g.get('WL', ''),
                    'min':      g.get('MIN', 0) or 0,
                    'pts':      g.get('PTS', 0) or 0,
                    'fgm':      g.get('FGM', 0) or 0,
                    'fga':      g.get('FGA', 0) or 0,
                    'fg_pct':   round((g.get('FG_PCT', 0) or 0) * 100, 1),
                    'fg3m':     g.get('FG3M', 0) or 0,
                    'fg3a':     g.get('FG3A', 0) or 0,
                    'fg3_pct':  round((g.get('FG3_PCT', 0) or 0) * 100, 1),
                    'ftm':      g.get('FTM', 0) or 0,
                    'fta':      g.get('FTA', 0) or 0,
                    'ft_pct':   round((g.get('FT_PCT', 0) or 0) * 100, 1),
                    'reb':      g.get('REB', 0) or 0,
                    'oreb':     g.get('OREB', 0) or 0,
                    'dreb':     g.get('DREB', 0) or 0,
                    'ast':      g.get('AST', 0) or 0,
                    'stl':      g.get('STL', 0) or 0,
                    'blk':      g.get('BLK', 0) or 0,
                    'tov':      g.get('TOV', 0) or 0,
                    'pf':       g.get('PF', 0) or 0,
                    'plus_minus': g.get('PLUS_MINUS', 0) or 0,
                })
 
            # game log comes back newest first - reverse so oldest game is index 0
            result.reverse()
            return result
 
        except Exception as e:
            print(f"Error getting game log: {e}")
            return []
 
    def _format_date(self, date_string):
        # api returns dates as '1997-09-02T00:00:00' so we clean that up
        if not date_string:
            return 'N/A'
        try:
            date_part = date_string.split('T')[0]
            year, month, day = date_part.split('-')
            months = ['','January','February','March','April','May','June',
                     'July','August','September','October','November','December']
            return f"{months[int(month)]} {int(day)}, {year}"
        except:
            return date_string
 
    def get_player_complete_data(self, player_id):
        # bundles everything for the main player api endpoint
        player_info = self.get_player_info(player_id)
        if not player_info:
            return None
        player_stats = self.get_player_stats(player_id)
        return {
            'info':     player_info,
            'stats':    player_stats,
            'advanced': player_stats.get('advanced') if player_stats else None
        }
 