/**
 * SkyGuard Frontend — Leaflet.js Interactive Web Prototype (SG-9)
 * Discipline: ПІС 2026 | Group: ОІ-33 | Team: corelogic
 * Author: Денис Пелех (PM / UI/UX & Frontend Lead)
 * Version: 2.0.0 (With Alarm Mode, Haversine Routing, DQ-3 Quorum, GPS & GeoJSON Export)
 */

// 1. Initial State
const state = {
  role: "CITIZEN",
  consent: true, // Default L2 consent active
  userLocation: { lat: 49.8419, lon: 24.0315 }, // Lviv, Rynok Square (center)
  activeFilter: "ALL",
  activeFeatures: new Set(),
  searchQuery: "",
  selectedShelterId: null,
  tampered: false,
  alarmActive: false,
  quorumCounts: {}, // shelterId -> count
  routeLine: null,
  shelters: []
};

// 2. Embedded Realistic Lviv Shelters Catalog (RFC 7946 GeoJSON Source)
const DEFAULT_SHELTERS = [
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
];

// 3. Mock Chained Audit Trail (SHA-256)
let auditLog = [
  {
    seq: 1,
    time: "2026-11-10T14:00:00Z",
    actor: "sys_init",
    role: "DSNS Operator",
    action: "GENESIS_BLOCK_INIT",
    resource: "system/core",
    cls: "INTERNAL",
    status: 200,
    hash: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  },
  {
    seq: 2,
    time: "2026-11-10T14:15:22Z",
    actor: "citizen_01",
    role: "Citizen",
    action: "CONSENT_OPT_IN_GRANTED",
    resource: "user/citizen_01",
    cls: "SENSITIVE",
    status: 200,
    hash: "9f83c60518882654514eb224c4e9d6da3150774a3f5963738194a0f443812829"
  },
  {
    seq: 3,
    time: "2026-11-10T14:30:10Z",
    actor: "citizen_01",
    role: "Citizen",
    action: "READ_PUBLIC_CATALOG",
    resource: "shelters/all",
    cls: "PUBLIC",
    status: 200,
    hash: "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e"
  },
  {
    seq: 4,
    time: "2026-11-10T14:45:05Z",
    actor: "manager_koval",
    role: "Shelter Manager",
    action: "UPDATE_STATUS_VERIFIED",
    resource: "shelter/SH-LVIV-001",
    cls: "PUBLIC",
    status: 200,
    hash: "7d793037a0760186574b0282f2f435e70d63877d4456215179590f7727e9da7a"
  },
  {
    seq: 5,
    time: "2026-11-10T15:02:18Z",
    actor: "citizen_02",
    role: "Citizen",
    action: "DQ_VIOLATION_HAVERSINE",
    resource: "shelter/SH-LVIV-008",
    cls: "PUBLIC",
    status: 422,
    hash: "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
  },
  {
    seq: 6,
    time: "2026-11-10T15:10:44Z",
    actor: "citizen_03",
    role: "Citizen",
    action: "READ_CONFIDENTIAL_TELEMETRY",
    resource: "shelter/SH-LVIV-003/telemetry",
    cls: "CONFIDENTIAL",
    status: 403,
    hash: "11a43a042541e316e3093c75a32ec05584b93417b654c601a13fa47d30f40e59"
  },
  {
    seq: 7,
    time: "2026-11-10T15:25:30Z",
    actor: "auditor_sec",
    role: "Security Auditor",
    action: "AUDIT_CHAIN_VERIFY_INSPECT",
    resource: "governance/audit-trail",
    cls: "INTERNAL",
    status: 200,
    hash: "c500eeeaf6e3771ce16a2c7c87281877590bdf3016f022d13cb6ceb9953a3237"
  }
];

// 4. Mathematical Haversine Distance Calculation (Metres)
function calculateHaversineDistance(lat1, lon1, lat2, lon2) {
  const R = 6371000; // Earth radius in metres
  const toRad = deg => (deg * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return Math.round(R * c);
}

function formatDistance(metres) {
  if (metres < 1000) return `${metres} м`;
  return `${(metres / 1000).toFixed(1)} км`;
}

function calculateWalkingMinutes(metres) {
  const speedMetresPerMin = 83.3; // 5 km/h
  const mins = Math.max(1, Math.round(metres / speedMetresPerMin));
  return mins;
}

// 5. Leaflet Map Initialization
let map;
let markersLayer;
let userMarker = null;

function initMap() {
  map = L.map("map", {
    zoomControl: false,
    attributionControl: false
  }).setView([49.8397, 24.0297], 13.5);

  // CartoDB Dark Matter
  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    subdomains: "abcd",
    maxZoom: 19
  }).addTo(map);

  L.control.zoom({ position: "bottomright" }).addTo(map);

  markersLayer = L.layerGroup().addTo(map);

  // Initialize quorum counts
  DEFAULT_SHELTERS.forEach(s => {
    state.quorumCounts[s.id] = (s.status === "LIMITED" ? 2 : 1);
  });

  state.shelters = [...DEFAULT_SHELTERS];
  updateUserMarker();
  renderShelters();
  updateStats();
}

