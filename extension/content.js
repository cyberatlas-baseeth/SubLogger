/**
 * SubLogger - Content Script
 * 
 * Detects subtitles from video players using multiple generic strategies:
 * 1. HTML5 TextTrack API (<track> elements on <video>)
 * 2. MutationObserver for dynamic subtitle containers
 * 3. Heuristic detection for overlay-style subtitles
 * 
 * No hardcoded selectors - works generically across sites.
 */

(() => {
  "use strict";

  // ── Configuration ──────────────────────────────────────────────────
  const DEBOUNCE_MS = 300;
  const CHECK_INTERVAL_MS = 2000;
  const MIN_TEXT_LENGTH = 2;
  const MAX_TEXT_LENGTH = 500;

  // ── State ──────────────────────────────────────────────────────────
  let lastSentText = "";
  let lastSendTime = 0;
  let debounceTimer = null;
  let enabled = true;
  let subtitleCount = 0;
  let observer = null;

  // ── Debounced send ─────────────────────────────────────────────────
  function sendSubtitle(text) {
    if (!enabled || !text) return;

    const cleaned = text.trim().replace(/\s+/g, " ");
    if (cleaned.length < MIN_TEXT_LENGTH || cleaned.length > MAX_TEXT_LENGTH) return;

    const now = Date.now();

    // Skip duplicate text within debounce window
    if (cleaned === lastSentText && (now - lastSendTime) < DEBOUNCE_MS * 3) return;

    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      lastSentText = cleaned;
      lastSendTime = Date.now();
      subtitleCount++;

      chrome.runtime.sendMessage({
        type: "subtitle",
        text: cleaned,
        timestamp: new Date().toISOString(),
        url: window.location.href,
        count: subtitleCount,
      });
    }, DEBOUNCE_MS);
  }

  // ── Strategy 1: HTML5 TextTrack API ────────────────────────────────
  function watchTextTracks() {
    const videos = document.querySelectorAll("video");

    videos.forEach((video) => {
      if (video._subloggerWatched) return;
      video._subloggerWatched = true;

      const tracks = video.textTracks;
      if (!tracks) return;

      for (let i = 0; i < tracks.length; i++) {
        const track = tracks[i];

        track.addEventListener("cuechange", () => {
          if (!track.activeCues || track.activeCues.length === 0) return;

          const texts = [];
          for (let j = 0; j < track.activeCues.length; j++) {
            const cue = track.activeCues[j];
            if (cue.text) {
              // Strip HTML tags from VTT cues
              const stripped = cue.text.replace(/<[^>]*>/g, "").trim();
              if (stripped) texts.push(stripped);
            }
          }

          if (texts.length > 0) {
            sendSubtitle(texts.join(" "));
          }
        });

        // Ensure track is showing
        if (track.mode === "disabled") {
          track.mode = "hidden";
        }
      }

      // Watch for new tracks being added
      video.textTracks.addEventListener("addtrack", () => {
        watchTextTracks();
      });
    });
  }

  // ── Strategy 2: MutationObserver for subtitle containers ──────────
  function isLikelySubtitleElement(el) {
    if (!el || el.nodeType !== Node.ELEMENT_NODE) return false;

    const tag = el.tagName.toLowerCase();
    // Skip non-visual elements
    if (["script", "style", "link", "meta", "head", "html", "body", "iframe"].includes(tag)) {
      return false;
    }

    // Check element attributes for subtitle hints
    const attrs = [
      el.className || "",
      el.id || "",
      el.getAttribute("role") || "",
      el.getAttribute("aria-label") || "",
      el.getAttribute("data-testid") || "",
    ].join(" ").toLowerCase();

    const subtitleKeywords = [
      "subtitle", "caption", "cue", "cc-", "closed-caption",
      "player-timedtext", "ytp-caption", "vjs-text-track",
      "plyr__captions",  "subtitle-text", "captions-text",
      "timed-text", "sub-text", "caption-window", "captions-display",
    ];

    for (const keyword of subtitleKeywords) {
      if (attrs.includes(keyword)) return true;
    }

    // Heuristic: element overlaying a video player
    if (isOverlayingVideo(el)) {
      const style = window.getComputedStyle(el);
      const position = style.position;
      if (position === "absolute" || position === "fixed") {
        // Check if it has text and looks like a subtitle
        const text = el.textContent?.trim();
        if (text && text.length >= MIN_TEXT_LENGTH && text.length <= MAX_TEXT_LENGTH) {
          const fontSize = parseFloat(style.fontSize);
          if (fontSize >= 12 && fontSize <= 72) {
            return true;
          }
        }
      }
    }

    return false;
  }

  function isOverlayingVideo(el) {
    try {
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return false;

      const videos = document.querySelectorAll("video");
      for (const video of videos) {
        const vRect = video.getBoundingClientRect();
        if (vRect.width === 0 || vRect.height === 0) continue;

        // Check if element overlaps with video
        const overlaps =
          rect.left < vRect.right &&
          rect.right > vRect.left &&
          rect.top < vRect.bottom &&
          rect.bottom > vRect.top;

        if (overlaps) return true;
      }
    } catch (e) {
      // getBoundingClientRect can fail in some contexts
    }
    return false;
  }

  function extractTextFromElement(el) {
    if (!el) return "";
    // Get text content, stripping HTML
    const text = el.textContent || el.innerText || "";
    return text.trim().replace(/\s+/g, " ");
  }

  function startMutationObserver() {
    if (observer) observer.disconnect();

    observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        // Check added nodes
        if (mutation.type === "childList") {
          for (const node of mutation.addedNodes) {
            if (node.nodeType === Node.ELEMENT_NODE) {
              if (isLikelySubtitleElement(node)) {
                const text = extractTextFromElement(node);
                if (text) sendSubtitle(text);
              }
              // Check children of added nodes
              const children = node.querySelectorAll?.("*") || [];
              for (const child of children) {
                if (isLikelySubtitleElement(child)) {
                  const text = extractTextFromElement(child);
                  if (text) sendSubtitle(text);
                }
              }
            } else if (node.nodeType === Node.TEXT_NODE) {
              const parent = node.parentElement;
              if (parent && isLikelySubtitleElement(parent)) {
                const text = node.textContent?.trim();
                if (text) sendSubtitle(text);
              }
            }
          }
        }

        // Check character data changes (text content updates)
        if (mutation.type === "characterData") {
          const parent = mutation.target.parentElement;
          if (parent && isLikelySubtitleElement(parent)) {
            const text = extractTextFromElement(parent);
            if (text) sendSubtitle(text);
          }
        }

        // Check attribute changes that might indicate subtitle visibility
        if (mutation.type === "attributes") {
          const el = mutation.target;
          if (isLikelySubtitleElement(el)) {
            const text = extractTextFromElement(el);
            if (text) sendSubtitle(text);
          }
        }
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["class", "style", "hidden", "aria-hidden"],
    });
  }

  // ── Strategy 3: Periodic scan for new video elements ──────────────
  function periodicCheck() {
    watchTextTracks();

    // Look for any new subtitle-like elements that might have been missed
    const allElements = document.querySelectorAll(
      '[class*="subtitle" i], [class*="caption" i], [class*="cue" i], ' +
      '[id*="subtitle" i], [id*="caption" i], ' +
      '[role="presentation"], [aria-live="polite"], [aria-live="assertive"]'
    );

    allElements.forEach((el) => {
      if (el._subloggerScanned) return;
      el._subloggerScanned = true;

      // Set up a mini observer for this specific element
      const miniObserver = new MutationObserver(() => {
        const text = extractTextFromElement(el);
        if (text) sendSubtitle(text);
      });

      miniObserver.observe(el, {
        childList: true,
        subtree: true,
        characterData: true,
      });
    });
  }

  // ── Initialization ─────────────────────────────────────────────────
  function init() {
    // Load enabled state
    chrome.storage.local.get(["enabled"], (result) => {
      enabled = result.enabled !== false; // default true
    });

    // Listen for enable/disable messages
    chrome.runtime.onMessage.addListener((message) => {
      if (message.type === "toggle") {
        enabled = message.enabled;
        chrome.storage.local.set({ enabled });
      }
    });

    // Start all detection strategies
    watchTextTracks();
    startMutationObserver();

    // Periodic check for dynamically loaded videos
    setInterval(periodicCheck, CHECK_INTERVAL_MS);

    console.log("[SubLogger] Content script initialized");
  }

  // Wait for DOM to be ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
