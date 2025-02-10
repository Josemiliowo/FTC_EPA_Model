import requests
import base64
import math
import pandas as pd

# Constants
API_URL = "http://ftc-api.firstinspires.org/v2.0"
DEFAULT_EPA = 80

# Your credentials for the API
USERNAME = "_____"  # Replace with your username
AUTHORIZATION_KEY = "_____"  # Replace with your authorization key

# Initialize EPA scores
epa_scores = {}

# DataFrame to store EPA scores
epa_dataframe = pd.DataFrame(columns=["team_id", "epa"])

# Helper Functions
def encode_authorization(username, auth_key):
    """Generate the Base64 Authorization header."""
    combined_string = f"{username}:{auth_key}"
    return base64.b64encode(combined_string.encode()).decode()

def fetch_matches(event_code, headers):
    """Fetch match results for a specific event."""
    url = f"{API_URL}/2024/matches/{event_code}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()["matches"]

def calculate_k_factor(match_number):
    """Calculate the K-factor dynamically based on match number."""
    if match_number <= 6:
        return 0.5
    elif match_number <= 12:
        return 0.5 - (1 / 30) * (match_number - 6)
    return 0.3

def calculate_margin_parameter(match_number):
    """Calculate the margin parameter (M) dynamically based on match number."""
    if match_number <= 12:
        return 0
    elif match_number <= 36:
        return (match_number - 12) / 24
    return 1

def calculate_default_epa(matches):
    """Calculate the default EPA dynamically from match scores."""
    total_scores = 0
    total_teams = 0

    for match in matches:
        red_score = match.get("scoreRedFinal", 0)
        blue_score = match.get("scoreBlueFinal", 0)
        total_scores += red_score + blue_score
        total_teams += 4  # Assuming 2 teams per alliance

    return total_scores / total_teams if total_teams > 0 else 60

def update_epa(red_team_ids, blue_team_ids, red_actual_score, blue_actual_score, k_factor, margin):
    """Update EPA scores for all teams based on the match results."""
    global epa_scores

    # Calculate total EPA for each alliance
    red_total_epa = sum(epa_scores.get(team, DEFAULT_EPA) for team in red_team_ids)
    blue_total_epa = sum(epa_scores.get(team, DEFAULT_EPA) for team in blue_team_ids)

    # Calculate individual EPA updates
    for team in red_team_ids:
        old_epa = epa_scores.get(team, DEFAULT_EPA)
        surprise_factor = (red_actual_score - red_total_epa) - margin * (blue_actual_score - blue_total_epa)
        epa_scores[team] = old_epa + (k_factor / (1 + margin)) * surprise_factor / len(red_team_ids)

    for team in blue_team_ids:
        old_epa = epa_scores.get(team, DEFAULT_EPA)
        surprise_factor = (blue_actual_score - blue_total_epa) - margin * (red_actual_score - red_total_epa)
        epa_scores[team] = old_epa + (k_factor / (1 + margin)) * surprise_factor / len(blue_team_ids)

def process_match(match, match_number):
    """Process a single match and update EPA scores."""
    # Calculate K-factor and margin parameter dynamically
    k_factor = calculate_k_factor(match_number)
    margin = calculate_margin_parameter(match_number)

    # Extract team and score information
    red_team_ids = [team["teamNumber"] for team in match.get("teams", []) if team["station"].startswith("Red")]
    blue_team_ids = [team["teamNumber"] for team in match.get("teams", []) if team["station"].startswith("Blue")]
    red_actual_score = match.get("scoreRedFinal", 0)
    blue_actual_score = match.get("scoreBlueFinal", 0)

    # Update EPA scores
    update_epa(red_team_ids, blue_team_ids, red_actual_score, blue_actual_score, k_factor, margin)

def calculate_win_probability(red_epa_total, blue_epa_total):
    """
    Calculate the win probability for the Red and Blue alliances based on their added EPA difference
    """
    d = blue_epa_total - red_epa_total  # Difference in EPA ratings
    blue_win_prob = 1 / (1 + 10 ** (d / 400))
    red_win_prob = 1 - blue_win_prob  # Complement of Blue's probability

    return {
        "red_win_prob": red_win_prob,
        "blue_win_prob": blue_win_prob
    }

