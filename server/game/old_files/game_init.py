import random as rd
import pandas as pd
import numpy as np



class Team:
    """A class representing a team in the game.
    Attributes:
        name (str): The name of the team.
        players (list): A list of Player objects representing the players in the team.
    Methods:
        __init__(self, name: str, players: list): Initializes a Team object with a name and a list of Player objects.
        __repr__(self): Returns a string representation of the Team object."""          

    def __init__(self, name: str, players: list):
        """Initialize a Team object with a name and a list of Player objects.
        Args:
            name (str): The name of the team.
            players (list): A list of Player objects representing the players in the team.
        Returns:
            None"""
        self.name = name
        self.players = players
    
    def __repr__(self):
        """Return a string representation of the Team object.
        Args:
            None
        Returns:
            A string representation of the Team object in the format "Team name: player1, player2" (e.g., "Team 1: Alice, Bob")."""

        return f"{self.name}: {', '.join([player.name for player in self.players])}"
    
    

    def initialize_players() -> list:
        """This function should create and return a list of Player objects based on user input.
        Args: 
            None
        Returns: 
            A list of Player objects representing the players in the game."""
        

        players = []
        while len(players) < 4:
            name = input(str(f"Enter name for Player {len(players)+1}: ")).capitalize()
            if name in players:
                print("Name already taken. Please choose a different name.")
            else:
                players.append(name)  # Replace with Player(name) when you have a Player class defined.
        print ("Players initialized:", players)
        return list(players)


    def group_players_into_teams(players: list) -> dict:
        """This function should take a list of Player objects and return a dictionary with team names as keys and lists of Player objects as values.
        Args: 
            players (list): A list of Player objects representing the players in the game.
        Returns: 
            A dictionary with team names as keys and lists of Player objects as values, representing the teams in the game."""
        
        random_teams = input("Do you want to randomize teams? (y/n): ").lower()
        if random_teams == "y":
            rd.shuffle(players)
        elif random_teams == "n":
            team1 = input(f"Who plays with {players[0]}? \n"
                        "1:   " + players[1] + " \n"
                        "2:   " + players[2] + " \n"
                        "3:   " + players[3] + " \n"
                        "Enter the number corresponding to the player: ")
            if team1 == "1":
                pass
            elif team1 == "2":
                players[1], players[2] = players[2], players[1]
            elif team1 == "3":
                players[1], players[3] = players[3], players[1]
            else:
                print("Invalid input. Randomizing teams.")
                rd.shuffle(players)
        teams = {"Team 1": [players[0], players[1]], "Team 2": [players[2], players[3]]}
        print("Teams formed:", teams)
        return teams

class Card_functions:
        """A class representing a single card in the game.
    Attributes:
        suit (str): The suit of the card (e.g., "rose", "schilte", "eichel", "schelle").
        value (str): The value of the card (e.g., "6", "7", "8", "9", "10", "Under", "Ober", "König", "Ass").
    Methods:
        __init__(self, suit: str, value: str): Initializes a Card object with a suit and value.
        __repr__(self): Returns a string representation of the Card object."""          

    def __init__(self, suit: str, value: str):
        """Initialize a Card object with a suit and value.
        Args:
            suit (str): The suit of the card (e.g., "rose", "schilte", "eichel", "schelle").
            value (str): The value of the card (e.g., "6", "7", "8", "9", "10", "Under", "Ober", "König", "Ass").
        Returns:
            None"""
        self.suit = suit
        self.value = value
    
    def __repr__(self):
        """Return a string representation of the Card object.
        Args:
            None
        Returns:
            A string representation of the Card object in the format "suit value" (e.g., "rose 6", "schilte Under").
        """

        return f"{self.suit} {self.value}"


    def initialize_cards() -> list:
        """This function should create and return a list of Card objects representing the deck of cards used in the game.
        Args: 
            None
        Returns: 
            A list of Card objects representing the deck of cards used in the game."""

        suits = ["rose", "schilte", "eichel", "schelle"]
        values = ["6", "7", "8", "9", "10", "Under", "Ober", "König", "Ass"]
        cards_list = [Card(suit, str(value)) for suit in suits for value in values]
        return cards_list


    def sample_initialization() -> list:
        """This function is a sample initialization function to demonstrate how to use the above functions together. You can modify this function as needed to fit your game logic.
        Args: 
            None
        Returns:
            players (list): A list of Player objects representing the players in the game.
            teams (dict): A dictionary with team names as keys and lists of Player objects as values, representing the teams in the game."""

        players = ["Alice", "Bob", "Charlie", "David"]
        teams = {"Team 1": [players[0], players[2]], "Team 2": [players[1], players[3]]}
        return players, teams