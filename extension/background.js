/**
 * SubLogger - Background Service Worker
 * 
 * Manages WebSocket connection to the Python backend.
 * Receives subtitle messages from content scripts and forwards them.
 * Auto-reconnects on disconnect.
 */

// ── Configuration ──────────────────────────────────────────────────
const DEFAULT_SERVER_URL = "ws://localhost:8765";
const RECONNECT_INTERVAL_MS = 3000;
const MAX_RECONNECT_ATTEMPTS = 50;

// ── State ──────────────────────────────────────────────────────────
let ws = null;
let serverUrl = DEFAULT_SERVER_URL;
let connected = false;
let reconnectAttempts = 0;
let reconnectTimer = null;
let totalSent = 0;
let totalAcked = 0;

// ── WebSocket Management ───────────────────────────────────────────
function connect() {
  if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) {
    return;
  }

  try {
    ws = new WebSocket(serverUrl);

    ws.onopen = () => {
      connected = true;
      reconnectAttempts = 0;
      console.log(`[SubLogger] Connected to backend: ${serverUrl}`);
      updateBadge("ON", "#4CAF50");
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "ack") {
          totalAcked++;
        }
      } catch (e) {
        // Ignore non-JSON messages
      }
    };

    ws.onclose = () => {
      connected = false;
      console.log("[SubLogger] Disconnected from backend");
      updateBadge("OFF", "#F44336");
      scheduleReconnect();
    };

    ws.onerror = (error) => {
      connected = false;
      console.log("[SubLogger] WebSocket error");
      updateBadge("ERR", "#FF9800");
    };

  } catch (e) {
    console.error("[SubLogger] Failed to create WebSocket:", e);
    connected = false;
    updateBadge("ERR", "#FF9800");
    scheduleReconnect();
  }
}

function scheduleReconnect() {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
    console.log("[SubLogger] Max reconnect attempts reached");
    updateBadge("X", "#9E9E9E");
    return;
  }

  reconnectAttempts++;
  const delay = Math.min(RECONNECT_INTERVAL_MS * reconnectAttempts, 30000);
  reconnectTimer = setTimeout(connect, delay);
}

function disconnect() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (ws) {
    ws.close();
    ws = null;
  }
  connected = false;
  updateBadge("OFF", "#9E9E9E");
}

function sendToBackend(data) {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    // Queue or drop - for MVP we just attempt to connect
    if (!connected) connect();
    return false;
  }

  try {
    ws.send(JSON.stringify(data));
    totalSent++;
    return true;
  } catch (e) {
    console.error("[SubLogger] Send failed:", e);
    return false;
  }
}

// ── Badge Management ───────────────────────────────────────────────
function updateBadge(text, color) {
  try {
    chrome.action.setBadgeText({ text });
    chrome.action.setBadgeBackgroundColor({ color });
  } catch (e) {
    // May fail during service worker startup
  }
}

// ── Message Handling ───────────────────────────────────────────────
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "subtitle") {
    // Forward subtitle data to backend
    const sent = sendToBackend({
      text: message.text,
      timestamp: message.timestamp,
      url: message.url,
    });
    sendResponse({ sent, connected });
    return true;
  }

  if (message.type === "getStatus") {
    sendResponse({
      connected,
      serverUrl,
      totalSent,
      totalAcked,
      reconnectAttempts,
    });
    return true;
  }

  if (message.type === "setServerUrl") {
    serverUrl = message.url || DEFAULT_SERVER_URL;
    chrome.storage.local.set({ serverUrl });
    disconnect();
    connect();
    sendResponse({ serverUrl, connected: false });
    return true;
  }

  if (message.type === "reconnect") {
    reconnectAttempts = 0;
    disconnect();
    connect();
    sendResponse({ reconnecting: true });
    return true;
  }
});

// ── Initialization ─────────────────────────────────────────────────
chrome.storage.local.get(["serverUrl"], (result) => {
  if (result.serverUrl) {
    serverUrl = result.serverUrl;
  }
  connect();
});

console.log("[SubLogger] Background service worker started");
