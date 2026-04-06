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
    """homepage with search"""
    return render_template('index.html')

@app.route('/api/search/players')
def search_players():
    """search for players - called when user types in search box"""
    
    # get the search query from the URL
    query = request.args.get('q', '')
    
    # need at least 2 characters to search
    if len(query) < 2:
        return jsonify({'error': 'search too short'}), 400
    
    # search using our NBA API
    players = nba_api.search_players(query)
    return jsonify({'players': players})

@app.route('/api/player/<player_id>')
def get_player_data(player_id):
    """get all data for one player"""
    
    player_data = nba_api.get_player_complete_data(player_id)
    
    if not player_data:
        return jsonify({'error': 'player not found'}), 404
    
    return jsonify(player_data)

@app.route('/player/<player_id>')
def player_page(player_id):
    """show the player profile page"""
    return render_template('player.html', player_id=player_id)

@app.route('/api/player/<player_id>/seasons')
def get_player_seasons(player_id):
    """get all seasons for a player"""
    
    seasons = nba_api.get_player_all_seasons(player_id)
    
    if not seasons:
        return jsonify({'error': 'no seasons found'}), 404
    
    return jsonify({'seasons': seasons})

@app.route('/compare/<player_id1>/<player_id2>')
def compare_page(player_id1, player_id2):
    # show the side-by-side player comparison page
    return render_template('compare.html', player_id1=player_id1, player_id2=player_id2)

@app.route('/api/compare/<player_id1>/<player_id2>')
def compare_players(player_id1, player_id2):
    # fetch data for both players and return it together
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