// Game rendering and client-side state

let gameState = null;

function handleEvent(event) {
  switch (event.type) {
    case "state_updated":
      gameState = event.state;
      render();
      break;
    case "game_over":
      showEndScreen(event.scores);
      break;
  }
}

function render() {
  // TODO: render hand, trick, scores from gameState
}

function showEndScreen(scores) {
  // TODO: display final scores
}
