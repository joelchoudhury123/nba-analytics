"""
NBA Player Analytics Dashboard
Main Flask application
"""

from flask import Flask, render_template, request, jsonify
from nba_service import NBAStatsAPI

app = Flask(__name__)
nba_api = NBAStatsAPI()

@app.route('/')
def home():
    return render_template('index.html')

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
    # returns empty list (not 404) if player never made playoffs
    seasons = nba_api.get_player_all_playoff_seasons(player_id)
    return jsonify({'seasons': seasons})

@app.route('/api/player/<player_id>/gamelog/<season>/<season_type>')
def get_game_log(player_id, season, season_type):
    """
    get every game for a player in a given season
    season format: '2015-16'
    season_type: 'regular' or 'playoffs' (we convert to the api's expected string)
    """
    # convert our url-friendly names to the api's expected format
    api_type = 'Playoffs' if season_type == 'playoffs' else 'Regular Season'
    games = nba_api.get_player_game_log(player_id, season, api_type)
    return jsonify({'games': games})

@app.route('/api/player/<player_id>/shotchart/<season_type>/<season>')
def get_shot_chart(player_id, season_type, season):
    """
    returns every shot attempt for a player in a given season
    season_type comes first in the URL so Flask doesn't choke on the hyphen in season
    season format: '2023-24'
    season_type: 'regular' or 'playoffs'
    each shot has x/y coords (nba tenth-feet), made/missed flag, zone, and shot type
    also returns a zone summary array for the breakdown panel
    """
    api_type = 'Playoffs' if season_type == 'playoffs' else 'Regular Season'
    data = nba_api.get_shot_chart_data(player_id, season, api_type)
    return jsonify(data)

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