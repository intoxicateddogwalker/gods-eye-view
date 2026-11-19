/**
 * Seer panel for the God's Eye View fork.
 * ========================================
 * Vanilla JS, no framework — matches the fork (vanilla JS + CesiumJS + Vite).
 *
 * What it does: fetches the swarm's live predictions + mini registry from
 * the repo itself (raw.githubusercontent.com serves open CORS, the same
 * trick the flights feed uses) and renders a "Seer" panel inside the
 * globe UI: home region first (Tulsa & Sapulpa), then the swarm, then
 * the predictions with confidence bars and the accuracy meter.
 *
 * It does NOT run any model. The models live on the Hugging Face Space;
 * this panel only displays what the swarm already predicted. The Space
 * URL is linked, not embedded, so the panel works even when the Space
 * is asleep.
 *
 * Integration: see INTEGRATION.md in the same folder.
 */
(function () {
  "use strict";

  var RAW_BASE = "https://raw.githubusercontent.com/intoxicateddogwalker/gods-eye-view/main";
  var PREDICTIONS_URL = RAW_BASE + "/data/seer/predictions.json";
  var MINIS_URL = RAW_BASE + "/data/seer/minis.json";
  var SPACE_URL = "https://huggingface.co/spaces/intoxicateddogwalker/seer-gods-eye-view";
  var REFRESH_MS = 5 * 60 * 1000; // same cadence as the flights feed

  // Home minis, in home order (matches swarm.py HOME_MINI_IDS).
  var HOME_MINI_IDS = [
    "cam-tulsa-downtown", "cam-tulsa-highway", "cam-tulsa-airport",
    "cam-tulsa-waterfront",
    "cam-sapulpa-downtown", "cam-sapulpa-highway", "cam-sapulpa-airport",
    "cam-sapulpa-waterfront",
    "region-tulsa", "region-sapulpa",
    "quake-oklahoma-aftershock", "fire-oklahoma",
    "weather-oklahoma", "flights-tul-hub"
  ];

  function fetchJson(url) {
    return fetch(url, { cache: "no-store" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status + " for " + url);
      return r.json();
    });
  }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function confBar(conf) {
    var pct = Math.round((conf || 0) * 100);
    var cls = pct >= 70 ? "seer-conf-high" : pct >= 50 ? "seer-conf-mid" : "seer-conf-low";
    return '<div class="seer-conf"><div class="seer-conf-fill ' + cls +
      '" style="width:' + pct + '%"></div><span>' + pct + '%</span></div>';
  }

  function statusChip(status) {
    var cls = status === "hit" ? "seer-hit" : status === "miss" ? "seer-miss" : "seer-open";
    return '<span class="seer-chip ' + cls + '">' + esc(status || "open") + "</span>";
  }

  function renderHome(minis) {
    var byId = {};
    minis.forEach(function (m) { byId[m.id] = m; });
    var rows = HOME_MINI_IDS.map(function (id) {
      var m = byId[id];
      if (!m) return "";
      var acc = m.accuracy == null ? "—" : Math.round(m.accuracy * 100) + "%";
      var flag = (m.predictions_made + m.hits + m.misses) >= 10 && (m.accuracy || 0) < 0.4
        ? ' <span class="seer-flag">RETRAIN</span>' : "";
      return "<tr><td>" + esc(m.id) + "</td><td>" + esc(m.kind) + "</td>" +
        "<td>" + esc(m.status) + "</td><td>" + acc + "</td>" +
        "<td>" + (m.trust != null ? m.trust : "—") + "</td><td>" + flag + "</td></tr>";
    }).join("");
    return "<h3>🏠 Home — Tulsa &amp; Sapulpa</h3>" +
      '<table class="seer-table"><thead><tr><th>mini</th><th>kind</th>' +
      "<th>status</th><th>accuracy</th><th>trust</th><th></th></tr></thead>" +
      "<tbody>" + rows + "</tbody></table>";
  }

  function renderPredictions(data) {
    var preds = (data.predictions || []).filter(function (p) { return p.status === "open"; });
    if (!preds.length) {
      return "<p class='seer-empty'>No open predictions right now — the swarm is quiet.</p>";
    }
    var items = preds.map(function (p) {
      var region = (p.region && p.region.name) || "global";
      var minis = (p.mini_ids || []).slice(0, 3).join(", ");
      return '<div class="seer-pred">' +
        '<div class="seer-pred-head"><strong>' + esc(p.title) + "</strong> " +
        statusChip(p.status) + "</div>" +
        '<div class="seer-pred-body">' + esc(p.prediction) + "</div>" +
        '<div class="seer-pred-meta">' + esc(region) + " · " +
        esc(p.kind) + (minis ? " · minis: " + esc(minis) : "") + "</div>" +
        confBar(p.confidence) +
        "</div>";
    }).join("");
    return "<h3>🔮 What Seer predicts next</h3>" + items;
  }

  function renderScoreboard(data) {
    var sb = data.scoreboard || {};
    var total = sb.total_scored || 0;
    var acc = sb.accuracy;
    var accText = (typeof acc === "number") ? Math.round(acc * 100) + "%" : "—";
    return '<div class="seer-meter"><div class="seer-meter-num">' + accText + "</div>" +
      '<div class="seer-meter-label">swarm accuracy · ' + total + " scored (" +
      (sb.hits || 0) + " right, " + (sb.misses || 0) + " wrong)</div></div>";
  }

  function renderSwarm(minis) {
    var active = minis.filter(function (m) { return m.status === "active"; }).length;
    var scored = minis.filter(function (m) { return m.accuracy != null; });
    var mean = scored.length
      ? Math.round(scored.reduce(function (a, m) { return a + m.accuracy; }, 0) / scored.length * 100) + "%"
      : "—";
    var kinds = {};
    minis.forEach(function (m) { kinds[m.kind] = (kinds[m.kind] || 0) + 1; });
    var kindText = Object.keys(kinds).sort().map(function (k) {
      return kinds[k] + " " + k;
    }).join(" · ");
    return "<h3>👁️ The swarm</h3>" +
      "<p><strong>" + active + "</strong> of <strong>" + minis.length +
      "</strong> minis active · mean mini accuracy " + mean + "<br>" +
      "<span class='seer-dim'>" + esc(kindText) + "</span></p>";
  }

  function renderAll(root, data, minis) {
    root.innerHTML =
      '<div class="seer-panel">' +
      '<div class="seer-head"><span class="seer-eye">👁️</span> SEER ' +
      '<span class="seer-dim">· 500 mini-AIs · coordinator brain on Hugging Face</span>' +
      '<a class="seer-link" href="' + SPACE_URL + '" target="_blank" rel="noopener">Open Seer Space ↗</a></div>' +
      renderScoreboard(data) +
      renderHome(minis) +
      renderPredictions(data) +
      renderSwarm(minis) +
      '<div class="seer-foot seer-dim">Predictions refresh every 5 min from the swarm. ' +
      "Seer watches feed data + camera metadata — not raw video, not social media. " +
      "Generated " + esc(data.generated_at || "—") + ".</div>" +
      "</div>";
  }

  function renderError(root, err) {
    root.innerHTML =
      '<div class="seer-panel"><div class="seer-head">👁️ SEER</div>' +
      '<p class="seer-empty">Seer data unavailable right now (' + esc(err.message) + "). " +
      "The swarm writes predictions every 15 minutes — try again shortly.</p></div>";
  }

  function load(root) {
    Promise.all([
      fetchJson(PREDICTIONS_URL).catch(function () { return null; }),
      fetchJson(MINIS_URL).catch(function () { return null; })
    ]).then(function (results) {
      var data = results[0] || { predictions: [], scoreboard: {} };
      var minis = (results[1] && results[1].minis) || [];
      if (!minis.length) {
        // Panel still works without the registry: show predictions only.
        root.innerHTML =
          '<div class="seer-panel"><div class="seer-head">👁️ SEER</div>' +
          renderScoreboard(data) + renderPredictions(data) +
          '<div class="seer-foot seer-dim">Mini registry loading…</div></div>';
        return;
      }
      renderAll(root, data, minis);
    }).catch(function (err) { renderError(root, err); });
  }

  window.SeerPanel = {
    init: function (containerId) {
      var root = document.getElementById(containerId);
      if (!root) return false;
      load(root);
      setInterval(function () { load(root); }, REFRESH_MS);
      return true;
    },
    refresh: function (containerId) {
      var root = document.getElementById(containerId);
      if (root) load(root);
    }
  };
})();
