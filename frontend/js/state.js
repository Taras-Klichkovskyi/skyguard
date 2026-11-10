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

  // Initialize state with default data
  init() {
    this.shelters = JSON.parse(JSON.stringify(SkyGuard.Config.DEFAULT_SHELTERS));
    this.shelters.forEach(s => {
      this.quorumCounts[s.id] = (s.status === "LIMITED" ? 2 : 1);
    });
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