function updateUserMarker() {
  if (!map) return;
  if (userMarker) {
    markersLayer.removeLayer(userMarker);
    userMarker = null;
  }

  if (state.consent && state.userLocation) {
    const icon = L.divIcon({
      className: "custom-user-pin",
      html: `
        <div class="user-live-pin">
          <div class="user-live-pulse"></div>
        </div>
      `,
      iconSize: [20, 20],
      iconAnchor: [10, 10]
    });

    userMarker = L.marker([state.userLocation.lat, state.userLocation.lon], { icon, zIndexOffset: 1000 })
      .bindTooltip("📍 Ваша поточна геопозиція", { direction: "top", offset: [0, -10] })
      .addTo(markersLayer);
  }
}

function createMarkerIcon(status, isHighlighted = false) {
  let pinClass = "pin-open";
  let iconEmoji = "🛡️";

  if (status === "LIMITED") {
    pinClass = "pin-limited";
    iconEmoji = "⚠️";
  } else if (status === "CLOSED") {
    pinClass = "pin-closed";
    iconEmoji = "⛔";
  }

  return L.divIcon({
    className: "custom-pin",
    html: `
      <div class="${pinClass} ${isHighlighted ? 'pin-highlighted' : ''}">
        ${status !== "CLOSED" ? '<div class="pin-pulse"></div>' : ''}
        <div class="pin-core" ${isHighlighted ? 'style="border-color: #38bdf8; box-shadow: 0 0 20px #38bdf8;"' : ''}>
          <span class="pin-icon">${iconEmoji}</span>
        </div>
      </div>
    `,
    iconSize: [36, 36],
    iconAnchor: [18, 34]
  });
}

function renderShelters() {
  if (!markersLayer) return;
  markersLayer.clearLayers();
  
  if (userMarker) markersLayer.addLayer(userMarker);
  if (state.routeLine) markersLayer.addLayer(state.routeLine);

  const query = state.searchQuery.toLowerCase().trim();

  state.shelters.forEach(shelter => {
    // Alarm Mode: only OPEN shelters shown!
    if (state.alarmActive && shelter.status !== "OPEN") return;

    // Status Filter
    if (state.activeFilter !== "ALL" && shelter.status !== state.activeFilter) return;

    // Feature Toggles Filter
    if (state.activeFeatures.has("wheelchair") && !shelter.wheelchair) return;
    if (state.activeFeatures.has("generator") && !shelter.generator) return;
    if (state.activeFeatures.has("starlink") && !shelter.starlink) return;
    if (state.activeFeatures.has("water") && !shelter.water) return;

    // Search Filter
    if (query) {
      const matchName = shelter.name.toLowerCase().includes(query);
      const matchAddr = shelter.address.toLowerCase().includes(query);
      const matchDistrict = shelter.district.toLowerCase().includes(query);
      if (!matchName && !matchAddr && !matchDistrict) return;
    }

    const isHighlighted = (state.selectedShelterId === shelter.id);
    const icon = createMarkerIcon(shelter.status, isHighlighted);
    const marker = L.marker([shelter.lat, shelter.lon], { icon });

    marker.on("click", () => {
      openShelterDetails(shelter.id);
    });

    markersLayer.addLayer(marker);
  });
}

function updateStats() {
  const total = state.shelters.length;
  const open = state.shelters.filter(s => s.status === "OPEN").length;
  const capacity = state.shelters.reduce((acc, s) => acc + s.capacity, 0);

  document.getElementById("statsTotal").textContent = total;
  document.getElementById("statsOpen").textContent = open;
  document.getElementById("statsCapacity").textContent = capacity.toLocaleString("uk-UA");
  document.getElementById("statsMode").textContent = state.alarmActive 
    ? "🚨 ПОВІТРЯНА ТРИВОГА" 
    : (state.consent ? "Штатний (L1/L2)" : "Обмежений (L1)");
}

