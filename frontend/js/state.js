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
  consent: false,

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
            if (typeof map[s.id].occupancy === "number") {
              s.current_occupancy = map[s.id].occupancy;
            }
          }
        });
      }

      const savedConsent = localStorage.getItem("skyguard_consent");
      this.consent = (savedConsent === "granted");
    } catch (e) {
      this.consent = false;
    }

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
            const { shelterId, shelterName, status, confirmed_at, occupancy } = event.data;
            const s = this.getShelterById(shelterId, shelterName);
            if (s) {
              const oldStatus = s.status;
              const oldOccupancy = s.current_occupancy;
              s.status = status;
              if (confirmed_at) s.confirmed_at = confirmed_at;
              if (typeof occupancy === "number") s.current_occupancy = occupancy;
              SkyGuard.Map.renderShelters();
              SkyGuard.UI.updateStats();
              if (this.selectedShelterId && 
                  (String(this.selectedShelterId).toLowerCase() === String(s.id).toLowerCase() ||
                   (shelterId && String(this.selectedShelterId).toLowerCase() === String(shelterId).toLowerCase()))) {
                SkyGuard.UI.openShelterDetails(s.id);
              }
              if (oldStatus !== status) {
                const statusName = status === "OPEN" ? "ВІДЧИНЕНО" : (status === "CLOSED" ? "ЗАЧИНЕНО" : "ОБМЕЖЕНО");
                SkyGuard.UI.showToast(`🚨 Оновлення ДСНС: ${s.name} → ${statusName}!`, status === "OPEN" ? "success" : "warning");
              } else if (typeof occupancy === "number" && oldOccupancy !== occupancy) {
                SkyGuard.UI.showToast(`📍 Live GPS: Заповненість «${s.name}» оновлено (${occupancy}/${s.capacity} осіб)`, "info");
              }
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
            const item = map[id];
            const s = this.getShelterById(id, item.name);
            if (s) {
              if (s.status !== item.status) {
                s.status = item.status;
                changed = true;
              }
              if (typeof item.occupancy === "number" && s.current_occupancy !== item.occupancy) {
                s.current_occupancy = item.occupancy;
                changed = true;
              }
              if (item.confirmed_at) s.confirmed_at = item.confirmed_at;
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
        map[s.id] = { 
          status: s.status, 
          confirmed_at: s.confirmed_at,
          occupancy: s.current_occupancy,
          name: s.name
        };
      });
      localStorage.setItem("skyguard_shelter_statuses", JSON.stringify(map));
    } catch (e) {}
  },

  broadcastShelterUpdate(shelterId, status, confirmed_at, occupancy = null) {
    this.persistShelters();
    if (this.channel) {
      try {
        const s = this.getShelterById(shelterId);
        const occ = (typeof occupancy === "number" ? occupancy : (s ? s.current_occupancy : null));
        this.channel.postMessage({
          type: "shelter_updated",
          shelterId,
          shelterName: s ? s.name : null,
          status,
          confirmed_at,
          occupancy: occ
        });
      } catch (e) {}
    }
  },

  // State mutators
  getShelterById(id, fallbackName = null) {
    if (!id && !fallbackName) return null;
    let found = null;
    if (id) {
      const strId = String(id).toLowerCase();
      found = this.shelters.find(s => s.id === id || String(s.id).toLowerCase() === strId);
    }
    if (!found && fallbackName) {
      const strName = String(fallbackName).toLowerCase();
      found = this.shelters.find(s => s.name && s.name.toLowerCase() === strName);
    }
    return found;
  },

  setRole(newRole) {
    this.role = newRole;
  },

  setConsent(granted) {
    this.consent = granted;
    try {
      localStorage.setItem("skyguard_consent", granted ? "granted" : "denied");
    } catch (e) {}
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
