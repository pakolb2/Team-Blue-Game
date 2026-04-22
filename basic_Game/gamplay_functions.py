### Game Rules traditional swiss game: Jass
import random as rd
import pandas as pd
import numpy as np


def distribute_cards(players: list, cards: list) -> dict:
    """This function should take the list of Player objects and the list of Card objects and return a dictionary with Player objects as keys and lists of Card objects as values, representing the cards each player has been dealt.

    Args: 
        players (list): A list of Player objects representing the players in the game.
        cards (list): A list of Card objects representing the deck of cards used in the game.
    
    Returns: 
        A dictionary with Player objects as keys and lists of Card objects as values, representing the cards each player has been dealt."""
    
    # Implement card distribution logic here, ensuring that each player gets 9 cards and that the distribution is random.
    # You can use random.shuffle to shuffle the cards before distributing them to players.
    rd.shuffle(cards)
    card_distribution = {player: cards[i*9:(i+1)*9] for i, player in enumerate([player for team in players.values() for player in team])}
    print("Cards distributed to players:", card_distribution)
    return card_distribution 


def sort(card_distribution: dict) -> dict:
    """This function should take the dictionary of players and their cards and return a new dictionary with the cards sorted according to the game rules.

    Args: 
        card_distribution (dict): A dictionary with Player objects as keys and lists of Card objects as values, representing the cards each player has been dealt.
    
    Returns: 
        A new dictionary with Player objects as keys and lists of Card objects as values, representing the cards each player has been dealt, but sorted according to the game rules."""
    
    # Implement sorting logic here based on the game rules. You can define a custom sorting key if needed.
    # For example, you might want to sort by suit first and then by rank within each suit.
    trump_suit = get_trump_suit()  # This function should return the current trump suit for the game, you can define this function based on your game logic.
    sorted_card_distribution = 
    return sorted_card_distribution

def get_trump_suit() -> str:
    """This function should return the current trump suit for the game.

    Args: 
        None 
    Returns: 
        A string representing the current trump suit for the game."""
    # Implement logic to determine the current trump suit based on your game rules. This could be random or based on player input.
    suits = ["rose", "schilte", "eichel", "schelle"]
    while True:
        False
        trump_suit = str(input("Which suit is trump?\n" + "1: rose\n" + "2: schilte\n" + "3: eichel\n" + "4: schelle: "))
        if trump_suit == "1":
            trump_suit = "rose"
        elif trump_suit == "2":
            trump_suit = "schilte"
        elif trump_suit == "3":
            trump_suit = "eichel"
        elif trump_suit == "4":
            trump_suit = "schelle"
        else: 
            print("Invalid input. Please enter a number between 1 and 4.")
            True
    print("Current trump suit:", trump_suit)
    return trump_suit


if __name__ == "__main__":
    
    print("This module is not meant to be run directly.")