// 6. Shelter Details Sidebar & Routing
function openShelterDetails(shelterId) {
  state.selectedShelterId = shelterId;
  const shelter = state.shelters.find(s => s.id === shelterId);
  if (!shelter) return;

  const sidebar = document.getElementById("detailsSidebar");
  const badge = document.getElementById("detailStatusBadge");
  const title = document.getElementById("detailTitle");
  const address = document.getElementById("detailAddress");
  const distEl = document.getElementById("detailDistance");
  const occText = document.getElementById("detailOccupancyText");
  const occBar = document.getElementById("detailOccupancyBar");
  const confTime = document.getElementById("detailConfirmedTime");
  const routeEstText = document.getElementById("routeEstText");
  const routeBtn = document.getElementById("btnToggleRoute");

  title.textContent = shelter.name;
  address.innerHTML = `📍 ${shelter.address} <span style="color: var(--text-dim);">(${shelter.district} р-н)</span>`;
  confTime.textContent = `Останнє підтвердження: ${shelter.confirmed_at}`;

  // Status Badge
  badge.className = "status-badge";
  if (shelter.status === "OPEN") {
    badge.classList.add("badge-open");
    badge.textContent = "🟢 Відчинено";
  } else if (shelter.status === "LIMITED") {
    badge.classList.add("badge-limited");
    badge.textContent = "🟡 Обмежена місткість";
  } else {
    badge.classList.add("badge-closed");
    badge.textContent = "🔴 Зачинено";
  }

  // Occupancy
  occText.textContent = `${shelter.current_occupancy} / ${shelter.capacity}`;
  const pct = Math.min(100, Math.round((shelter.current_occupancy / shelter.capacity) * 100));
  occBar.style.width = `${pct}%`;

  // Distance & Navigation Card
  if (state.consent && state.userLocation) {
    const dist = calculateHaversineDistance(state.userLocation.lat, state.userLocation.lon, shelter.lat, shelter.lon);
    const mins = calculateWalkingMinutes(dist);
    distEl.innerHTML = `🎯 <b>${formatDistance(dist)}</b> від вашої позиції`;
    distEl.style.display = "inline-flex";
    routeEstText.textContent = `🚶 ~${mins} хв пішки (${formatDistance(dist)})`;
    routeBtn.style.display = "block";
    document.getElementById("routeCard").style.display = "block";
  } else {
    distEl.innerHTML = `🔒 <i>Відстань приховано (потрібна згода на GPS)</i>`;
    distEl.style.display = "inline-flex";
    document.getElementById("routeCard").style.display = "none";
  }

  // Quorum Consensus Card (DQ-3)
  updateQuorumDisplay(shelter.id);

  // Amenities Grid
  const amenitiesGrid = document.getElementById("detailAmenitiesGrid");
  amenitiesGrid.innerHTML = `
    <div class="amenity-item ${shelter.wheelchair ? 'amenity-active' : 'amenity-inactive'}">
      <span class="amenity-icon">♿</span>
      <span>${shelter.wheelchair ? 'Пандус / Доступно' : 'Без пандуса'}</span>
    </div>
    <div class="amenity-item ${shelter.generator ? 'amenity-active' : 'amenity-inactive'}">
      <span class="amenity-icon">⚡</span>
      <span>${shelter.generator ? 'Генератор 15 кВт' : 'Без генератора'}</span>
    </div>
    <div class="amenity-item ${shelter.starlink ? 'amenity-active' : 'amenity-inactive'}">
      <span class="amenity-icon">🛰️</span>
      <span>${shelter.starlink ? 'Термінал Starlink' : 'Мобільний зв’язок'}</span>
    </div>
    <div class="amenity-item ${shelter.water ? 'amenity-active' : 'amenity-inactive'}">
      <span class="amenity-icon">💧</span>
      <span>${shelter.water ? 'Питна вода (бак)' : 'Технічна вода'}</span>
    </div>
  `;

  // Commander (L2) Privacy Gate
  const commanderContent = document.getElementById("commanderDetailsContent");
  if (state.consent || state.role !== "ANONYMOUS") {
    commanderContent.className = "";
    document.getElementById("detailCommanderName").textContent = shelter.commander.name;
    document.getElementById("detailCommanderPhone").textContent = `📞 ${shelter.commander.phone}`;
    document.getElementById("detailCommanderId").textContent = `Службовий жетон: ${shelter.commander.id}`;
  } else {
    commanderContent.className = "blurred-content";
    document.getElementById("detailCommanderName").textContent = "Ковальчук П. О.";
    document.getElementById("detailCommanderPhone").textContent = "📞 +380 67 ••• •• ••";
    document.getElementById("detailCommanderId").textContent = "Службовий жетон: DSNS-LV-••••";
  }

  // Telemetry (L3)
  const isPrivileged = ["MANAGER", "OPERATOR", "AUDITOR"].includes(state.role);
  const telemetryContent = document.getElementById("telemetryDetailsContent");
  if (isPrivileged) {
    telemetryContent.className = "";
    document.getElementById("detailLockStatus").textContent = `Стан: ${shelter.lock.state} · Батарея: ${shelter.lock.battery}`;
    document.getElementById("detailLockId").textContent = `Модуль: ${shelter.lock.id} (Сигнал: ${shelter.lock.rssi})`;
  } else {
    telemetryContent.className = "blurred-content";
    document.getElementById("detailLockStatus").textContent = `Стан: •••••••• · Батарея: ••%`;
    document.getElementById("detailLockId").textContent = `Модуль: LOCK-••••-••• (Захищено RBAC L3)`;
  }

  sidebar.classList.add("open");
}

