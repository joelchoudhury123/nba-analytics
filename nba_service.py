"""
handles all the nba api calls and stat calculations
using the nba_api library because it wraps the official stats.nba.com endpoints
and handles headers/rate limiting for us
"""

from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import (
    commonplayerinfo, playercareerstats, playergamelog,
    commonteamroster, teamyearbyyearstats, teamdashboardbygeneralsplits,
    leaguedashteamstats
)
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
# bump timeout to 60s - home networks can be slow to reach stats.nba.com
NBAStatsHTTP.timeout = 60

# static conference/division mapping - this never changes mid-season
# keyed by team abbreviation so we can look up any team in O(1)
CONFERENCE_MAP = {
    'East': {
        'Atlantic':  ['BOS','BKN','NYK','PHI','TOR'],
        'Central':   ['CHI','CLE','DET','IND','MIL'],
        'Southeast': ['ATL','CHA','MIA','ORL','WAS'],
    },
    'West': {
        'Northwest': ['DEN','MIN','OKC','POR','UTA'],
        'Pacific':   ['GSW','LAC','LAL','PHX','SAC'],
        'Southwest': ['DAL','HOU','MEM','NOP','SAS'],
    }
}

# build reverse lookup: abbreviation -> {conference, division}
_TEAM_CONF_LOOKUP = {}
for _conf, _divs in CONFERENCE_MAP.items():
    for _div, _abbrs in _divs.items():
        for _abbr in _abbrs:
            _TEAM_CONF_LOOKUP[_abbr] = {'conference': _conf, 'division': _div}


