"""
NBA Player Analytics Dashboard
Main Flask application
"""

from flask import Flask, render_template, request, jsonify
from nba_service import NBAStatsAPI

app = Flask(__name__)
nba_api = NBAStatsAPI()

# ── HOME ──────────────────────────────────────────────────────────────────────

@app.route('/')
def home():
    return render_template('index.html')

# ── PLAYER ROUTES ─────────────────────────────────────────────────────────────

@app.route('/api/search/players')
def search_players():
    query = request.args.get('q', '')
    if len(query) < 2:
        return jsonify({'error': 'search too short'}), 400
    players = nba_api.search_players(query)
    return jsonify({'players': players})

@app.route('/api/player/<player_id>')
def get_player_data(player_id):
    player_data = nba_api.get_player_complete_data(player_id)
    if not player_data:
        return jsonify({'error': 'player not found'}), 404
    return jsonify(player_data)

@app.route('/player/<player_id>')
def player_page(player_id):
    return render_template('player.html', player_id=player_id)

@app.route('/api/player/<player_id>/seasons')
def get_player_seasons(player_id):
    seasons = nba_api.get_player_all_seasons(player_id)
    if not seasons:
        return jsonify({'error': 'no seasons found'}), 404
    return jsonify({'seasons': seasons})

@app.route('/api/player/<player_id>/playoffs')
def get_player_playoffs(player_id):
    seasons = nba_api.get_player_all_playoff_seasons(player_id)
    return jsonify({'seasons': seasons})

@app.route('/api/player/<player_id>/gamelog/<season>/<season_type>')
def get_game_log(player_id, season, season_type):
    api_type = 'Playoffs' if season_type == 'playoffs' else 'Regular Season'
    games = nba_api.get_player_game_log(player_id, season, api_type)
    return jsonify({'games': games})

@app.route('/api/player/<player_id>/shotchart/<season_type>/<season>')
def get_shot_chart(player_id, season_type, season):
    api_type = 'Playoffs' if season_type == 'playoffs' else 'Regular Season'
    data = nba_api.get_shot_chart_data(player_id, season, api_type)
    return jsonify(data)

# ── TEAM ROUTES ───────────────────────────────────────────────────────────────

@app.route('/teams')
def teams_page():
    return render_template('teams.html')

@app.route('/team/<team_id>')
def team_page(team_id):
    return render_template('team.html', team_id=team_id)

@app.route('/api/teams')
def get_teams():
    """
    returns all 30 nba teams grouped by conference and division
    uses static data so response is instant
    """
    all_teams = nba_api.get_all_teams()
    grouped = {'East': {}, 'West': {}}
    for t in all_teams:
        conf = t['conference']
        div  = t['division']
        if div not in grouped[conf]:
            grouped[conf][div] = []
        grouped[conf][div].append(t)
    return jsonify(grouped)

@app.route('/api/team/<team_id>/roster')
def get_team_roster(team_id):
    # optional ?season=2018-19 returns historical roster for that year
    season = request.args.get('season', None)
    roster = nba_api.get_team_roster(team_id, season=season)
    return jsonify({'roster': roster or []})

@app.route('/api/team/<team_id>/stats/<season_type>/<season>')
def get_team_stats(team_id, season_type, season):
    """
    per-game stats for a team in a specific season
    season_type first to avoid Flask choking on the hyphen in season string
    """
    api_type = 'Playoffs' if season_type == 'playoffs' else 'Regular Season'
    stats = nba_api.get_team_season_stats(team_id, season, api_type)
    if not stats:
        return jsonify({'error': 'no stats found'}), 404
    return jsonify(stats)

@app.route('/api/team/<team_id>/history')
def get_team_history(team_id):
    """
    year-by-year stats for a franchise
    ?type=playoffs fetches postseason history instead of regular season
    used to populate the correct season dropdown based on current toggle mode
    """
    season_type = request.args.get('type', 'regular')
    api_type = 'Playoffs' if season_type == 'playoffs' else 'Regular Season'
    history = nba_api.get_team_history(team_id, season_type=api_type)
    return jsonify({'seasons': history})

