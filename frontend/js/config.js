/**
 * SkyGuard — Frontend Configuration & Constants
 * Discipline: ПІС 2026 | Group: ОІ-33 | Team: corelogic
 * Module: js/config.js
 */

window.SkyGuard = window.SkyGuard || {};

SkyGuard.Config = {
  // Backend API Integration Settings (FastAPI SG-10 / SG-21)
  API_BASE_URL: "http://localhost:8000/api/v1",
  API_TIMEOUT_MS: 3000,

  // Map Initial Coordinates (Lviv City Center)
  MAP_CENTER: [49.8397, 24.0297],
  MAP_DEFAULT_ZOOM: 13.5,
  MAP_TILE_LAYER: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
  MAP_SUBDOMAINS: "abcd",
  MAP_MAX_ZOOM: 19,

  // Default User Geolocation (Rynok Square, Lviv)
  DEFAULT_USER_LOCATION: {
    lat: 49.8419,
    lon: 24.0315,
    name: "м. Львів, пл. Ринок (центр)"
  },

  // Data Quality Rules (Architecture Section 4 & SG-21)
  DQ_RULES: {
    DQ1_MAX_DISTANCE_METRES: 100, // Maximum allowed distance for crowdsourcing report
    DQ3_CONSENSUS_QUORUM: 3,      // Required independent confirmations for status flip
    WALKING_SPEED_METRES_MIN: 83.3 // Average pedestrian speed (~5 km/h)
  },

  // Available User Roles (RBAC Matrix)
  ROLES: {
    CITIZEN: { id: "CITIZEN", label: "Громадянин (Citizen)", clearance: "L1_PUBLIC" },
    MANAGER: { id: "MANAGER", label: "Комендант (Shelter Owner)", clearance: "L2_INTERNAL" },
    OPERATOR: { id: "OPERATOR", label: "Офіцер ДСНС (DSNS Officer)", clearance: "L3_CONFIDENTIAL" },
    AUDITOR: { id: "AUDITOR", label: "Аудитор безпеки (Security Auditor)", clearance: "L3_CONFIDENTIAL" }
  },

  // Embedded Realistic Lviv Shelters Catalog (RFC 7946 GeoJSON Standard)
  DEFAULT_SHELTERS: [
    {
      id: "SH-LVIV-001",
      name: "Центральне укриття №1 (ТЦ «Форум Львів»)",
      address: "м. Львів, вул. Під Дубом, 7Б",
      district: "Галицький",
      lat: 49.8510,
      lon: 24.0225,
      capacity: 850,
      current_occupancy: 120,
      status: "OPEN",
      wheelchair: true,
      generator: true,
      starlink: true,
      water: true,
      confirmed_at: "15 хв тому",
      commander: { name: "Ковальчук П. О.", phone: "+380 67 111 22 33", id: "DSNS-LV-4412" },
      lock: { id: "LOCK-ESP32-998", battery: "94%", rssi: "-65 dBm", state: "UNLOCKED" }
    },
    {
      id: "SH-LVIV-002",
      name: "Сховище НУ «Львівська політехніка»",
      address: "м. Львів, вул. Степана Бандери, 12",
      district: "Франківський",
      lat: 49.8355,
      lon: 24.0145,
      capacity: 450,
      current_occupancy: 180,
      status: "OPEN",
      wheelchair: true,
      generator: true,
      starlink: true,
      water: true,
      confirmed_at: "22 хв тому",
      commander: { name: "Григоренко В. М.", phone: "+380 50 444 55 66", id: "DSNS-LV-8801" },
      lock: { id: "LOCK-ESP32-332", battery: "88%", rssi: "-72 dBm", state: "UNLOCKED" }
    },
    {
      id: "SH-LVIV-003",
      name: "Підземне укриття Львівської міської ради (Ратуша)",
      address: "м. Львів, пл. Ринок, 1",
      district: "Галицький",
      lat: 49.8419,
      lon: 24.0315,
      capacity: 250,
      current_occupancy: 65,
      status: "OPEN",
      wheelchair: false,
      generator: true,
      starlink: true,
      water: true,
      confirmed_at: "5 хв тому",
      commander: { name: "Садовий А. І.", phone: "+380 32 297 59 11", id: "LMR-LV-0001" },
      lock: { id: "LOCK-ESP32-101", battery: "99%", rssi: "-55 dBm", state: "UNLOCKED" }
    },
    {
      id: "SH-LVIV-004",
      name: "Сховище Палацу мистецтв / Бібліотека",
      address: "м. Львів, вул. Коперника, 17",
      district: "Галицький",
      lat: 49.8385,
      lon: 24.0255,
      capacity: 320,
      current_occupancy: 295,
      status: "LIMITED",
      wheelchair: true,
      generator: true,
      starlink: false,
      water: true,
      confirmed_at: "35 хв тому",
      commander: { name: "Возняк Т. С.", phone: "+380 67 222 33 44", id: "DSNS-LV-5519" },
      lock: { id: "LOCK-ESP32-404", battery: "75%", rssi: "-80 dBm", state: "UNLOCKED" }
    },
    {
      id: "SH-LVIV-005",
      name: "Укриття Ліцею №8",
      address: "м. Львів, вул. Підвальна, 2",
      district: "Галицький",
      lat: 49.8425,
      lon: 24.0358,
      capacity: 200,
      current_occupancy: 195,
      status: "LIMITED",
      wheelchair: false,
      generator: false,
      starlink: false,
      water: true,
      confirmed_at: "18 хв тому",
      commander: { name: "Данилюк Н. В.", phone: "+380 63 333 44 55", id: "LMR-EDU-08" },
      lock: { id: "LOCK-ESP32-512", battery: "62%", rssi: "-85 dBm", state: "UNLOCKED" }
    },
    {
      id: "SH-LVIV-006",
      name: "Сховище вокзалу «Львів-Головний»",
      address: "м. Львів, пл. Двірцева, 1",
      district: "Залізничний",
      lat: 49.8358,
      lon: 23.9942,
      capacity: 1200,
      current_occupancy: 310,
      status: "OPEN",
      wheelchair: true,
      generator: true,
      starlink: true,
      water: true,
      confirmed_at: "8 хв тому",
      commander: { name: "Бойко І. В.", phone: "+380 67 888 99 00", id: "UZ-LV-01" },
      lock: { id: "LOCK-ESP32-777", battery: "98%", rssi: "-60 dBm", state: "UNLOCKED" }
    },
    {
      id: "SH-LVIV-007",
      name: "Протирадіаційне сховище 8-ї міської лікарні",
      address: "м. Львів, вул. Навроцького, 23",
      district: "Сихівський",
      lat: 49.8085,
      lon: 24.0535,
      capacity: 500,
      current_occupancy: 80,
      status: "OPEN",
      wheelchair: true,
      generator: true,
      starlink: true,
      water: true,
      confirmed_at: "40 хв тому",
      commander: { name: "Федак В. О.", phone: "+380 50 999 00 11", id: "DSNS-LV-8088" },
      lock: { id: "LOCK-ESP32-888", battery: "95%", rssi: "-68 dBm", state: "UNLOCKED" }
    },
    {
      id: "SH-LVIV-008",
      name: "Сховище ЗОШ №90 (Сихів)",
      address: "м. Львів, вул. Антоненка-Давидовича, 8",
      district: "Сихівський",
      lat: 49.7925,
      lon: 24.0620,
      capacity: 350,
      current_occupancy: 0,
      status: "CLOSED",
      wheelchair: true,
      generator: false,
      starlink: false,
      water: false,
      confirmed_at: "3 год тому (ремонт вентиляції)",
      commander: { name: "Сиховська О. П.", phone: "+380 97 123 45 67", id: "LMR-EDU-90" },
      lock: { id: "LOCK-ESP32-901", battery: "40%", rssi: "-90 dBm", state: "LOCKED" }
    },
    {
      id: "SH-LVIV-009",
      name: "Підземний паркінг ТРЦ «Victoria Gardens»",
      address: "м. Львів, вул. Кульпарківська, 226А",
      district: "Франківський",
      lat: 49.8070,
      lon: 23.9785,
      capacity: 1500,
      current_occupancy: 420,
      status: "OPEN",
      wheelchair: true,
      generator: true,
      starlink: true,
      water: true,
      confirmed_at: "12 хв тому",
      commander: { name: "Кульпарківський Д. С.", phone: "+380 67 555 66 77", id: "VG-SEC-01" },
      lock: { id: "LOCK-ESP32-303", battery: "92%", rssi: "-63 dBm", state: "UNLOCKED" }
    },
    {
      id: "SH-LVIV-010",
      name: "Сховище Шевченківського району (Замарстинів)",
      address: "м. Львів, вул. Гетьмана Мазепи, 1А",
      district: "Шевченківський",
      lat: 49.8710,
      lon: 24.0320,
      capacity: 400,
      current_occupancy: 0,
      status: "CLOSED",
      wheelchair: false,
      generator: false,
      starlink: false,
      water: false,
      confirmed_at: "5 год тому (аварійний стан)",
      commander: { name: "Шевченко М. В.", phone: "+380 67 999 88 77", id: "DSNS-LV-1110" },
      lock: { id: "LOCK-ESP32-110", battery: "35%", rssi: "-92 dBm", state: "LOCKED" }
    }
  ]
};
