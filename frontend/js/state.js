/**
 * SkyGuard — Central State Management
 * Discipline: ПІС 2026 | Group: ОІ-33 | Team: corelogic
 * Module: js/state.js
 */

window.SkyGuard = window.SkyGuard || {};

SkyGuard.State = {
  // Current user role in system (CITIZEN, MANAGER, OPERATOR, AUDITOR)
  role: "CITIZEN",

  // Data Governance consent level (true = L2 granted GPS & Crowdsource, false = L1 PUBLIC only)
  consent: true,

  // User coordinates (defaults to Rynok Square until GPS locates)
  userLocation: { ...SkyGuard.Config.DEFAULT_USER_LOCATION },

  // Filters
  activeFilter: "ALL",         // ALL | OPEN | LIMITED | CLOSED
  activeFeatures: new Set(),   // wheelchair, generator, starlink, water
  searchQuery: "",             // string for text search

  // Selected item
  selectedShelterId: null,

  // Security & Audit state
  tampered: false,

  // Air raid alert mode
  alarmActive: false,

  // DQ-3 Quorum counters: shelterId -> witness count (0..3)
  quorumCounts: {},

  // Active navigation route polyline (Leaflet layer)
  routeLine: null,

  // Dynamic list of shelters
  shelters: [],

  // Broadcast channel for instant multi-tab sync (DSNS <-> Citizen)
  channel: null,

  // Geofence Presence Check-in (current shelter user is physically inside)
  checkedInShelterId: null,

  // Initialize state with default data and load any active overrides
  init() {
    this.shelters = JSON.parse(JSON.stringify(SkyGuard.Config.DEFAULT_SHELTERS));
    try {
      const saved = localStorage.getItem("skyguard_shelter_statuses");
      if (saved) {
        const map = JSON.parse(saved);
        this.shelters.forEach(s => {
          if (map[s.id]) {
            s.status = map[s.id].status;
            s.confirmed_at = map[s.id].confirmed_at;
          }
        });
      }
    } catch (e) {}

    this.shelters.forEach(s => {
      this.quorumCounts[s.id] = (s.status === "LIMITED" ? 2 : 1);
    });

    this.initSync();
  },

  initSync() {
    try {
      if (typeof BroadcastChannel !== "undefined") {
        this.channel = new BroadcastChannel("skyguard_sync");
        this.channel.onmessage = (event) => {
          if (event.data && event.data.type === "shelter_updated") {
            const { shelterId, status, confirmed_at } = event.data;
            const s = this.getShelterById(shelterId);
            if (s) {
              s.status = status;
              if (confirmed_at) s.confirmed_at = confirmed_at;
              SkyGuard.Map.renderShelters();
              SkyGuard.UI.updateStats();
              if (this.selectedShelterId === shelterId) {
                SkyGuard.UI.openShelterDetails(shelterId);
              }
              const statusName = status === "OPEN" ? "ВІДЧИНЕНО" : "ЗАЧИНЕНО";
              SkyGuard.UI.showToast(`🚨 Оновлення ДСНС: ${s.name} → ${statusName}!`, status === "OPEN" ? "success" : "warning");
            }
          }
        };
      }
    } catch (e) {}

    window.addEventListener("storage", (e) => {
      if (e.key === "skyguard_shelter_statuses" && e.newValue) {
        try {
          const map = JSON.parse(e.newValue);
          let changed = false;
          Object.keys(map).forEach(id => {
            const s = this.getShelterById(id);
            if (s && s.status !== map[id].status) {
              s.status = map[id].status;
              s.confirmed_at = map[id].confirmed_at || s.confirmed_at;
              changed = true;
            }
          });
          if (changed) {
            SkyGuard.Map.renderShelters();
            SkyGuard.UI.updateStats();
            if (this.selectedShelterId) {
              SkyGuard.UI.openShelterDetails(this.selectedShelterId);
            }
          }
        } catch (err) {}
      }
    });
  },

  persistShelters() {
    try {
      const map = {};
      this.shelters.forEach(s => {
        map[s.id] = { status: s.status, confirmed_at: s.confirmed_at };
      });
      localStorage.setItem("skyguard_shelter_statuses", JSON.stringify(map));
    } catch (e) {}
  },

  broadcastShelterUpdate(shelterId, status, confirmed_at) {
    this.persistShelters();
    if (this.channel) {
      try {
        this.channel.postMessage({
          type: "shelter_updated",
          shelterId,
          status,
          confirmed_at
        });
      } catch (e) {}
    }
  },

  // State mutators
  getShelterById(id) {
    return this.shelters.find(s => s.id === id);
  },

  setRole(newRole) {
    this.role = newRole;
  },

  setConsent(granted) {
    this.consent = granted;
  },

  setUserLocation(lat, lon, name = "Визначено через GPS") {
    this.userLocation = { lat, lon, name };
  },

  setSelectedShelter(id) {
    this.selectedShelterId = id;
  },

  setAlarmActive(active) {
    this.alarmActive = active;
  }
};
