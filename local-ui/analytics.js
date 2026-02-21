// Lightweight analytics for Railway Job Search UI (local-ui).
// Same API as analytics-lab/assets/js/analytics.js — sends events to your Worker endpoint.
// Usage: load this script, then initAnalyticsTracking({ site: 'railway-ui', baseEvent: 'core', endpoint: 'https://events.colab.indevs.in/api/events' });

(function () {
  var DEFAULT_ENDPOINT = "https://events.colab.indevs.in/api/events";
  var SESSION_KEY = "analytics_railway_ui_session_id";
  var DEBUG_KEY = "analytics_debug";

  function isDebug() {
    try {
      if (typeof window !== "undefined" && window.location && window.location.search) {
        if (window.location.search.indexOf("analytics_debug=1") !== -1) return true;
      }
      if (typeof localStorage !== "undefined" && localStorage.getItem(DEBUG_KEY) === "1") return true;
    } catch (e) {}
    return false;
  }

  function generateSessionId() {
    if (window.crypto && crypto.randomUUID) {
      return crypto.randomUUID();
    }
    return "s-" + Math.random().toString(36).slice(2) + Date.now().toString(36);
  }

  function getSessionId() {
    var existing = null;
    try {
      existing = localStorage.getItem(SESSION_KEY);
    } catch (e) {}
    if (existing) return existing;
    var id = generateSessionId();
    try {
      localStorage.setItem(SESSION_KEY, id);
    } catch (e) {}
    return id;
  }

  function getFingerprintTraits() {
    var nav = (typeof navigator !== "undefined" && navigator) || {};
    var scr = (typeof window !== "undefined" && window.screen) || {};
    var intlOpts = {};
    try {
      if (window.Intl && Intl.DateTimeFormat) {
        intlOpts = Intl.DateTimeFormat().resolvedOptions() || {};
      }
    } catch (e) {}
    var pointerCoarse = false;
    try {
      if (window.matchMedia) {
        pointerCoarse = window.matchMedia("(pointer: coarse)").matches;
      }
    } catch (e) {}
    return {
      hardwareConcurrency: nav.hardwareConcurrency || null,
      deviceMemory: nav.deviceMemory || null,
      colorDepth: scr.colorDepth || null,
      maxTouchPoints: typeof nav.maxTouchPoints === "number" ? nav.maxTouchPoints : null,
      timeZone: intlOpts.timeZone || null,
      languages: nav.languages || (nav.language ? [nav.language] : null),
      pointerCoarse: pointerCoarse,
      platform: nav.platform || null,
      vendor: nav.vendor || null,
      userAgent: nav.userAgent || null
    };
  }

  function buildBasePayload(config, eventName) {
    return {
      site: config.site || "railway-ui",
      event: eventName,
      sessionId: config.sessionId,
      ts: new Date().toISOString(),
      path: window.location.pathname + window.location.search,
      referrer: document.referrer || null,
      userAgent: navigator.userAgent || null,
      language: navigator.language || null,
      platform: navigator.platform || null,
      device: {
        width: window.innerWidth || null,
        height: window.innerHeight || null,
        screenWidth: window.screen && window.screen.width,
        screenHeight: window.screen && window.screen.height,
        pixelRatio: window.devicePixelRatio || 1,
        touch: "ontouchstart" in window || navigator.maxTouchPoints > 0
      },
      fpTraits: getFingerprintTraits()
    };
  }

  function sendAnalyticsEvent(config, eventName, extra) {
    var debug = isDebug();
    if (!config.endpoint) {
      if (debug) console.warn("[Analytics] No endpoint configured, event not sent:", eventName);
      return;
    }
    if (debug) console.log("[Analytics] Sending:", eventName, "→", config.endpoint);

    var payload = buildBasePayload(config, eventName);
    if (extra && typeof extra === "object") {
      for (var k in extra) {
        if (Object.prototype.hasOwnProperty.call(extra, k)) payload[k] = extra[k];
      }
    }
    var body = JSON.stringify(payload);

    var baseUrl = config.endpoint;
    try {
      var urlObj = new URL(config.endpoint);
      baseUrl = urlObj.origin;
    } catch (e) {}
    var fallbackPaths = ["/api/events", "/api/track", "/events", "/track", "/ping", "/log"];
    var endpointsToTry = [config.endpoint];
    if (baseUrl !== config.endpoint) {
      for (var i = 0; i < fallbackPaths.length; i++) {
        endpointsToTry.push(baseUrl + fallbackPaths[i]);
      }
    }

    var beaconSent = false;
    if (navigator.sendBeacon) {
      try {
        for (var b = 0; b < endpointsToTry.length; b++) {
          var blob = new Blob([body], { type: "application/json" });
          if (navigator.sendBeacon(endpointsToTry[b], blob)) {
            beaconSent = true;
            if (debug) console.log("[Analytics] Sent via sendBeacon:", endpointsToTry[b]);
            break;
          }
        }
      } catch (e) {}
    }

    if (!beaconSent) {
      function tryEndpoint(index) {
        if (index >= endpointsToTry.length) return;
        var endpoint = endpointsToTry[index];
        var timeoutId = setTimeout(function () { tryEndpoint(index + 1); }, 2000);
        fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: body,
          keepalive: true,
          credentials: "omit"
        })
          .then(function (response) {
            clearTimeout(timeoutId);
            if (!response.ok) tryEndpoint(index + 1);
          })
          .catch(function () {
            clearTimeout(timeoutId);
            tryEndpoint(index + 1);
          });
      }
      try { tryEndpoint(0); } catch (e) {}
    }
  }

  window.initAnalyticsTracking = function initAnalyticsTracking(options) {
    try {
      var pageLoadMs = Date.now();
      var sessionId = getSessionId();
      var cfg = {
        site: (options && options.site) || "railway-ui",
        baseEvent: (options && options.baseEvent) || "page",
        endpoint: (options && options.endpoint) || DEFAULT_ENDPOINT || null,
        sessionId: sessionId
      };
      if (!cfg.endpoint) return;
      if (isDebug()) console.log("[Analytics] Init:", cfg.baseEvent, "site:", cfg.site);

      sendAnalyticsEvent(cfg, cfg.baseEvent + "_visit");

      window.addEventListener("beforeunload", function () {
        var durationMs = Date.now() - pageLoadMs;
        if (durationMs >= 0 && durationMs < 24 * 60 * 60 * 1000) {
          sendAnalyticsEvent(cfg, cfg.baseEvent + "_unload", { durationMs: durationMs });
        }
      });
    } catch (e) {}
  };
})();
