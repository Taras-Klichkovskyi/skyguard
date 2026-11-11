/**
 * SkyGuard — Main Application Entry Point & Event Wiring
 * Discipline: ПІС 2026 | Group: ОІ-33 | Team: corelogic
 * Author: Денис Пелех (PM / UI/UX & Frontend Lead)
 * Module: js/main.js
 */

window.SkyGuard = window.SkyGuard || {};

SkyGuard.init = async function () {
  console.info("🛡️ Initializing SkyGuard Frontend Web Client v2.1.0...");

  // 1. Initialize State with 10 default Lviv shelters
  SkyGuard.State.init();

  // 2. Initialize Map & Markers immediately (instant render, zero delay!)
  SkyGuard.Map.init();

  // 3. Update Stats Counter
  SkyGuard.UI.updateStats();

  // 4. Setup Event Listeners
  SkyGuard.bindEvents();

  // 5. Connect Live WebSocket (SG-21) in background
  SkyGuard.Api.initWebSocket();

  // 6. Asynchronously check live backend in background
  try {
    const liveShelters = await SkyGuard.Api.fetchShelters();
    if (liveShelters && liveShelters.length > 0) {
      SkyGuard.State.shelters = liveShelters;
      SkyGuard.Map.renderShelters();
      SkyGuard.UI.updateStats();
    }
  } catch (err) {
    console.debug("[SkyGuard] Backend offline, continuing in local mode.");
  }

  console.info("✓ SkyGuard Client initialized successfully.");
};

