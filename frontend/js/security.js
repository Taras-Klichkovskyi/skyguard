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