function closeShelterDetails() {
  document.getElementById("detailsSidebar").classList.remove("open");
  clearRouteLine();
}

// 7. Route Polyline Drawing (Haversine Walking Path)
function drawRouteToShelter(shelterId) {
  const shelter = state.shelters.find(s => s.id === shelterId);
  if (!shelter || !state.userLocation) return;

  clearRouteLine();

  const userPoint = [state.userLocation.lat, state.userLocation.lon];
  const shelterPoint = [shelter.lat, shelter.lon];

  // Draw animated dashed route line
  state.routeLine = L.polyline([userPoint, shelterPoint], {
    color: "#38bdf8",
    weight: 4,
    opacity: 0.9,
    dashArray: "8, 8",
    className: "route-pulse-line"
  }).addTo(markersLayer);

  // Fit bounds to show full route
  map.fitBounds(L.latLngBounds([userPoint, shelterPoint]), { padding: [80, 80] });

  const dist = calculateHaversineDistance(userPoint[0], userPoint[1], shelterPoint[0], shelterPoint[1]);
  const mins = calculateWalkingMinutes(dist);
  showToast(`🗺️ Побудовано найкоротший піший маршрут: ${formatDistance(dist)} (~${mins} хв)`, "info");
}

function clearRouteLine() {
  if (state.routeLine && markersLayer) {
    markersLayer.removeLayer(state.routeLine);
    state.routeLine = null;
  }
}

// 8. Air Raid Alert Mode Simulation (🚨 ДСНС)
function toggleAlarmMode() {
  state.alarmActive = !state.alarmActive;
  const banner = document.getElementById("alertBanner");
  const triggerBtn = document.getElementById("btnAlarmTrigger");
  const triggerText = document.getElementById("alarmBtnText");

  if (state.alarmActive) {
    banner.classList.add("active");
    triggerBtn.classList.add("alarm-active");
    triggerText.textContent = "Вимкнути тривогу";

    // Filter map strictly to OPEN shelters
    state.activeFilter = "OPEN";
    document.querySelectorAll(".filter-chips .chip").forEach(c => {
      c.classList.toggle("active", c.dataset.status === "OPEN");
    });

    // Auto-find nearest open shelter
    const openShelters = state.shelters.filter(s => s.status === "OPEN");
    if (openShelters.length > 0 && state.userLocation) {
      let nearest = openShelters[0];
      let minDist = calculateHaversineDistance(state.userLocation.lat, state.userLocation.lon, nearest.lat, nearest.lon);

      openShelters.forEach(s => {
        const d = calculateHaversineDistance(state.userLocation.lat, state.userLocation.lon, s.lat, s.lon);
        if (d < minDist) {
          minDist = d;
          nearest = s;
        }
      });

      // Auto-route and open details
      renderShelters();
      openShelterDetails(nearest.id);
      drawRouteToShelter(nearest.id);

      showToast(`🚨 ПОВІТРЯНА ТРИВОГА! Найближче укриття: ${nearest.name} (${formatDistance(minDist)})`, "error");
    }

    logAuditEvent("AIR_RAID_ALERT_ACTIVATED", "dsns/lviv_region", "SENSITIVE", 200);
  } else {
    banner.classList.remove("active");
    triggerBtn.classList.remove("alarm-active");
    triggerText.textContent = "Симуляція тривоги";

    clearRouteLine();
    state.activeFilter = "ALL";
    document.querySelectorAll(".filter-chips .chip").forEach(c => {
      c.classList.toggle("active", c.dataset.status === "ALL");
    });
    renderShelters();
    showToast("✓ Відбій повітряної тривоги. Відновлено штатний режим роботи", "success");
    logAuditEvent("AIR_RAID_ALERT_DEACTIVATED", "dsns/lviv_region", "INTERNAL", 200);
  }

  updateStats();
}