class NBAStatsAPI:

    def __init__(self):
        pass

    def _fetch_with_retry(self, fn, retries=3, delay=4):
        """
        wraps any nba_api call with retry logic
        stats.nba.com drops connections on home networks under load
        3 attempts with 4s delay covers most transient failures
        """
        last_err = None
        for attempt in range(retries):
            try:
                if attempt > 0:
                    print(f"  retrying after {delay}s (attempt {attempt+1}/{retries})...")
                    time.sleep(delay)
                return fn()
            except Exception as e:
                last_err = e
                print(f"  attempt {attempt+1} failed: {e.__class__.__name__}: {e}")
        raise last_err

    # ── TEAM METHODS ──────────────────────────────────────────────────────────

    def get_all_teams(self):
        """
        returns all 30 nba franchises with conference and division attached
        uses the static teams list so no api call needed - instant response
        """
        try:
            all_teams = teams.get_teams()
            result = []
            for t in all_teams:
                abbr = t['abbreviation']
                conf_info = _TEAM_CONF_LOOKUP.get(abbr, {'conference': 'Unknown', 'division': 'Unknown'})
                result.append({
                    'id':           str(t['id']),
                    'name':         t['full_name'],
                    'abbreviation': abbr,
                    'nickname':     t['nickname'],
                    'city':         t['city'],
                    'conference':   conf_info['conference'],
                    'division':     conf_info['division'],
                })
            result.sort(key=lambda x: (x['conference'], x['division'], x['city']))
            return result
        except Exception as e:
            print(f"Error getting all teams: {e}")
            return []

    def get_team_roster(self, team_id, season=None):
        """
        returns the roster for a given team
        season averages are fetched separately by the frontend in parallel
        """
        try:
            kwargs = {'team_id': team_id}
            if season:
                kwargs['season'] = season
            def _call():
                r = commonteamroster.CommonTeamRoster(**kwargs)
                time.sleep(0.6)
                return r.get_normalized_dict()
            data = self._fetch_with_retry(_call)

            players_raw = data.get('CommonTeamRoster', [])
            result = []
            for p in players_raw:
                result.append({
                    'player_id': str(p.get('PLAYER_ID', '')),
                    'name':      p.get('PLAYER', ''),
                    'number':    p.get('NUM', 'N/A') or 'N/A',
                    'position':  p.get('POSITION', 'N/A') or 'N/A',
                    'height':    p.get('HEIGHT', 'N/A') or 'N/A',
                    'weight':    p.get('WEIGHT', 'N/A') or 'N/A',
                    'age':       p.get('AGE', 'N/A') or 'N/A',
                    'exp':       p.get('EXP', '0') or '0',
                    'school':    p.get('SCHOOL', 'N/A') or 'N/A',
                })
            return result
        except Exception as e:
            print(f"Error getting team roster: {e}")
            return []

    def get_team_season_stats(self, team_id, season, season_type='Regular Season'):
        """
        returns per-game offensive + defensive stats for a team, plus built-in league ranks
        uses leaguedashteamstats twice:
          1. Base measure    -> offensive stats + _RANK fields (already computed by nba.com)
          2. Opponent measure -> defensive stats (what the team allowed) + opponent ranks
        this is more reliable than teamdashboardbygeneralsplits opponent measure
        which tends to return empty data
        """
        try:
            # --- offensive stats + ranks (Base measure) ---
            def _off_call():
                d = leaguedashteamstats.LeagueDashTeamStats(
                    season=season,
                    season_type_all_star=season_type,
                    per_mode_detailed='PerGame',
                    measure_type_detailed_defense='Base',
                )
                time.sleep(0.6)
                return d.get_normalized_dict()
            off_data = self._fetch_with_retry(_off_call)

            off_rows = off_data.get('LeagueDashTeamStats', [])
            if not off_rows:
                return None

            # find this team's row
            tid_int = int(team_id)
            r = next((x for x in off_rows if x.get('TEAM_ID') == tid_int), None)
            if not r:
                return None

            # defensive (opponent measure) removed - too unreliable across networks
            return {
                'season':          season,
                'gp':              r.get('GP', 0),
                'w':               r.get('W', 0),
                'l':               r.get('L', 0),
                'w_pct':           round((r.get('W_PCT', 0) or 0) * 100, 1),
                # offensive per game
                'pts':             round(r.get('PTS', 0) or 0, 1),
                'reb':             round(r.get('REB', 0) or 0, 1),
                'ast':             round(r.get('AST', 0) or 0, 1),
                'stl':             round(r.get('STL', 0) or 0, 1),
                'blk':             round(r.get('BLK', 0) or 0, 1),
                'tov':             round(r.get('TOV', 0) or 0, 1),
                'fgm':             round(r.get('FGM', 0) or 0, 1),
                'fga':             round(r.get('FGA', 0) or 0, 1),
                'fg_pct':          round((r.get('FG_PCT', 0) or 0) * 100, 1),
                'fg3m':            round(r.get('FG3M', 0) or 0, 1),
                'fg3a':            round(r.get('FG3A', 0) or 0, 1),
                'fg3_pct':         round((r.get('FG3_PCT', 0) or 0) * 100, 1),
                'ftm':             round(r.get('FTM', 0) or 0, 1),
                'fta':             round(r.get('FTA', 0) or 0, 1),
                'ft_pct':          round((r.get('FT_PCT', 0) or 0) * 100, 1),
                'oreb':            round(r.get('OREB', 0) or 0, 1),
                'dreb':            round(r.get('DREB', 0) or 0, 1),
                'pf':              round(r.get('PF', 0) or 0, 1),
                'plus_minus':      round(r.get('PLUS_MINUS', 0) or 0, 1),
                # built-in league ranks from nba.com (1 = best for most stats)
                'pts_rank':        r.get('PTS_RANK', 0),
                'reb_rank':        r.get('REB_RANK', 0),
                'ast_rank':        r.get('AST_RANK', 0),
                'stl_rank':        r.get('STL_RANK', 0),
                'blk_rank':        r.get('BLK_RANK', 0),
                'tov_rank':        r.get('TOV_RANK', 0),
                'oreb_rank':       r.get('OREB_RANK', 0),
                'dreb_rank':       r.get('DREB_RANK', 0),
                'fgm_rank':        r.get('FGM_RANK', 0),
                'fga_rank':        r.get('FGA_RANK', 0),
                'fg_pct_rank':     r.get('FG_PCT_RANK', 0),
                'fg3m_rank':       r.get('FG3M_RANK', 0),
                'fg3a_rank':       r.get('FG3A_RANK', 0),
                'fg3_pct_rank':    r.get('FG3_PCT_RANK', 0),
                'ftm_rank':        r.get('FTM_RANK', 0),
                'fta_rank':        r.get('FTA_RANK', 0),
                'ft_pct_rank':     r.get('FT_PCT_RANK', 0),
                'plus_minus_rank': r.get('PLUS_MINUS_RANK', 0),
                'w_pct_rank':      r.get('W_PCT_RANK', 0),
            }
        except Exception as e:
            print(f"Error getting team season stats: {e}")
            return None

    def get_team_history(self, team_id, season_type='Regular Season'):
        """
        returns year-by-year stats for a franchise going back as far as the api has
        uses teamyearbyyearstats which is more reliable than the dashboard endpoint
        accepts season_type so we can fetch playoff history for the dropdown too
        """
        try:
            def _call():
                h = teamyearbyyearstats.TeamYearByYearStats(
                    team_id=team_id,
                    per_mode_simple='PerGame',
                    season_type_all_star=season_type,
                )
                time.sleep(0.6)
                return h.get_normalized_dict()
            data = self._fetch_with_retry(_call)

            rows = data.get('TeamStats', [])
            if not rows:
                return []

            result = []
            for r in rows:
                result.append({
                    'season':  r.get('YEAR', ''),
                    'gp':      r.get('GP', 0),
                    'w':       r.get('W', 0),
                    'l':       r.get('L', 0),
                    'w_pct':   round((r.get('W_PCT', 0) or 0) * 100, 1),
                    'pts':     round(r.get('PTS', 0) or 0, 1),
                    'reb':     round(r.get('REB', 0) or 0, 1),
                    'ast':     round(r.get('AST', 0) or 0, 1),
                    'stl':     round(r.get('STL', 0) or 0, 1),
                    'blk':     round(r.get('BLK', 0) or 0, 1),
                    'tov':     round(r.get('TOV', 0) or 0, 1),
                    'fg_pct':  round((r.get('FG_PCT', 0) or 0) * 100, 1),
                    'fg3_pct': round((r.get('FG3_PCT', 0) or 0) * 100, 1),
                    'ft_pct':  round((r.get('FT_PCT', 0) or 0) * 100, 1),
                })
            # newest season first
            result.reverse()
            return result
        except Exception as e:
            print(f"Error getting team history: {e}")
            return []

    def get_league_team_stats(self, season, season_type='Regular Season'):
        """
        returns per-game stats for all 30 teams in one call
        used by the frontend to compute where each team ranks in each category
        keyed by team_id string so lookup is O(1)
        """
        try:
            dash = leaguedashteamstats.LeagueDashTeamStats(
                season=season,
                season_type_all_star=season_type,
                per_mode_simple='PerGame',
                measure_type_simple='Base',
            )
            data = dash.get_normalized_dict()
            time.sleep(0.6)

            rows = data.get('LeagueDashTeamStats', [])
            result = {}
            for r in rows:
                result[str(r.get('TEAM_ID', ''))] = {
                    'team_name': r.get('TEAM_NAME', ''),
                    'pts':       round(r.get('PTS', 0) or 0, 1),
                    'reb':       round(r.get('REB', 0) or 0, 1),
                    'ast':       round(r.get('AST', 0) or 0, 1),
                    'stl':       round(r.get('STL', 0) or 0, 1),
                    'blk':       round(r.get('BLK', 0) or 0, 1),
                    'tov':       round(r.get('TOV', 0) or 0, 1),
                    'fg_pct':    round((r.get('FG_PCT', 0) or 0) * 100, 1),
                    'fg3_pct':   round((r.get('FG3_PCT', 0) or 0) * 100, 1),
                    'ft_pct':    round((r.get('FT_PCT', 0) or 0) * 100, 1),
                    'w_pct':     round((r.get('W_PCT', 0) or 0) * 100, 1),
                    'plus_minus':round(r.get('PLUS_MINUS', 0) or 0, 1),
                }
            return result
        except Exception as e:
            print(f"Error getting league team stats: {e}")
            return {}

    def get_player_stats_latest(self, player_id, season=None, season_type='Regular Season'):
        """
        lightweight version of get_player_stats - only calls playercareerstats
        skips commonplayerinfo entirely so it's one api call instead of two
        if season is given, returns that specific season's row
        if season_type is Playoffs, reads postseason totals instead
        used by the roster table which only needs stat numbers, not bio
        """
        try:
            def _call():
                r = playercareerstats.PlayerCareerStats(player_id=player_id)
                return r.get_normalized_dict()
            data = self._fetch_with_retry(_call)
            time.sleep(0.6)

            key = 'SeasonTotalsPostSeason' if season_type == 'Playoffs' else 'SeasonTotalsRegularSeason'
            rows = data.get(key, [])
            if not rows:
                return None

            if season:
                # find the specific season row
                row = next((r for r in rows if r.get('SEASON_ID') == season), None)
                return self._build_season_dict(row) if row else None

            # default: most recent season
            return self._build_season_dict(rows[-1])
        except Exception as e:
            print(f"Error getting latest player stats: {e}")
            return None

    # ── PLAYER METHODS ────────────────────────────────────────────────────────

    def search_players(self, player_name):
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
        try:
            def _call():
                r = commonplayerinfo.CommonPlayerInfo(player_id=player_id)
                return r.get_normalized_dict()
            data = self._fetch_with_retry(_call)
            time.sleep(0.6)
            info = data['CommonPlayerInfo'][0]
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
        ts_pct    = round((pts / ts_denominator) * 100, 1) if ts_denominator > 0 else 0.0
        efg_pct   = round(((fgm + 0.5 * fg3m) / fga) * 100, 1) if fga > 0 else 0.0
        ftr       = round((fta / fga), 3) if fga > 0 else 0.0
        three_par = round((fg3a / fga) * 100, 1) if fga > 0 else 0.0
        per36_pts = round((pts  / min_) * 36, 1) if min_ > 0 else 0.0
        per36_reb = round((reb  / min_) * 36, 1) if min_ > 0 else 0.0
        per36_ast = round((ast  / min_) * 36, 1) if min_ > 0 else 0.0
        per36_stl = round((stl  / min_) * 36, 1) if min_ > 0 else 0.0
        per36_blk = round((blk  / min_) * 36, 1) if min_ > 0 else 0.0
        per36_tov = round((tov  / min_) * 36, 1) if min_ > 0 else 0.0
        ast_tov   = round(ast / tov, 2) if tov > 0 else float(ast)
        stock     = round((stl + blk) / gp, 1) if gp > 0 else 0.0

        return {
            'ts_pct': ts_pct, 'efg_pct': efg_pct, 'ftr': ftr, 'three_par': three_par,
            'per36_pts': per36_pts, 'per36_reb': per36_reb, 'per36_ast': per36_ast,
            'per36_stl': per36_stl, 'per36_blk': per36_blk, 'per36_tov': per36_tov,
            'ast_tov': ast_tov, 'stock': stock,
        }

    def _build_season_dict(self, stats):
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
        try:
            def _call():
                r = playercareerstats.PlayerCareerStats(player_id=player_id)
                return r.get_normalized_dict()
            data = self._fetch_with_retry(_call)
            time.sleep(0.6)
            if not data['SeasonTotalsRegularSeason']:
                return None
            return self._build_season_dict(data['SeasonTotalsRegularSeason'][-1])
        except Exception as e:
            print(f"Error getting player stats: {e}")
            return None

    def get_player_all_seasons(self, player_id):
        try:
            def _call():
                r = playercareerstats.PlayerCareerStats(player_id=player_id)
                return r.get_normalized_dict()
            data = self._fetch_with_retry(_call)
            time.sleep(0.6)
            if not data['SeasonTotalsRegularSeason']:
                return []
            return [self._build_season_dict(s) for s in reversed(data['SeasonTotalsRegularSeason'])]
        except Exception as e:
            print(f"Error getting all seasons: {e}")
            return []

    def get_player_all_playoff_seasons(self, player_id):
        try:
            def _call():
                r = playercareerstats.PlayerCareerStats(player_id=player_id)
                return r.get_normalized_dict()
            data = self._fetch_with_retry(_call)
            time.sleep(0.6)
            if not data['SeasonTotalsPostSeason']:
                return []
            return [self._build_season_dict(s) for s in reversed(data['SeasonTotalsPostSeason'])]
        except Exception as e:
            print(f"Error getting playoff seasons: {e}")
            return []

    def get_player_game_log(self, player_id, season, season_type='Regular Season'):
        try:
            def _call():
                r = playergamelog.PlayerGameLog(
                    player_id=player_id,
                    season=season,
                    season_type_all_star=season_type
                )
                return r.get_normalized_dict()
            data = self._fetch_with_retry(_call)
            time.sleep(0.6)
            games = data.get('PlayerGameLog', [])
            if not games:
                return []
            result = []
            for g in games:
                matchup = g.get('MATCHUP', '')
                if ' vs. ' in matchup:
                    opponent = matchup.split(' vs. ')[1]
                elif ' @ ' in matchup:
                    opponent = matchup.split(' @ ')[1]
                else:
                    opponent = 'N/A'
                location = 'Away' if '@ ' in matchup else 'Home'
                # convert 'OCT 28, 2023' to '2023-10-28' so JS date comparisons work
                raw_date = g.get('GAME_DATE', '')
                try:
                    import datetime
                    iso_date = datetime.datetime.strptime(raw_date, '%b %d, %Y').strftime('%Y-%m-%d')
                except:
                    iso_date = ''

                result.append({
                    'game_id':    g.get('Game_ID', ''),
                    'date':       raw_date,
                    'iso_date':   iso_date,
                    'matchup':    matchup,
                    'opponent':   opponent,
                    'location':   location,
                    'wl':         g.get('WL', ''),
                    'min':        g.get('MIN', 0) or 0,
                    'pts':        g.get('PTS', 0) or 0,
                    'fgm':        g.get('FGM', 0) or 0,
                    'fga':        g.get('FGA', 0) or 0,
                    'fg_pct':     round((g.get('FG_PCT', 0) or 0) * 100, 1),
                    'fg3m':       g.get('FG3M', 0) or 0,
                    'fg3a':       g.get('FG3A', 0) or 0,
                    'fg3_pct':    round((g.get('FG3_PCT', 0) or 0) * 100, 1),
                    'ftm':        g.get('FTM', 0) or 0,
                    'fta':        g.get('FTA', 0) or 0,
                    'ft_pct':     round((g.get('FT_PCT', 0) or 0) * 100, 1),
                    'reb':        g.get('REB', 0) or 0,
                    'oreb':       g.get('OREB', 0) or 0,
                    'dreb':       g.get('DREB', 0) or 0,
                    'ast':        g.get('AST', 0) or 0,
                    'stl':        g.get('STL', 0) or 0,
                    'blk':        g.get('BLK', 0) or 0,
                    'tov':        g.get('TOV', 0) or 0,
                    'pf':         g.get('PF', 0) or 0,
                    'plus_minus': g.get('PLUS_MINUS', 0) or 0,
                })
            result.reverse()
            return result
        except Exception as e:
            print(f"Error getting game log: {e}")
            return []

    def get_shot_chart_data(self, player_id, season, season_type='Regular Season'):
        try:
            from nba_api.stats.endpoints import shotchartdetail
            def _call():
                r = shotchartdetail.ShotChartDetail(
                    team_id=0,
                    player_id=player_id,
                    season_nullable=season,
                    season_type_all_star=season_type,
                    context_measure_simple='FGA'
                )
                return r.get_normalized_dict()
            data = self._fetch_with_retry(_call)
            time.sleep(0.6)
            shots_raw = data.get('Shot_Chart_Detail', [])
            if not shots_raw:
                return {'shots': [], 'zones': []}
            shots = []
            for s in shots_raw:
                shots.append({
                    'x':        s.get('LOC_X', 0),
                    'y':        s.get('LOC_Y', 0),
                    'made':     s.get('SHOT_MADE_FLAG', 0) == 1,
                    'zone':     s.get('SHOT_ZONE_BASIC', ''),
                    'distance': s.get('SHOT_DISTANCE', 0),
                    'type':     s.get('ACTION_TYPE', ''),
                    'value':    s.get('SHOT_TYPE', ''),
                })
            zone_totals = {}
            for s in shots:
                z = s['zone'] or 'Unknown'
                if z not in zone_totals:
                    zone_totals[z] = {'made': 0, 'attempts': 0}
                zone_totals[z]['attempts'] += 1
                if s['made']:
                    zone_totals[z]['made'] += 1
            zones = []
            for zone_name, counts in zone_totals.items():
                pct = round((counts['made'] / counts['attempts']) * 100, 1) if counts['attempts'] > 0 else 0.0
                zones.append({'zone': zone_name, 'made': counts['made'], 'attempts': counts['attempts'], 'pct': pct})
            zones.sort(key=lambda z: z['attempts'], reverse=True)
            return {'shots': shots, 'zones': zones}
        except Exception as e:
            print(f"Error getting shot chart: {e}")
            return {'shots': [], 'zones': []}

    def _format_date(self, date_string):
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
        player_info = self.get_player_info(player_id)
        if not player_info:
            return None
        player_stats = self.get_player_stats(player_id)
        return {
            'info':     player_info,
            'stats':    player_stats,
            'advanced': player_stats.get('advanced') if player_stats else None
        }