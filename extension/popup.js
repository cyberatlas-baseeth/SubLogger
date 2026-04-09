/**
 * SubLogger - Popup Script
 * Controls the extension popup UI.
 */

document.addEventListener("DOMContentLoaded", () => {
  const statusIndicator = document.getElementById("status-indicator");
  const statusText = document.getElementById("status-text");
  const statSent = document.getElementById("stat-sent");
  const statAcked = document.getElementById("stat-acked");
  const serverUrlInput = document.getElementById("server-url");
  const btnSave = document.getElementById("btn-save");
  const btnReconnect = document.getElementById("btn-reconnect");
  const toggleEnabled = document.getElementById("toggle-enabled");

  // ── Load saved state ────────────────────────────────────────────
  chrome.storage.local.get(["serverUrl", "enabled"], (result) => {
    if (result.serverUrl) {
      serverUrlInput.value = result.serverUrl;
    }
    toggleEnabled.checked = result.enabled !== false;
  });

  // ── Update status ───────────────────────────────────────────────
  function updateStatus() {
    chrome.runtime.sendMessage({ type: "getStatus" }, (response) => {
      if (chrome.runtime.lastError || !response) return;

      if (response.connected) {
        statusIndicator.className = "status-dot connected";
        statusText.textContent = "Connected";
      } else {
        statusIndicator.className = "status-dot disconnected";
        statusText.textContent = response.reconnectAttempts > 0
          ? `Reconnecting (${response.reconnectAttempts})...`
          : "Disconnected";
      }

      statSent.textContent = response.totalSent || 0;
      statAcked.textContent = response.totalAcked || 0;

      if (response.serverUrl) {
        serverUrlInput.value = response.serverUrl;
      }
    });
  }

  // Initial update + poll
  updateStatus();
  setInterval(updateStatus, 1000);

  // ── Save URL ────────────────────────────────────────────────────
  btnSave.addEventListener("click", () => {
    const url = serverUrlInput.value.trim();
    if (!url) return;

    chrome.runtime.sendMessage({
      type: "setServerUrl",
      url: url,
    }, () => {
      btnSave.textContent = "✓";
      setTimeout(() => { btnSave.textContent = "↻"; }, 1000);
    });
  });

  // ── Reconnect ───────────────────────────────────────────────────
  btnReconnect.addEventListener("click", () => {
    chrome.runtime.sendMessage({ type: "reconnect" }, () => {
      btnReconnect.textContent = "Reconnecting...";
      setTimeout(() => {
        btnReconnect.textContent = "Reconnect";
        updateStatus();
      }, 2000);
    });
  });

  // ── Toggle detection ────────────────────────────────────────────
  toggleEnabled.addEventListener("change", () => {
    const enabled = toggleEnabled.checked;
    chrome.storage.local.set({ enabled });

    // Notify all content scripts
    chrome.tabs.query({}, (tabs) => {
      tabs.forEach((tab) => {
        chrome.tabs.sendMessage(tab.id, {
          type: "toggle",
          enabled: enabled,
        }).catch(() => {});
      });
    });
  });
});