// 9. Crowdsourcing Quorum DQ-3 Simulator
function updateQuorumDisplay(shelterId) {
  const count = state.quorumCounts[shelterId] || 1;
  const countText = document.getElementById("quorumCountText");
  const bar = document.getElementById("quorumBarFill");
  const hint = document.getElementById("quorumStatusHint");

  countText.textContent = `${count} / 3 свідків`;
  const pct = Math.min(100, Math.round((count / 3) * 100));
  bar.style.width = `${pct}%`;

  if (count >= 3) {
    countText.style.color = "#34d399";
    hint.textContent = "✓ Консенсус DQ-3 досягнуто! Статус верифіковано";
  } else {
    countText.style.color = "#fbbf24";
    hint.textContent = `Потрібно ще ${3 - count} підтвердження від свідків поруч`;
  }
}

function addWitnessToQuorum() {
  if (!state.selectedShelterId) return;
  const id = state.selectedShelterId;
  const shelter = state.shelters.find(s => s.id === id);
  if (!shelter) return;

  state.quorumCounts[id] = (state.quorumCounts[id] || 1) + 1;
  const current = state.quorumCounts[id];

  updateQuorumDisplay(id);

  if (current >= 3) {
    shelter.status = "OPEN";
    shelter.confirmed_at = "Щойно (кворум DQ-3 підтверджено)";
    renderShelters();
    openShelterDetails(id);
    showToast("🎉 Кворум DQ-3 досягнуто (3/3)! Укриття автоматично переведено в статус ВІДЧИНЕНО", "success");
    logAuditEvent("QUORUM_DQ3_CONSENSUS_REACHED", `shelter/${id}`, "PUBLIC", 200);
  } else {
    showToast(`👍 Додано підтвердження свідка (${current}/3). До консенсусу залишилось: ${3 - current}`, "info");
    logAuditEvent("CROWDSOURCE_WITNESS_SUBMITTED", `shelter/${id}`, "PUBLIC", 200);
  }
}

// 10. Locate Me (HTML5 Geolocation API)
function handleLocateMe() {
  if (!navigator.geolocation) {
    showToast("Геолокація не підтримується цим браузером", "warning");
    return;
  }

  showToast("📡 Визначення вашої точної GPS-позиції...", "info");

  navigator.geolocation.getCurrentPosition(
    pos => {
      state.userLocation = { lat: pos.coords.latitude, lon: pos.coords.longitude };
      state.consent = true;
      setConsent(true);
      updateUserMarker();
      map.setView([state.userLocation.lat, state.userLocation.lon], 15);
      showToast(`🎯 Координати знайдено: [${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}]`, "success");
    },
    err => {
      // Fallback to central Lviv
      state.userLocation = { lat: 49.8419, lon: 24.0315 };
      updateUserMarker();
      map.setView([49.8419, 24.0315], 14.5);
      showToast("📍 Використовується фіксована точка: пл. Ринок (центр Львова)", "warning");
    },
    { enableHighAccuracy: true, timeout: 5000 }
  );
}

// 11. GeoJSON Registry Export (RFC 7946 L1 PUBLIC)
function exportGeoJsonRegistry() {
  const geojson = {
    type: "FeatureCollection",
    name: "SkyGuard_Lviv_Shelters_Export",
    crs: { type: "name", properties: { name: "urn:ogc:def:crs:OGC:1.3:CRS84" } },
    features: state.shelters.map(s => ({
      type: "Feature",
      properties: {
        id: s.id,
        name: s.name,
        address: s.address,
        district: s.district,
        capacity: s.capacity,
        current_occupancy: s.current_occupancy,
        status: s.status,
        wheelchair_accessible: s.wheelchair,
        has_power_generator: s.generator,
        has_starlink: s.starlink,
        potable_water: s.water,
        last_confirmed: s.confirmed_at
      },
      geometry: { type: "Point", coordinates: [s.lon, s.lat] }
    }))
  };

  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(geojson, null, 2));
  const dlAnchor = document.createElement("a");
  dlAnchor.setAttribute("href", dataStr);
  dlAnchor.setAttribute("download", "skyguard_lviv_shelters.geojson");
  dlAnchor.click();
  showToast("📥 Завантажено skyguard_lviv_shelters.geojson (RFC 7946)", "success");
}

