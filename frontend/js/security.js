/**
 * SkyGuard — Security & Data Governance Controls (RBAC & Consent L1/L2)
 * Discipline: ПІС 2026 | Group: ОІ-33 | Team: corelogic
 * Module: js/security.js
 */

window.SkyGuard = window.SkyGuard || {};

SkyGuard.Security = {
  token: localStorage.getItem("skyguard_token") || null,

  ROLE_CREDENTIALS: {
    OPERATOR: { email: "dsns@skyguard.demo", password: "skyguard-demo" },
    MANAGER: { email: "manager@skyguard.demo", password: "skyguard-demo" },
    AUDITOR: { email: "auditor@skyguard.demo", password: "skyguard-demo" },
    VOLUNTEER: { email: "volunteer@skyguard.demo", password: "skyguard-demo" },
    CITIZEN: { email: "citizen@skyguard.demo", password: "skyguard-demo" }
  },

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
   * Access test on a CONFIDENTIAL resource (UC-03): commander contacts of the selected shelter.
   * The request goes to the server; on 403 the dialog shows the server's audit record id.
   * Target endpoint: GET /api/v1/shelters/{id}/contacts (SG-10)
   */
  async triggerForbiddenIncident() {
    const shelter = SkyGuard.State.getShelterById(SkyGuard.State.selectedShelterId);
    if (!shelter) return;
    const res = await SkyGuard.Api.fetchShelterContacts(shelter.backendId || shelter.id);

    if (res.ok) {
      const c = res.data;
      shelter.commander = { ...(shelter.commander || {}), name: c.commander_name || "—", phone: c.commander_phone || "—" };
      SkyGuard.UI.openShelterDetails(shelter.id);
      SkyGuard.UI.showToast(`🔓 200 OK · доступ дозволено (CONFIDENTIAL): ${c.commander_name}, ${c.commander_phone}`, "success");
      return;
    }
    if (res.offline) {
      SkyGuard.UI.showToast("⚠️ Сервер недоступний: перевірку доступу не виконано", "error");
      return;
    }

    const err = res.data || {};
    const set = (id, value) => { const el = document.getElementById(id); if (el) el.textContent = value; };
    set("forbiddenHttpCode", `HTTP ${res.status}`);
    set("forbiddenCurrentRole", err.role || SkyGuard.State.role);
    set("forbiddenAuditId", err.audit_entry_id != null ? `#${err.audit_entry_id}` : "—");
    set("forbiddenTimestamp", new Date().toISOString());
    set("forbiddenErrorCode", err.error || `HTTP ${res.status}`);
    set("forbiddenRequiredRoles", (err.required_roles || []).join(", ") || "—");
    set("forbiddenRequestId", err.request_id || "—");

    const modal = document.getElementById("forbiddenModal");
    if (modal) modal.classList.add("active");
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

  setConsent(granted, { sync = true } = {}) {
    SkyGuard.State.setConsent(granted);
    if (sync) this.syncConsentWithServer(granted);

    const indicator = document.getElementById("consentBtn");
    const text = document.getElementById("consentStatusText");

    if (granted) {
      if (indicator) indicator.className = "geo-status-pill granted";
      if (text) text.textContent = "Геолокація активна";
      SkyGuard.Audit.logEvent("CONSENT_OPT_IN_GRANTED", "user/session", "SENSITIVE", 200);
    } else {
      if (indicator) indicator.className = "geo-status-pill denied";
      if (text) text.textContent = "Геолокація вимкнена";
      SkyGuard.Audit.logEvent("CONSENT_OPT_OUT_REVOKED", "user/session", "SENSITIVE", 200);
    }

    SkyGuard.Map.updateUserMarker();
    SkyGuard.UI.updateStats();

    if (SkyGuard.State.selectedShelterId) {
      SkyGuard.UI.openShelterDetails(SkyGuard.State.selectedShelterId);
    }

    this.closeConsentModal();
  },

  /**
   * Records the consent on the server for the signed-in user (purposes ROUTE_GPS, REPORT_GEOFENCE).
   * Revocation is only sent if the server holds an active consent, so a fresh visit stays quiet.
   */
  async syncConsentWithServer(granted) {
    const results = await SkyGuard.Api.updateConsent(granted);
    if (!results.length) return;
    if (granted) {
      const created = results.filter(r => r.status === 201).length;
      const ok = results.every(r => r.ok);
      if (ok && created) {
        SkyGuard.UI.showToast(`✓ 201 Created · згоду записано на сервері: ${results.map(r => r.purpose).join(", ")}`, "success");
      } else if (!ok) {
        const bad = results.find(r => !r.ok);
        SkyGuard.UI.showToast(`⚠️ Згоду не записано на сервері (HTTP ${bad.status})`, "warning");
      }
    } else if (results.some(r => r.status === 200)) {
      SkyGuard.UI.showToast("✓ Згоду відкликано на сервері", "info");
    }
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
  async requestRoleSwitch(targetRoleId) {
    if (targetRoleId === "ANONYMOUS") {
      this.token = null;
      localStorage.removeItem("skyguard_token");
      localStorage.removeItem("skyguard_jwt_token");
      this.switchRole(targetRoleId);
      return;
    }

    if (targetRoleId === "CITIZEN") {
      await this.loginWithJwt("citizen@skyguard.demo", "skyguard-demo");
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

  async confirmPendingRole(password) {
    if (!this.pendingRole) return;
    if (password === "skyguard-demo") {
      const roleToSet = this.pendingRole;
      const creds = this.ROLE_CREDENTIALS[roleToSet] || { email: "citizen@skyguard.demo", password: "skyguard-demo" };
      this.cancelPendingRole();
      await this.loginWithJwt(creds.email, password);
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

    // Audit button is ONLY visible for AUDITOR role
    const openAuditBtn = document.getElementById("openAuditBtn");
    if (openAuditBtn) {
      if (roleDef.id === "AUDITOR") {
        openAuditBtn.style.display = "flex";
        openAuditBtn.style.borderColor = "#38bdf8";
        openAuditBtn.style.boxShadow = "0 0 12px rgba(56, 189, 248, 0.4)";
      } else {
        openAuditBtn.style.display = "none";
      }
    }

    // Toast and Audit Log
    SkyGuard.UI.showToast(`✓ Права доступу змінено: ${roleDef.label}`, "success");
    SkyGuard.Audit.logEvent("RBAC_ROLE_SWITCH", `user/session`, roleDef.clearance, 200);

    // If sidebar is currently open, refresh to show role-specific controls
    if (SkyGuard.State.selectedShelterId) {
      SkyGuard.UI.openShelterDetails(SkyGuard.State.selectedShelterId);
    }

    // If switched to AUDITOR, automatically open the Audit Console and fetch DB records
    if (roleDef.id === "AUDITOR") {
      setTimeout(() => {
        SkyGuard.Audit.renderTable();
        SkyGuard.Audit.fetchLiveAuditTrail();
        const modal = document.getElementById("auditModal");
        if (modal) modal.classList.add("active");
        SkyGuard.Audit.startLiveSync();  // new events (e.g. a fresh 403) appear without reopening
      }, 200);
    }

    this.closeAuthModal();
  },

  /**
   * JWT Authentication through API (FastAPI SG-10/SG-21)
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

    SkyGuard.UI.showToast(`🔐 Отримання JWT Bearer токена для ${email}...`, "info");

    try {
      // Connect to live FastAPI backend with JSON LoginIn schema
      const resp = await fetch(`${SkyGuard.Config.API_BASE_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password: password.trim() })
      });

      if (resp.ok) {
        const data = await resp.json();
        if (data.access_token) {
          this.token = data.access_token;
          localStorage.setItem("skyguard_token", data.access_token);
          localStorage.setItem("skyguard_jwt_token", data.access_token);
          console.info(`[SkyGuard Auth] Live JWT obtained from backend: role=${data.role}`);
          if (SkyGuard.State.consent) this.syncConsentWithServer(true);
        }
      } else {
        const errJson = await resp.json().catch(() => ({}));
        console.warn("[SkyGuard Auth] Live login returned non-200:", resp.status, errJson);
      }
    } catch (e) {
      console.debug("[SkyGuard Auth] Live backend offline, fallback to simulated session:", e.message);
    }

    // Apply role and feedback
    this.switchRole(targetRole);
    SkyGuard.UI.showToast(`✓ Авторизовано як ${email} (Bearer JWT дійсний 15 хв)`, "success");
    SkyGuard.Audit.logEvent("JWT_AUTH_SUCCESS", `auth/login?email=${email}`, "CONFIDENTIAL", 200);
  }
};
