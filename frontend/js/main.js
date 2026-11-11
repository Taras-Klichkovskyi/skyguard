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
  SkyGuard.Audit.init();

  // 2. Initialize Map & Markers immediately (instant render, zero delay!)
  SkyGuard.Map.init();

  // 3. Update Stats Counter
  SkyGuard.UI.updateStats();

  // 4. Setup Event Listeners
  SkyGuard.bindEvents();

  // 4.1. Restore or acquire initial JWT token for API calls
  const savedToken = localStorage.getItem("skyguard_token");
  if (savedToken) {
    SkyGuard.Security.token = savedToken;
  } else {
    SkyGuard.Security.loginWithJwt("citizen@skyguard.demo", "skyguard-demo").catch(() => {});
  }

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
  // 1. Testing & Simulation Tools Dropdown
  const btnToolsMenu = document.getElementById("btnToolsMenu");
  const toolsDropdown = document.getElementById("toolsDropdown");

  if (btnToolsMenu && toolsDropdown) {
    btnToolsMenu.addEventListener("click", (e) => {
      e.stopPropagation();
      toolsDropdown.classList.toggle("show");
      btnToolsMenu.classList.toggle("active", toolsDropdown.classList.contains("show"));
    });

    document.addEventListener("click", (e) => {
      if (!toolsDropdown.contains(e.target) && e.target !== btnToolsMenu) {
        toolsDropdown.classList.remove("show");
        btnToolsMenu.classList.remove("active");
      }
    });
  }

  // 2. Authentication & Role Switcher Modal (RBAC Portal)
  const btnOpenAuthModal = document.getElementById("btnOpenAuthModal");
  const closeAuthModalBtn = document.getElementById("closeAuthModalBtn");
  const tabBtnRoles = document.getElementById("tabBtnRoles");
  const tabBtnLogin = document.getElementById("tabBtnLogin");
  const tabPaneRoles = document.getElementById("tabPaneRoles");
  const tabPaneLogin = document.getElementById("tabPaneLogin");

  if (btnOpenAuthModal) {
    btnOpenAuthModal.addEventListener("click", () => SkyGuard.Security.openAuthModal());
  }
  if (closeAuthModalBtn) {
    closeAuthModalBtn.addEventListener("click", () => SkyGuard.Security.closeAuthModal());
  }

  // Auth Tabs Switching
  if (tabBtnRoles && tabBtnLogin && tabPaneRoles && tabPaneLogin) {
    tabBtnRoles.addEventListener("click", () => {
      tabBtnRoles.classList.add("active");
      tabBtnLogin.classList.remove("active");
      tabPaneRoles.style.display = "block";
      tabPaneLogin.style.display = "none";
    });

    tabBtnLogin.addEventListener("click", () => {
      tabBtnLogin.classList.add("active");
      tabBtnRoles.classList.remove("active");
      tabPaneLogin.style.display = "block";
      tabPaneRoles.style.display = "none";
    });
  }

  // Fast Role Switch Cards with Password Verification
  document.querySelectorAll(".btn-switch-role").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const role = btn.dataset.role || btn.closest(".role-select-card")?.dataset.role;
      if (role) SkyGuard.Security.requestRoleSwitch(role);
    });
  });

  document.querySelectorAll(".role-select-card").forEach(card => {
    card.addEventListener("click", (e) => {
      if (e.target.closest(".btn-switch-role")) return;
      const role = card.dataset.role;
      if (role) SkyGuard.Security.requestRoleSwitch(role);
    });
  });

  // Password Confirmation Handlers for Privileged Roles
  const btnConfirmRolePass = document.getElementById("btnConfirmRolePass");
  const btnCancelRolePass = document.getElementById("btnCancelRolePass");
  const inputRoleVerifyPass = document.getElementById("inputRoleVerifyPass");

  if (btnConfirmRolePass && inputRoleVerifyPass) {
    btnConfirmRolePass.addEventListener("click", () => {
      SkyGuard.Security.confirmPendingRole(inputRoleVerifyPass.value);
    });
    inputRoleVerifyPass.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        SkyGuard.Security.confirmPendingRole(inputRoleVerifyPass.value);
      }
    });
  }
  if (btnCancelRolePass) {
    btnCancelRolePass.addEventListener("click", () => {
      SkyGuard.Security.cancelPendingRole();
    });
  }

  // JWT Quick Presets
  document.querySelectorAll(".btn-preset-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      const email = pill.dataset.email;
      const inputEmail = document.getElementById("inputAuthEmail");
      const inputPass = document.getElementById("inputAuthPassword");
      if (inputEmail) inputEmail.value = email;
      if (inputPass) inputPass.value = "skyguard-demo";
      SkyGuard.UI.showToast(`Заповнено пресет: ${email}`, "info");
    });
  });

  // Submit JWT Auth
  const btnSubmitJwtAuth = document.getElementById("btnSubmitJwtAuth");
  if (btnSubmitJwtAuth) {
    btnSubmitJwtAuth.addEventListener("click", () => {
      const email = document.getElementById("inputAuthEmail")?.value;
      const pass = document.getElementById("inputAuthPassword")?.value;
      SkyGuard.Security.loginWithJwt(email, pass);
    });
  }

  // Legacy Role Selector (fallback compatibility)
  const roleSelect = document.getElementById("roleSelector");
  if (roleSelect) {
    roleSelect.value = SkyGuard.State.role;
    roleSelect.addEventListener("change", e => {
      SkyGuard.Security.switchRole(e.target.value);
    });
  }

  // 3. Air Raid Alarm Triggers
  const btnAlarm = document.getElementById("btnAlarmTrigger");
  const btnDismissAlert = document.getElementById("btnDismissAlert");
  if (btnAlarm) {
    btnAlarm.addEventListener("click", () => {
      if (toolsDropdown) toolsDropdown.classList.remove("show");
      SkyGuard.UI.toggleAlarmMode();
    });
  }
  if (btnDismissAlert) btnDismissAlert.addEventListener("click", () => SkyGuard.UI.toggleAlarmMode());

  // 4. Role Action Controls (Sidebar)
  const btnManagerApplyStatus = document.getElementById("btnManagerApplyStatus");
  if (btnManagerApplyStatus) {
    btnManagerApplyStatus.addEventListener("click", () => SkyGuard.UI.applyManagerShelterUpdate());
  }

  const btnDsnsForceOpen = document.getElementById("btnDsnsForceOpen");
  const btnDsnsForceClose = document.getElementById("btnDsnsForceClose");
  if (btnDsnsForceOpen) {
    btnDsnsForceOpen.addEventListener("click", () => SkyGuard.UI.forceDsnsStatus("OPEN"));
  }
  if (btnDsnsForceClose) {
    btnDsnsForceClose.addEventListener("click", () => SkyGuard.UI.forceDsnsStatus("CLOSED"));
  }

  // 4b. Smart Geofence Presence Check-in Toggle
  const btnTogglePresence = document.getElementById("btnTogglePresence");
  if (btnTogglePresence) {
    btnTogglePresence.addEventListener("click", () => SkyGuard.UI.toggleGeofencePresence());
  }

  // 5. Geolocation Pill in Header (Click transmits GPS location immediately)
  const consentBtn = document.getElementById("consentBtn");
  const closeConsentBtn = document.getElementById("closeConsentModalBtn");
  const btnGrantConsent = document.getElementById("btnGrantConsent");
  const btnDenyConsent = document.getElementById("btnDenyConsent");

  if (consentBtn) {
    consentBtn.addEventListener("click", () => {
      SkyGuard.Security.handleGeoButtonClick();
    });
  }
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
  SkyGuard.UI.initMobileGestures();

  const btnMobileRoute = document.getElementById("btnMobileRoute");
  const btnMobileExpand = document.getElementById("btnMobileExpand");
  const sheetDragHandle = document.getElementById("sheetDragHandle");

  if (btnMobileRoute) {
    btnMobileRoute.addEventListener("click", () => {
      if (SkyGuard.State.routeLine) {
        SkyGuard.Map.clearRouteLine();
        SkyGuard.UI.showToast("Маршрут скинуто", "info");
      } else if (SkyGuard.State.selectedShelterId) {
        SkyGuard.Map.drawRouteToShelter(SkyGuard.State.selectedShelterId);
      }
    });
  }

  if (btnMobileExpand) {
    btnMobileExpand.addEventListener("click", () => {
      SkyGuard.UI.toggleMobileExpand();
    });
  }

  if (sheetDragHandle) {
    sheetDragHandle.addEventListener("click", () => {
      SkyGuard.UI.toggleMobileExpand();
    });
  }
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
      if (toolsDropdown) toolsDropdown.classList.remove("show");
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

  // 9. Audit Console Modal (SG-11 - Auditor Only)
  const openAuditBtn = document.getElementById("openAuditBtn");
  const closeAuditModalBtn = document.getElementById("closeAuditModalBtn");
  const btnCloseAuditDialog = document.getElementById("btnCloseAuditDialog");
  const btnExportAuditJson = document.getElementById("btnExportAuditJson");

  // Initial visibility check: hidden for citizens, only visible for AUDITOR
  if (openAuditBtn) {
    openAuditBtn.style.display = (SkyGuard.State.role === "AUDITOR" ? "flex" : "none");
    openAuditBtn.addEventListener("click", () => {
      if (toolsDropdown) toolsDropdown.classList.remove("show");
      SkyGuard.Audit.renderTable();
      SkyGuard.Audit.startLiveSync();
      document.getElementById("auditModal").classList.add("active");
    });
  }

  if (closeAuditModalBtn) {
    closeAuditModalBtn.addEventListener("click", () => {
      SkyGuard.Audit.stopLiveSync();
      document.getElementById("auditModal").classList.remove("active");
    });
  }
  if (btnCloseAuditDialog) {
    btnCloseAuditDialog.addEventListener("click", () => {
      SkyGuard.Audit.stopLiveSync();
      document.getElementById("auditModal").classList.remove("active");
    });
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