// 12. Modals Management
function openConsentModal() {
  document.getElementById("consentModal").classList.add("active");
}

function closeConsentModal() {
  document.getElementById("consentModal").classList.remove("active");
}

function setConsent(granted) {
  state.consent = granted;
  const indicator = document.getElementById("consentBtn");
  const text = document.getElementById("consentStatusText");

  if (granted) {
    indicator.className = "consent-indicator granted";
    text.textContent = "Згода на геодані: Активна (L2)";
    showToast("✓ Згоду на обробку GPS-координат успішно збережено (L2)", "success");
    logAuditEvent("CONSENT_OPT_IN_GRANTED", "user/citizen_01", "SENSITIVE", 200);
  } else {
    indicator.className = "consent-indicator denied";
    text.textContent = "Згода: Відхилено (Режим L1 PUBLIC)";
    showToast("⚠️ Режим L1 PUBLIC: геолокація вимкнена відповідно до ст. 11 ЗУ", "warning");
    logAuditEvent("CONSENT_OPT_OUT_REVOKED", "user/citizen_01", "SENSITIVE", 200);
  }

  updateUserMarker();
  updateStats();
  if (state.selectedShelterId) openShelterDetails(state.selectedShelterId);
  closeConsentModal();
}

// 13. 403 Forbidden Security Dialog (UC-03 Simulation)
function triggerForbiddenSimulation() {
  const isPrivileged = ["MANAGER", "OPERATOR", "AUDITOR"].includes(state.role);
  
  if (isPrivileged) {
    showToast("🔓 Авторизація успішна: доступ до телеметрії замка надано (RBAC L3)", "success");
    return;
  }

  const incidentId = "ae-" + Math.random().toString(36).substring(2, 6) + "-" + Math.random().toString(36).substring(2, 10);
  const timestamp = new Date().toISOString();

  document.getElementById("forbiddenCurrentRole").textContent = state.role;
  document.getElementById("forbiddenAuditId").textContent = incidentId;
  document.getElementById("forbiddenTimestamp").textContent = timestamp;

  document.getElementById("forbiddenModal").classList.add("active");

  logAuditEvent("READ_CONFIDENTIAL_TELEMETRY", `shelter/${state.selectedShelterId || 'SH-LVIV-001'}/telemetry`, "CONFIDENTIAL", 403, incidentId);
}

// 14. Crowdsourcing Status Dialog (UC-02 / SG-21)
function openReportModal() {
  if (!state.selectedShelterId) return;
  const shelter = state.shelters.find(s => s.id === state.selectedShelterId);
  if (!shelter) return;

  document.getElementById("reportModalShelterName").textContent = shelter.name;
  const distEl = document.getElementById("reportModalDistanceCheck");
  const dqWarning = document.getElementById("dqWarningBox");

  let dist = 50; // default near
  if (state.consent && state.userLocation) {
    dist = calculateHaversineDistance(state.userLocation.lat, state.userLocation.lon, shelter.lat, shelter.lon);
  }

  distEl.innerHTML = `Розрахована відстань за формулою Haversine: <b>${formatDistance(dist)}</b>`;

  // Check DQ-1 rule (<= 100m)
  if (dist > 100) {
    dqWarning.style.display = "block";
    dqWarning.innerHTML = `⚠️ <b>Порушення правила якості DQ-1:</b> Ваша дистанція до об'єкта становить <b>${formatDistance(dist)} (> 100 м)</b>. Згідно з політикою Data Governance, звіт буде відхилено сервером із кодом <b>HTTP 422 Unprocessable Entity</b> для запобігання фейковим оновленням.`;
  } else {
    dqWarning.style.display = "none";
  }

  document.getElementById("reportModal").classList.add("active");
}