def predict_match_result(red_team1, red_team2, blue_team1, blue_team2):
    """
    Predict the result of a match between two alliances based on their EPA values.
    """
    # Fetch the EPA for each team
    red_epa1 = epa_scores.get(red_team1, DEFAULT_EPA)
    red_epa2 = epa_scores.get(red_team2, DEFAULT_EPA)
    blue_epa1 = epa_scores.get(blue_team1, DEFAULT_EPA)
    blue_epa2 = epa_scores.get(blue_team2, DEFAULT_EPA)

    # Total EPA for each alliance
    total_red_epa = red_epa1 + red_epa2
    total_blue_epa = blue_epa1 + blue_epa2

    # Predicted score margin
    predicted_margin = total_red_epa - total_blue_epa

    # Predicted scores
    predicted_red_score = total_red_epa
    predicted_blue_score = total_blue_epa

    # Calculate win probabilities
    win_probabilities = calculate_win_probability(total_red_epa, total_blue_epa)

    # Determine the winner
    winner = "Red Alliance" if predicted_margin > 0 else "Blue Alliance"

    return {
        "predicted_red_score": predicted_red_score,
        "predicted_blue_score": predicted_blue_score,
        "predicted_margin": predicted_margin,
        "red_win_prob": win_probabilities["red_win_prob"],
        "blue_win_prob": win_probabilities["blue_win_prob"],
        "winner": winner,
    }


def update_dataframe():
    """Update the global DataFrame with the latest EPA scores."""
    global epa_dataframe
    epa_dataframe = pd.DataFrame(
        [{"team_id": team, "epa": epa} for team, epa in epa_scores.items()]
    )

def show_top_teams(n):
    """
    Display the top N teams based on their EPA scores.
    """
    global epa_dataframe

    # Sort the DataFrame by EPA in descending order
    top_teams = epa_dataframe.sort_values(by="epa", ascending=False).head(n)

    # Display the top teams
    print(f"\nTop {n} Teams by EPA:")
    print(top_teams.to_string(index=False))


def main():
    # Generate Authorization Header
    encoded_token = encode_authorization(USERNAME, AUTHORIZATION_KEY)
    headers = {"Authorization": f"Basic {encoded_token}"}

    # List of event codes
    event_codes = ["MXCMQ2", "MXCAQ", "MXMEQ", "MXTOQ", "MXZAQ", "MXCMQ1", "MXMOQ"]  # Replace with actual event codes

    # Process all events
    for event_code in event_codes:
        # Fetch matches for the event
        matches = fetch_matches(event_code, headers)

        # Dynamically calculate DEFAULT_EPA
        global DEFAULT_EPA
        DEFAULT_EPA = calculate_default_epa(matches)
        print(f"Default EPA for {event_code}: {DEFAULT_EPA}")

        # Process matches in chronological order
        for match_number, match in enumerate(sorted(matches, key=lambda m: m.get("actualStartTime", "")), start=1):
            process_match(match, match_number)

    # Update the DataFrame with EPA scores
    update_dataframe()

    # Display the EPA DataFrame
    print("\nFinal EPA Scores (DataFrame):")
    print(epa_dataframe)

    # Show the top 10 teams
    show_top_teams(10)

    # Example: Predict a match result
    blue1 = int(input("Enter the Blue Alliance Team 1: "))
    blue2 = int(input("Enter the Blue Alliance Team 2: "))
    red1 = int(input("Enter the Red Alliance Team 1: "))
    red2 = int(input("Enter the Red Alliance Team 2: "))

    prediction = predict_match_result(red1, red2, blue1, blue2)
    print("\nMatch Prediction:")

    print(f"Predicted Red Score: {prediction['predicted_blue_score']:.2f}")
    print(f"Predicted Blue Score: {prediction['predicted_red_score']:.2f}")
    print(f"Red Win Probability: {prediction['red_win_prob']:.2%}")
    print(f"Blue Win Probability: {prediction['blue_win_prob']:.2%}")
    print(f"Predicted Winner: {prediction['winner']}")

if __name__ == "__main__":
    main()