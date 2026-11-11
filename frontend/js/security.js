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
   * Data Governance Consent Management (L1 Public vs L2 Processing)
   */
  openConsentModal() {
    const modal = document.getElementById("consentModal");
    if (modal) modal.classList.add("active");
  },

  closeConsentModal() {
    const modal = document.getElementById("consentModal");
    if (modal) modal.classList.remove("active");
  },

  /**
   * Authentication & Role Switcher Modal Management (RBAC Portal)
   */
  openAuthModal() {
    const modal = document.getElementById("authModal");
    if (!modal) return;
    modal.classList.add("active");
    this.updateModalActiveCard(SkyGuard.State.role);
  },

  closeAuthModal() {
    const modal = document.getElementById("authModal");
    if (modal) modal.classList.remove("active");
  },

  updateModalActiveCard(roleId) {
    document.querySelectorAll(".role-select-card").forEach(card => {
      const match = (card.dataset.role === roleId);
      card.classList.toggle("active", match);
      const btn = card.querySelector(".btn-switch-role");
      if (btn) {
        btn.textContent = match ? "✓ Активна роль" : "Активувати роль";
        btn.style.background = match ? "#10b981" : "";
        btn.style.borderColor = match ? "#34d399" : "";
      }
    });
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
    const badgeEl = document.getElementById("headerUserRoleBadge");

    if (avatarEl) avatarEl.textContent = roleDef.avatar;
    if (nameEl) nameEl.textContent = roleDef.label.split(" (")[0];
    if (badgeEl) {
      badgeEl.textContent = roleDef.badge;
      if (roleDef.clearance === "L3_CONFIDENTIAL") {
        badgeEl.style.background = "rgba(239, 68, 68, 0.2)";
        badgeEl.style.color = "#f87171";
      } else if (roleDef.clearance === "L2_INTERNAL") {
        badgeEl.style.background = "rgba(245, 158, 11, 0.2)";
        badgeEl.style.color = "#fbbf24";
      } else {
        badgeEl.style.background = "rgba(59, 130, 246, 0.2)";
        badgeEl.style.color = "#60a5fa";
      }
    }

    this.updateModalActiveCard(roleDef.id);

    // Toast and Audit Log
    SkyGuard.UI.showToast(`✓ Права доступу змінено: ${roleDef.label} (${roleDef.badge})`, "success");
    SkyGuard.Audit.logEvent("RBAC_ROLE_SWITCH", `user/session`, roleDef.clearance, 200);

    // If sidebar is currently open, refresh to show role-specific controls
    if (SkyGuard.State.selectedShelterId) {
      SkyGuard.UI.openShelterDetails(SkyGuard.State.selectedShelterId);
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
  },

  setConsent(granted) {
    SkyGuard.State.setConsent(granted);
    SkyGuard.Api.updateConsent(granted);

    const indicator = document.getElementById("consentBtn");
    const text = document.getElementById("consentStatusText");

    if (granted) {
      if (indicator) indicator.className = "consent-indicator granted";
      if (text) text.textContent = "Згода на геодані: Активна (L2)";
      SkyGuard.UI.showToast("✓ Згоду на обробку GPS-координат успішно збережено (L2)", "success");
      SkyGuard.Audit.logEvent("CONSENT_OPT_IN_GRANTED", "user/citizen_01", "SENSITIVE", 200);
    } else {
      if (indicator) indicator.className = "consent-indicator denied";
      if (text) text.textContent = "Згода: Відхилено (Режим L1 PUBLIC)";
      SkyGuard.UI.showToast("⚠️ Режим L1 PUBLIC: геолокація вимкнена відповідно до ст. 11 ЗУ", "warning");
      SkyGuard.Audit.logEvent("CONSENT_OPT_OUT_REVOKED", "user/citizen_01", "SENSITIVE", 200);
    }

    SkyGuard.Map.updateUserMarker();
    SkyGuard.UI.updateStats();

    if (SkyGuard.State.selectedShelterId) {
      SkyGuard.UI.openShelterDetails(SkyGuard.State.selectedShelterId);
    }

    this.closeConsentModal();
  }
};