function submitReport() {
  const shelter = state.shelters.find(s => s.id === state.selectedShelterId);
  if (!shelter) return;

  const selectedStatus = document.querySelector('input[name="reportStatus"]:checked').value;
  let dist = 50;
  if (state.consent && state.userLocation) {
    dist = calculateHaversineDistance(state.userLocation.lat, state.userLocation.lon, shelter.lat, shelter.lon);
  }

  // If distance > 100m -> Fail DQ-1 with 422
  if (dist > 100) {
    logAuditEvent("DQ_VIOLATION_HAVERSINE", `shelter/${shelter.id}`, "PUBLIC", 422);
    showToast(`⛔ Помилка HTTP 422: Відхилено за правилом якості DQ-1 (дистанція ${formatDistance(dist)} > 100 м)!`, "error");
    document.getElementById("reportModal").classList.remove("active");
    return;
  }

  // Success 200 OK
  shelter.status = selectedStatus;
  shelter.confirmed_at = "Щойно (краудсорсинг підтверджено)";
  if (selectedStatus === "OPEN") shelter.current_occupancy = Math.min(shelter.capacity, shelter.current_occupancy + 15);
  if (selectedStatus === "CLOSED") shelter.current_occupancy = 0;

  logAuditEvent("CROWDSOURCE_STATUS_UPDATE", `shelter/${shelter.id}`, "PUBLIC", 200);
  showToast(`✓ Статус укриття оновлено на ${selectedStatus} (200 OK)! Подію внесено в аудит`, "success");

  renderShelters();
  openShelterDetails(shelter.id);
  updateStats();
  document.getElementById("reportModal").classList.remove("active");
}

// 15. Audit Trail Engine (SHA-256 Chaining & Verification)
function logAuditEvent(action, resource, classification, statusCode, customEventId = null) {
  const seq = auditLog.length + 1;
  const time = new Date().toISOString();
  const actor = state.role.toLowerCase() + "_user";
  const fakeHash = Math.random().toString(16).substring(2) + Math.random().toString(16).substring(2) + Math.random().toString(16).substring(2);

  const entry = {
    seq,
    time,
    actor,
    role: state.role,
    action,
    resource,
    cls: classification,
    status: statusCode,
    hash: fakeHash
  };

  auditLog.push(entry);
}

function openAuditConsole() {
  renderAuditTable();
  document.getElementById("auditModal").classList.add("active");
}

function renderAuditTable(filterStatus = null) {
  const tbody = document.getElementById("auditTableBody");
  tbody.innerHTML = "";

  const items = filterStatus ? auditLog.filter(e => e.status === filterStatus) : auditLog;

  items.forEach(item => {
    const tr = document.createElement("tr");
    let statusClass = "status-cell-200";
    if (item.status === 403) statusClass = "status-cell-403";
    if (item.status === 422) statusClass = "status-cell-422";
    if (item.status === 401) statusClass = "status-cell-401";

    tr.innerHTML = `
      <td>#${item.seq}</td>
      <td style="color: var(--text-dim);">${item.time.replace("T", " ").replace("Z", "")}</td>
      <td><b>${item.role}</b> <span style="color: var(--text-dim); font-size: 0.7rem;">(${item.actor})</span></td>
      <td><code>${item.action}</code></td>
      <td><span class="classification-tag tag-l${item.cls === 'PUBLIC' ? 1 : item.cls === 'INTERNAL' ? 2 : 3}">${item.cls}</span></td>
      <td class="${statusClass}">HTTP ${item.status}</td>
      <td style="color: #60a5fa; font-size: 0.72rem;"><code>${item.hash.substring(0, 16)}…</code></td>
    `;
    tbody.appendChild(tr);
  });

  const strip = document.getElementById("auditStatusStrip");
  const label = document.getElementById("auditStatusLabel");
  if (state.tampered) {
    strip.style.background = "#7f1d1d";
    strip.style.borderColor = "#ef4444";
    strip.style.color = "#fee2e2";
    label.innerHTML = `⚠️ <b>КРИТИЧНО: Порушення цілісності ланцюга!</b> Підроблено блок #4 (Broken Chain SHA-256 Mismatch)`;
  } else {
    strip.style.background = "#064e3b";
    strip.style.borderColor = "#059669";
    strip.style.color = "#6ee7b7";
    label.innerHTML = `✓ Ланцюг SHA-256: <b>ЦІЛІСНИЙ</b> (${auditLog.length} блоків перевірено HMAC-SHA-256)`;
  }
}

function simulateTamper() {
  state.tampered = !state.tampered;
  if (state.tampered) {
    showToast("⚠️ Симуляція атаки: змінено байт у блоці #4! Перевірка цілісності виявила розрив", "error");
  } else {
    showToast("✓ Хеш-ланцюг відновлено до еталонного стану", "success");
  }
  renderAuditTable();
}

