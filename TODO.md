Running document in which things that still need to be done can be added, for an overview of possible changes

## List of things fixed
- More things added to the .gitignore, so all pycache folders should now be in there
- At your turn the light now lights up, it was a small change in the RenderSeat function in game.js: It would not update your own indicator 

## List of UI changes
- There is now a timer for each move in server/shared/timing.py Maybe a popup indicating that the round ended or with a timing line or something would help
- It probably also helps to add a time limit per turn, as now I could theoretically go infinitely long
- We could add a footer that displays our names and team name
- auto sort button ()
- log adjust names
- refresh game --> update status 
- Bots can be renamed to easy and difficult
- How many rounds do we play?


## List of game related changes
- have a card comparison (french swiss)
- automatic replacing people with bots if room left or too long inactive
- rejoining the game (same id) --> someone else can join the game in that name
- check game rules --> points dont add up to 157 ==> Pytests related to game rules fail, so yes there is an error
- french game cars in tutorial instead swiss adjust

## List of repository changes
- update docstring / cleanup repository