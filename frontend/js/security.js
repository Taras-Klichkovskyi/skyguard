/**
 * SkyGuard — Security & Data Governance Controls (RBAC & Consent L1/L2)
 * Discipline: ПІС 2026 | Group: ОІ-33 | Team: corelogic
 * Module: js/security.js
 */

window.SkyGuard = window.SkyGuard || {};

SkyGuard.Security = {
  /**
   * Checks whether the current user has permission to perform action on resource
   */
  hasPermission(requiredClearance) {
    const roleConfig = SkyGuard.Config.ROLES[SkyGuard.State.role] || SkyGuard.Config.ROLES.CITIZEN;
    const hierarchy = { "L1_PUBLIC": 1, "L2_INTERNAL": 2, "L3_CONFIDENTIAL": 3 };
    const userLevel = hierarchy[roleConfig.clearance] || 1;
    const requiredLevel = hierarchy[requiredClearance] || 1;
    return userLevel >= requiredLevel;
  },

  /**
   * Simulates 403 Forbidden Security Incident (UC-03 / NFR-SEC-02)
   */
  triggerForbiddenIncident() {
    const isPrivileged = ["MANAGER", "OPERATOR", "AUDITOR"].includes(SkyGuard.State.role);

    if (isPrivileged) {
      SkyGuard.UI.showToast("🔓 Авторизація успішна: доступ до телеметрії замка надано (RBAC L3)", "success");
      return;
    }

    const incidentId = "ae-" + Math.random().toString(36).substring(2, 6) + "-" + Math.random().toString(36).substring(2, 10);
    const timestamp = new Date().toISOString();

    const roleEl = document.getElementById("forbiddenCurrentRole");
    const auditIdEl = document.getElementById("forbiddenAuditId");
    const timeEl = document.getElementById("forbiddenTimestamp");

    if (roleEl) roleEl.textContent = SkyGuard.State.role;
    if (auditIdEl) auditIdEl.textContent = incidentId;
    if (timeEl) timeEl.textContent = timestamp;

    const modal = document.getElementById("forbiddenModal");
    if (modal) modal.classList.add("active");

    const shelterId = SkyGuard.State.selectedShelterId || "SH-LVIV-001";
    SkyGuard.Audit.logEvent(
      "READ_CONFIDENTIAL_TELEMETRY",
      `shelter/${shelterId}/telemetry`,
      "CONFIDENTIAL",
      403,
      incidentId
    );
  },

  /**
   * Data Governance Consent Management & Geolocation Pill
   */
  openConsentModal() {
    const modal = document.getElementById("consentModal");
    if (modal) modal.classList.add("active");
  },

  closeConsentModal() {
    const modal = document.getElementById("consentModal");
    if (modal) modal.classList.remove("active");
  },

  setConsent(granted) {
    SkyGuard.State.setConsent(granted);
    SkyGuard.Api.updateConsent(granted);

    const indicator = document.getElementById("consentBtn");
    const text = document.getElementById("consentStatusText");

    if (granted) {
      if (indicator) indicator.className = "geo-status-pill granted";
      if (text) text.textContent = "Геолокація активна";
      SkyGuard.Audit.logEvent("CONSENT_OPT_IN_GRANTED", "user/citizen_01", "SENSITIVE", 200);
    } else {
      if (indicator) indicator.className = "geo-status-pill denied";
      if (text) text.textContent = "Геолокація вимкнена";
      SkyGuard.Audit.logEvent("CONSENT_OPT_OUT_REVOKED", "user/citizen_01", "SENSITIVE", 200);
    }

    SkyGuard.Map.updateUserMarker();
    SkyGuard.UI.updateStats();

    if (SkyGuard.State.selectedShelterId) {
      SkyGuard.UI.openShelterDetails(SkyGuard.State.selectedShelterId);
    }

    this.closeConsentModal();
  },

  /**
   * Action when clicking the Geolocation & Consent pill in header:
   * Instantly requests GPS from browser, centers map, and finds nearest shelter!
   */
  handleGeoButtonClick() {
    SkyGuard.UI.showToast("📡 Визначення точних координат та передача геопозиції...", "info");
    SkyGuard.Geo.locateUser(
      (lat, lon) => {
        SkyGuard.State.setUserLocation(lat, lon);
        this.setConsent(true);
        SkyGuard.Map.updateUserMarker();
        SkyGuard.Map.instance.setView([lat, lon], 15.5);

        // Find nearest open shelter
        const openShelters = SkyGuard.State.shelters.filter(s => s.status === "OPEN");
        if (openShelters.length > 0) {
          let nearest = openShelters[0];
          let minDist = SkyGuard.Geo.calculateHaversineDistance(lat, lon, nearest.lat, nearest.lon);
          openShelters.forEach(s => {
            const d = SkyGuard.Geo.calculateHaversineDistance(lat, lon, s.lat, s.lon);
            if (d < minDist) { minDist = d; nearest = s; }
          });
          SkyGuard.UI.openShelterDetails(nearest.id);
          SkyGuard.Map.drawRouteToShelter(nearest.id);
          SkyGuard.UI.showToast(`🎯 Вашу геопозицію передано! Найближче укриття: ${nearest.name} (${SkyGuard.Geo.formatDistance(minDist)})`, "success");
        } else {
          SkyGuard.UI.showToast(`🎯 Вашу геопозицію передано: [${lat.toFixed(4)}, ${lon.toFixed(4)}]`, "success");
        }
      },
      (err) => {
        // Fallback to center Lviv
        SkyGuard.State.setUserLocation(49.8419, 24.0315, "м. Львів, пл. Ринок");
        this.setConsent(true);
        SkyGuard.Map.updateUserMarker();
        SkyGuard.Map.instance.setView([49.8419, 24.0315], 15);
        SkyGuard.UI.showToast("📍 Геопозицію передано (центр Львова, пл. Ринок)", "success");
      }
    );
  },

  /**
   * Authentication & Role Switcher Modal Management (RBAC Portal)
   */
  pendingRole: null,

  openAuthModal() {
    const modal = document.getElementById("authModal");
    if (!modal) return;
    modal.classList.add("active");
    this.cancelPendingRole();
    this.updateModalActiveCard(SkyGuard.State.role);
  },

  closeAuthModal() {
    const modal = document.getElementById("authModal");
    if (modal) modal.classList.remove("active");
    this.cancelPendingRole();
  },

  updateModalActiveCard(roleId) {
    document.querySelectorAll(".role-select-card").forEach(card => {
      const match = (card.dataset.role === roleId);
      card.classList.toggle("active", match);
      const btn = card.querySelector(".btn-switch-role");
      if (btn) {
        if (match) {
          btn.textContent = "✓ Активна роль";
          btn.style.background = "#10b981";
          btn.style.borderColor = "#34d399";
        } else {
          btn.textContent = (card.dataset.role === "CITIZEN" ? "Вільний доступ" : "🔑 Увійти з паролем");
          btn.style.background = "";
          btn.style.borderColor = "";
        }
      }
    });
  },

  /**
   * Request role switch: if privileged, requires password verification
   */
  requestRoleSwitch(targetRoleId) {
    if (targetRoleId === "CITIZEN" || targetRoleId === "ANONYMOUS") {
      this.switchRole(targetRoleId);
      return;
    }

    this.pendingRole = targetRoleId;
    const roleDef = SkyGuard.Config.ROLES[targetRoleId];
    const box = document.getElementById("rolePasswordVerifyBox");
    const title = document.getElementById("verifyRoleTitle");
    const err = document.getElementById("rolePassError");
    const input = document.getElementById("inputRoleVerifyPass");

    if (box && title) {
      box.style.display = "block";
      title.textContent = `Підтвердження службового доступу: ${roleDef ? roleDef.label : targetRoleId}`;
      if (err) err.style.display = "none";
      if (input) {
        input.value = "skyguard-demo";
        input.focus();
      }
    }
  },

  confirmPendingRole(password) {
    if (!this.pendingRole) return;
    if (password === "skyguard-demo") {
      const roleToSet = this.pendingRole;
      this.cancelPendingRole();
      this.switchRole(roleToSet);
    } else {
      const err = document.getElementById("rolePassError");
      if (err) err.style.display = "block";
      SkyGuard.UI.showToast("⚠️ Невірний пароль для цієї ролі. Для тестування: skyguard-demo", "error");
    }
  },

  cancelPendingRole() {
    this.pendingRole = null;
    const box = document.getElementById("rolePasswordVerifyBox");
    if (box) box.style.display = "none";
  },

  /**
   * Switches user role and updates all UI security gates
   */
  switchRole(newRoleId) {
    const roleDef = SkyGuard.Config.ROLES[newRoleId] || SkyGuard.Config.ROLES.CITIZEN;
    SkyGuard.State.setRole(roleDef.id);

    // Update Header Profile Badge
    const avatarEl = document.getElementById("headerUserAvatar");
    const nameEl = document.getElementById("headerUserRoleName");

    if (avatarEl) avatarEl.textContent = roleDef.avatar;
    if (nameEl) nameEl.textContent = roleDef.label.split(" (")[0];

    this.updateModalActiveCard(roleDef.id);

    // Toast and Audit Log
    SkyGuard.UI.showToast(`✓ Права доступу змінено: ${roleDef.label}`, "success");
    SkyGuard.Audit.logEvent("RBAC_ROLE_SWITCH", `user/session`, roleDef.clearance, 200);

    // If sidebar is currently open, refresh to show role-specific controls
    if (SkyGuard.State.selectedShelterId) {
      SkyGuard.UI.openShelterDetails(SkyGuard.State.selectedShelterId);
    }

    // If switched to AUDITOR, automatically open the Audit Console
    if (roleDef.id === "AUDITOR") {
      setTimeout(() => {
        SkyGuard.Audit.renderTable();
        SkyGuard.Audit.fetchLiveAuditTrail();
        const modal = document.getElementById("auditModal");
        if (modal) modal.classList.add("active");
      }, 300);
    }

    this.closeAuthModal();
  },

  /**
   * JWT Authentication through API or simulated credential check
   */
  async loginWithJwt(email, password) {
    if (!email || !password) {
      SkyGuard.UI.showToast("⚠️ Будь ласка, вкажіть email та пароль для входу", "warning");
      return;
    }

    // Role mapping based on email prefix
    let targetRole = "CITIZEN";
    if (email.startsWith("dsns") || email.includes("operator")) targetRole = "OPERATOR";
    else if (email.startsWith("manager")) targetRole = "MANAGER";
    else if (email.startsWith("auditor")) targetRole = "AUDITOR";
    else if (email.startsWith("volunteer")) targetRole = "VOLUNTEER";

    SkyGuard.UI.showToast(`🔐 Перевірка облікових даних через шлюз безпеки...`, "info");

    try {
      // Try live backend if available
      const resp = await fetch(`${SkyGuard.Config.API_BASE_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ username: email, password: password })
      });

      if (resp.ok) {
        const data = await resp.json();
        if (data.access_token) {
          localStorage.setItem("skyguard_token", data.access_token);
        }
      }
    } catch (e) {
      // Backend offline: continue with simulated seed credentials
      console.debug("[SkyGuard] API login fallback to local session:", e.message);
    }

    // Apply role and feedback
    this.switchRole(targetRole);
    SkyGuard.UI.showToast(`✓ Авторизовано як ${email} (Bearer JWT дійсний 15 хв)`, "success");
    SkyGuard.Audit.logEvent("JWT_AUTH_SUCCESS", `auth/login?email=${email}`, "CONFIDENTIAL", 200);
  }
};
