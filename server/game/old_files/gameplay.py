# Game Play (4 players, 2 teams, 36 cards, 9 cards per player, only trump suit) 
import random as rd
import pandas as pd
import numpy as np
from new_setup.jass.server.game.old_files.game_init import *  # Importing all functions from game_init.py, you can specify which functions to import if you want to avoid namespace pollution.
from new_setup.jass.server.game.old_files.gamplay_functions import *  # Importing all functions from gamplay_functions.py, you can specify which functions to import if you want to avoid namespace pollution.




def main():
    print("Welcome to the Jass Game!")

    # Initialize players and teams
    if input ("Do you want to initialize players and teams? (y/n): ").lower() == "y":
        players = initialize_players() # This function should create and return a list of Player objects based on user input.
        teams = group_players_into_teams(players) # This function should take a list of Player objects and return a dictionary with team names as keys and lists of Player objects as values.
    else:
        print("Skipping player and team initialization. Using default players and teams.")
        players = ["Alice", "Bob", "Charlie", "David"]
        rd.shuffle(players)  # Replace with Player objects when you have a Player class defined.
        teams = {"Team 1": [players[0], players[1]], "Team 2": [players[2], players[3]]}
        print("Default teams formed:", teams)
   
    cards = initialize_cards()  # This function should create and return a list of Card objects representing the deck of cards used in the game.

    # This condition should check if the current round of the game is over, you can define this variable based on your game logic.
    card_distribution = distribute_cards(teams, cards)  # This function should take the list of Player objects and the list of Card objects and return a dictionary with Player objects as keys and lists of Card objects as values, representing the cards each player has been dealt.   
    sorted_cards = sort(card_distribution)  # This function should take the dictionary of players and their cards and return a new dictionary with the cards sorted according to the game rules.
    # Initialize game state and start the game loop
        # Implement the game loop here, calling functions from gamplay_functions.py to handle the game logic, player turns, scoring, etc.





    # 



if __name__ == "__main__":
    main()