function exportAuditJson() {
  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(auditLog, null, 2));
  const dlAnchor = document.createElement("a");
  dlAnchor.setAttribute("href", dataStr);
  dlAnchor.setAttribute("download", "audit_export.json");
  dlAnchor.click();
  showToast("📥 Файл audit_export.json успішно завантажено", "success");
}

// 16. Toasts
function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(50px)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// 17. DOM Event Listeners & Binding
document.addEventListener("DOMContentLoaded", () => {
  initMap();

  // Role Switcher
  const roleSelect = document.getElementById("roleSelector");
  roleSelect.value = state.role;
  roleSelect.addEventListener("change", e => {
    state.role = e.target.value;
    showToast(`Роль переключено на: ${e.target.options[e.target.selectedIndex].text}`, "info");
    if (state.selectedShelterId) openShelterDetails(state.selectedShelterId);
  });

  // Alarm Trigger
  document.getElementById("btnAlarmTrigger").addEventListener("click", toggleAlarmMode);
  document.getElementById("btnDismissAlert").addEventListener("click", toggleAlarmMode);

  // Consent Button & Modal
  document.getElementById("consentBtn").addEventListener("click", openConsentModal);
  document.getElementById("closeConsentModalBtn").addEventListener("click", closeConsentModal);
  document.getElementById("btnGrantConsent").addEventListener("click", () => setConsent(true));
  document.getElementById("btnDenyConsent").addEventListener("click", () => setConsent(false));

  // Sidebar Controls
  document.getElementById("closeSidebarBtn").addEventListener("click", closeShelterDetails);
  document.getElementById("requestTelemetryBtn").addEventListener("click", triggerForbiddenSimulation);
  document.getElementById("openReportBtn").addEventListener("click", openReportModal);
  document.getElementById("btnToggleRoute").addEventListener("click", () => {
    if (state.selectedShelterId) drawRouteToShelter(state.selectedShelterId);
  });
  document.getElementById("btnAddWitnessBtn").addEventListener("click", addWitnessToQuorum);

  // Locate Me Floating Button
  document.getElementById("btnLocateMe").addEventListener("click", handleLocateMe);

  // GeoJSON Export
  document.getElementById("btnExportGeoJson").addEventListener("click", exportGeoJsonRegistry);

  // 403 Forbidden Modal
  document.getElementById("btnCloseForbiddenBtn").addEventListener("click", () => {
    document.getElementById("forbiddenModal").classList.remove("active");
  });

  // Report Modal
  document.getElementById("closeReportModalBtn").addEventListener("click", () => {
    document.getElementById("reportModal").classList.remove("active");
  });
  document.getElementById("btnCancelReport").addEventListener("click", () => {
    document.getElementById("reportModal").classList.remove("active");
  });
  document.getElementById("btnSubmitReport").addEventListener("click", submitReport);

  // Audit Console Modal
  document.getElementById("openAuditBtn").addEventListener("click", openAuditConsole);
  document.getElementById("closeAuditModalBtn").addEventListener("click", () => {
    document.getElementById("auditModal").classList.remove("active");
  });
  document.getElementById("btnCloseAuditDialog").addEventListener("click", () => {
    document.getElementById("auditModal").classList.remove("active");
  });
  document.getElementById("btnSimulateTamper").addEventListener("click", simulateTamper);
  document.getElementById("btnExportAuditJson").addEventListener("click", exportAuditJson);

  // Audit Filter Buttons
  document.getElementById("auditFilterAll").addEventListener("click", () => renderAuditTable());
  document.getElementById("auditFilter200").addEventListener("click", () => renderAuditTable(200));
  document.getElementById("auditFilter403").addEventListener("click", () => renderAuditTable(403));
  document.getElementById("auditFilter422").addEventListener("click", () => renderAuditTable(422));

  // Search Input
  document.getElementById("searchInput").addEventListener("input", e => {
    state.searchQuery = e.target.value;
    renderShelters();
  });

  // Status Filter Chips
  document.querySelectorAll(".filter-chips .chip").forEach(chip => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".filter-chips .chip").forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      state.activeFilter = chip.dataset.status;
      renderShelters();
    });
  });

  // Feature Toggle Chips
  document.querySelectorAll(".feature-toggles .toggle-chip").forEach(toggle => {
    toggle.addEventListener("click", () => {
      const feat = toggle.dataset.feature;
      if (state.activeFeatures.has(feat)) {
        state.activeFeatures.delete(feat);
        toggle.classList.remove("active");
      } else {
        state.activeFeatures.add(feat);
        toggle.classList.add("active");
      }
      renderShelters();
    });
  });
});