SkyGuard.bindEvents = function () {
  // 1. Role Selector
  const roleSelect = document.getElementById("roleSelector");
  if (roleSelect) {
    roleSelect.value = SkyGuard.State.role;
    roleSelect.addEventListener("change", e => {
      SkyGuard.State.setRole(e.target.value);
      SkyGuard.UI.showToast(`Роль переключено на: ${e.target.options[e.target.selectedIndex].text}`, "info");
      if (SkyGuard.State.selectedShelterId) {
        SkyGuard.UI.openShelterDetails(SkyGuard.State.selectedShelterId);
      }
    });
  }

  // 2. Air Raid Alarm Triggers
  const btnAlarm = document.getElementById("btnAlarmTrigger");
  const btnDismissAlert = document.getElementById("btnDismissAlert");
  if (btnAlarm) btnAlarm.addEventListener("click", () => SkyGuard.UI.toggleAlarmMode());
  if (btnDismissAlert) btnDismissAlert.addEventListener("click", () => SkyGuard.UI.toggleAlarmMode());

  // 3. Consent Management
  const consentBtn = document.getElementById("consentBtn");
  const closeConsentBtn = document.getElementById("closeConsentModalBtn");
  const btnGrantConsent = document.getElementById("btnGrantConsent");
  const btnDenyConsent = document.getElementById("btnDenyConsent");

  if (consentBtn) consentBtn.addEventListener("click", () => SkyGuard.Security.openConsentModal());
  if (closeConsentBtn) closeConsentBtn.addEventListener("click", () => SkyGuard.Security.closeConsentModal());
  if (btnGrantConsent) btnGrantConsent.addEventListener("click", () => SkyGuard.Security.setConsent(true));
  if (btnDenyConsent) btnDenyConsent.addEventListener("click", () => SkyGuard.Security.setConsent(false));

  // 4. Sidebar Controls
  const closeSidebarBtn = document.getElementById("closeSidebarBtn");
  const requestTelemetryBtn = document.getElementById("requestTelemetryBtn");
  const openReportBtn = document.getElementById("openReportBtn");
  const btnToggleRoute = document.getElementById("btnToggleRoute");
  const btnAddWitnessBtn = document.getElementById("btnAddWitnessBtn");

  if (closeSidebarBtn) closeSidebarBtn.addEventListener("click", () => SkyGuard.UI.closeShelterDetails());
  if (requestTelemetryBtn) requestTelemetryBtn.addEventListener("click", () => SkyGuard.Security.triggerForbiddenIncident());
  if (openReportBtn) openReportBtn.addEventListener("click", () => SkyGuard.Crowdsource.openReportModal());
  if (btnToggleRoute) {
    btnToggleRoute.addEventListener("click", () => {
      if (SkyGuard.State.selectedShelterId) {
        SkyGuard.Map.drawRouteToShelter(SkyGuard.State.selectedShelterId);
      }
    });
  }
  if (btnAddWitnessBtn) btnAddWitnessBtn.addEventListener("click", () => SkyGuard.Crowdsource.addWitnessToQuorum());

  // 5. GPS Locate Me Button
  const btnLocateMe = document.getElementById("btnLocateMe");
  if (btnLocateMe) {
    btnLocateMe.addEventListener("click", () => {
      SkyGuard.UI.showToast("📡 Визначення вашої точної GPS-позиції...", "info");
      SkyGuard.Geo.locateUser(
        (lat, lon) => {
          SkyGuard.State.setUserLocation(lat, lon);
          SkyGuard.Security.setConsent(true);
          SkyGuard.Map.updateUserMarker();
          SkyGuard.Map.instance.setView([lat, lon], 15);
          SkyGuard.UI.showToast(`🎯 Координати знайдено: [${lat.toFixed(4)}, ${lon.toFixed(4)}]`, "success");
        },
        err => {
          SkyGuard.State.setUserLocation(49.8419, 24.0315, "пл. Ринок (центр Львова)");
          SkyGuard.Map.updateUserMarker();
          SkyGuard.Map.instance.setView([49.8419, 24.0315], 14.5);
          SkyGuard.UI.showToast("📍 Використовується фіксована точка: пл. Ринок (центр Львова)", "warning");
        }
      );
    });
  }

  // 6. GeoJSON Registry Export
  const btnExportGeoJson = document.getElementById("btnExportGeoJson");
  if (btnExportGeoJson) {
    btnExportGeoJson.addEventListener("click", () => {
      SkyGuard.Api.downloadGeoJson(SkyGuard.State.shelters);
      SkyGuard.UI.showToast("📥 Завантажено skyguard_lviv_shelters.geojson (RFC 7946)", "success");
    });
  }

  // 7. 403 Forbidden Modal
  const btnCloseForbiddenBtn = document.getElementById("btnCloseForbiddenBtn");
  if (btnCloseForbiddenBtn) {
    btnCloseForbiddenBtn.addEventListener("click", () => {
      document.getElementById("forbiddenModal").classList.remove("active");
    });
  }

  // 8. Crowdsourcing Report Modal
  const closeReportModalBtn = document.getElementById("closeReportModalBtn");
  const btnCancelReport = document.getElementById("btnCancelReport");
  const btnSubmitReport = document.getElementById("btnSubmitReport");

  if (closeReportModalBtn) {
    closeReportModalBtn.addEventListener("click", () => {
      document.getElementById("reportModal").classList.remove("active");
    });
  }
  if (btnCancelReport) {
    btnCancelReport.addEventListener("click", () => {
      document.getElementById("reportModal").classList.remove("active");
    });
  }
  if (btnSubmitReport) {
    btnSubmitReport.addEventListener("click", () => SkyGuard.Crowdsource.submitReport());
  }

  // 9. Audit Console Modal
  const openAuditBtn = document.getElementById("openAuditBtn");
  const closeAuditModalBtn = document.getElementById("closeAuditModalBtn");
  const btnCloseAuditDialog = document.getElementById("btnCloseAuditDialog");
  const btnSimulateTamper = document.getElementById("btnSimulateTamper");
  const btnExportAuditJson = document.getElementById("btnExportAuditJson");

  if (openAuditBtn) {
    openAuditBtn.addEventListener("click", () => {
      SkyGuard.Audit.renderTable();
      document.getElementById("auditModal").classList.add("active");
    });
  }
  if (closeAuditModalBtn) {
    closeAuditModalBtn.addEventListener("click", () => {
      document.getElementById("auditModal").classList.remove("active");
    });
  }
  if (btnCloseAuditDialog) {
    btnCloseAuditDialog.addEventListener("click", () => {
      document.getElementById("auditModal").classList.remove("active");
    });
  }
  if (btnSimulateTamper) {
    btnSimulateTamper.addEventListener("click", () => SkyGuard.Audit.toggleTamperSimulation());
  }
  if (btnExportAuditJson) {
    btnExportAuditJson.addEventListener("click", () => SkyGuard.Audit.exportJson());
  }

  // Audit Filter Buttons
  const filterAll = document.getElementById("auditFilterAll");
  const filter200 = document.getElementById("auditFilter200");
  const filter403 = document.getElementById("auditFilter403");
  const filter422 = document.getElementById("auditFilter422");

  if (filterAll) filterAll.addEventListener("click", () => SkyGuard.Audit.renderTable());
  if (filter200) filter200.addEventListener("click", () => SkyGuard.Audit.renderTable(200));
  if (filter403) filter403.addEventListener("click", () => SkyGuard.Audit.renderTable(403));
  if (filter422) filter422.addEventListener("click", () => SkyGuard.Audit.renderTable(422));

  // 10. Search Input
  const searchInput = document.getElementById("searchInput");
  if (searchInput) {
    searchInput.addEventListener("input", e => {
      SkyGuard.State.searchQuery = e.target.value;
      SkyGuard.Map.renderShelters();
    });
  }

  // 11. Status Filter Chips
  document.querySelectorAll(".filter-chips .chip").forEach(chip => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".filter-chips .chip").forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      SkyGuard.State.activeFilter = chip.dataset.status;
      SkyGuard.Map.renderShelters();
    });
  });

  // 12. Feature Toggle Chips
  document.querySelectorAll(".feature-toggles .toggle-chip").forEach(toggle => {
    toggle.addEventListener("click", () => {
      const feat = toggle.dataset.feature;
      if (SkyGuard.State.activeFeatures.has(feat)) {
        SkyGuard.State.activeFeatures.delete(feat);
        toggle.classList.remove("active");
      } else {
        SkyGuard.State.activeFeatures.add(feat);
        toggle.classList.add("active");
      }
      SkyGuard.Map.renderShelters();
    });
  });
};

// Bootstrap application on page load
document.addEventListener("DOMContentLoaded", () => {
  SkyGuard.init();
});