@app.route('/api/league/teamstats/<season_type>/<season>')
def get_league_team_stats(season_type, season):
    """
    per-game stats for all 30 teams in one shot
    season_type first to avoid Flask choking on the hyphen in season string
    frontend uses this to compute rank badges for each stat
    """
    api_type = 'Playoffs' if season_type == 'playoffs' else 'Regular Season'
    stats = nba_api.get_league_team_stats(season, api_type)
    return jsonify(stats)

@app.route('/api/player/<player_id>/statsonly')
def get_player_stats_only(player_id):
    """
    lightweight endpoint - only calls playercareerstats, skips bio
    optional ?season=2023-24&type=playoffs for team roster playoff stats
    """
    season      = request.args.get('season', None)
    season_type = request.args.get('type', 'regular')
    api_type    = 'Playoffs' if season_type == 'playoffs' else 'Regular Season'
    stats = nba_api.get_player_stats_latest(player_id, season=season, season_type=api_type)
    if not stats:
        return jsonify({'error': 'no stats found'}), 404
    return jsonify({'stats': stats})

@app.route('/api/player/<player_id>/gamelog/daterange')
def get_game_log_daterange(player_id):
    """
    fetches game log for any date range - figures out which nba season(s)
    the range spans, fetches each one, merges, then filters to exact dates
    date_from and date_to are ISO strings: '2023-11-01'
    season_type: 'regular' or 'playoffs'
    """
    date_from   = request.args.get('from', '')
    date_to     = request.args.get('to', '')
    season_type = request.args.get('type', 'regular')
    api_type    = 'Playoffs' if season_type == 'playoffs' else 'Regular Season'

    if not date_from or not date_to:
        return jsonify({'error': 'from and to dates required'}), 400

    from datetime import date
    try:
        d_from = date.fromisoformat(date_from)
        d_to   = date.fromisoformat(date_to)
    except ValueError:
        return jsonify({'error': 'invalid date format'}), 400

    # figure out which nba seasons overlap this range
    # nba season YYYY-YY starts in october of YYYY and ends in june of YYYY+1
    def date_to_season(d):
        # if month >= october, it's the first year of the season
        year = d.year if d.month >= 10 else d.year - 1
        return f"{year}-{str(year + 1)[2:]}"

    seasons_needed = set()
    # walk month by month through the range to catch all overlapping seasons
    from datetime import timedelta
    cursor = date(d_from.year, d_from.month, 1)
    end    = date(d_to.year, d_to.month, 1)
    while cursor <= end:
        seasons_needed.add(date_to_season(cursor))
        # advance by one month
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)

    # fetch each required season and merge
    all_games = []
    for season in sorted(seasons_needed):
        games = nba_api.get_player_game_log(player_id, season, api_type)
        all_games.extend(games)

    # filter to exact date range using iso_date field
    filtered = [g for g in all_games
                if g.get('iso_date') and date_from <= g['iso_date'] <= date_to]

    # sort oldest first
    filtered.sort(key=lambda g: g.get('iso_date', ''))

    return jsonify({'games': filtered})

# ── COMPARE ROUTES ────────────────────────────────────────────────────────────

@app.route('/compare/<player_id1>/<player_id2>')
def compare_page(player_id1, player_id2):
    return render_template('compare.html', player_id1=player_id1, player_id2=player_id2)

@app.route('/api/compare/<player_id1>/<player_id2>')
def compare_players(player_id1, player_id2):
    data1 = nba_api.get_player_complete_data(player_id1)
    data2 = nba_api.get_player_complete_data(player_id2)
    if not data1 or not data2:
        return jsonify({'error': 'one or both players not found'}), 404
    return jsonify({'player1': data1, 'player2': data2})

if __name__ == '__main__':
    print("🏀 NBA Analytics Dashboard")
    print("=" * 50)
    print("Open browser to: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)