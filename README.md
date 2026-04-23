# Team-Blue-Game
651-4284-00L AI-Assisted Coding and Collaborative Project Development FS2026, 

This is the offical repository for our Project
(if you wan to test stuff f.e with git, please use the repository of the lecture! a-purrfect-story) 

to run the whole program: 

cd TEAM-BLUE-GAME
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate (can be sxipped if you dont want to create an extra env)
pip install -r server/requirements.txt
pytest                                             # 455 tests should pass
uvicorn server.main:app --reload                  # open http://localhost:8000