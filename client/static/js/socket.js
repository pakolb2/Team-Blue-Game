// WebSocket client — connects to the FastAPI backend
const ws = new WebSocket(`ws://${location.host}/ws`);

ws.onopen = () => console.log("Connected to server");
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  handleEvent(data);
};

function sendEvent(type, payload = {}) {
  ws.send(JSON.stringify({ type, ...payload }));
}
