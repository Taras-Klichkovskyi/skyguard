/**
 * SkyGuard — Crowdsourcing & Data Quality Validation Engine (DQ-1 & DQ-3)
 * Discipline: ПІС 2026 | Group: ОІ-33 | Team: corelogic
 * Module: js/crowdsource.js
 */

window.SkyGuard = window.SkyGuard || {};

SkyGuard.Crowdsource = {
  /**
   * Updates visual progress bar of DQ-3 Quorum consensus for current shelter
   */
  updateQuorumDisplay(shelterId) {
    const count = (typeof SkyGuard.State.quorumCounts[shelterId] === "number") ? SkyGuard.State.quorumCounts[shelterId] : 0;
    const countText = document.getElementById("quorumCountText");
    const bar = document.getElementById("quorumBarFill");
    const hint = document.getElementById("quorumStatusHint");
    const btn = document.getElementById("btnAddWitnessBtn");

    if (!countText || !bar || !hint) return;

    countText.textContent = `${count} / 3 свідків`;
    const pct = Math.min(100, Math.round((count / 3) * 100));
    bar.style.width = `${pct}%`;

    if (btn) {
      btn.textContent = "+1 Підтвердити як свідок";
      btn.style.opacity = "1";
      btn.title = "Надіслати власне спостереження на сервер (DQ-1 ≤ 100 м, кворум DQ-3)";
    }

    if (count >= SkyGuard.Config.DQ_RULES.DQ3_CONSENSUS_QUORUM) {
      countText.style.color = "#34d399";
      hint.textContent = "✓ Консенсус DQ-3 досягнуто! Статус верифіковано";
    } else if (count === 0) {
      countText.style.color = "#94a3b8";
      hint.textContent = "Потрібно 3 незалежні свідки за 15 хв (або 1 верифікований волонтер)";
    } else {
      countText.style.color = "#fbbf24";
      const remaining = SkyGuard.Config.DQ_RULES.DQ3_CONSENSUS_QUORUM - count;
      hint.textContent = `Потрібно ще ${remaining} підтвердження від свідків поруч`;
    }
  },

  /**
   * "+1 witness": an independent confirmation is just another report checked by the server
   * (one user = one vote, DQ-1 ≤ 100 m, quorum DQ-3), so it uses the same dialog.
   */
  addWitnessToQuorum() {
    this.openReportModal();
  },

  /**
   * Opens crowdsourcing modal with real-time Haversine DQ-1 validation check
   */
  openReportModal() {
    const shelterId = SkyGuard.State.selectedShelterId;
    if (!shelterId) return;
    const shelter = SkyGuard.State.getShelterById(shelterId);
    if (!shelter) return;

    const titleEl = document.getElementById("reportModalShelterName");
    const distEl = document.getElementById("reportModalDistanceCheck");
    const dqWarning = document.getElementById("dqWarningBox");

    if (titleEl) titleEl.textContent = shelter.name;

    let dist = 50; // default simulation within bounds
    if (SkyGuard.State.consent && SkyGuard.State.userLocation) {
      dist = SkyGuard.Geo.calculateHaversineDistance(
        SkyGuard.State.userLocation.lat,
        SkyGuard.State.userLocation.lon,
        shelter.lat,
        shelter.lon
      );
    }

    if (distEl) {
      distEl.innerHTML = `Розрахована відстань за формулою Haversine: <b>${SkyGuard.Geo.formatDistance(dist)}</b>`;
    }

    // Check DQ-1 rule (<= 100m)
    const maxAllowed = SkyGuard.Config.DQ_RULES.DQ1_MAX_DISTANCE_METRES;
    if (dist > maxAllowed && dqWarning) {
      dqWarning.style.display = "block";
      dqWarning.innerHTML = `⚠️ <b>Порушення правила якості DQ-1:</b> Ваша дистанція до об'єкта становить <b>${SkyGuard.Geo.formatDistance(dist)} (> ${maxAllowed} м)</b>. Згідно з політикою Data Governance, звіт буде відхилено сервером із кодом <b>HTTP 422 Unprocessable Entity</b> для запобігання фейковим оновленням.`;
    } else if (dqWarning) {
      dqWarning.style.display = "none";
    }

    const modal = document.getElementById("reportModal");
    if (modal) modal.classList.add("active");
  },

  /**
   * Submits a crowdsourced report. The server is the authority: it measures the distance
   * (DQ-1), checks freshness (DQ-2) and the quorum (DQ-3); the UI only shows its verdict.
   */
  async submitReport() {
    const shelter = SkyGuard.State.getShelterById(SkyGuard.State.selectedShelterId);
    if (!shelter) return;
    const modal = document.getElementById("reportModal");

    if (!SkyGuard.State.consent || !SkyGuard.State.userLocation) {
      if (modal) modal.classList.remove("active");
      SkyGuard.UI.showToast("🔒 Для звіту потрібна згода на обробку GPS", "warning");
      SkyGuard.Security.openConsentModal();
      return;
    }

    const selectedRadio = document.querySelector('input[name="reportStatus"]:checked');
    const selectedStatus = selectedRadio ? selectedRadio.value : "OPEN";
    const loc = SkyGuard.State.userLocation;

    const result = await SkyGuard.Api.submitStatusReport(shelter.backendId || shelter.id, {
      status: (selectedStatus === "LIMITED" ? "FULL" : selectedStatus),
      latitude: loc.lat,
      longitude: loc.lon,
      comment: "Краудсорс-звіт мешканця"
    });
    if (modal) modal.classList.remove("active");

    if (result.success) {
      const res = result.data;
      SkyGuard.State.quorumCounts[shelter.id] = res.quorum ? res.quorum.collected : 0;
      if (res.applied) {
        this.applyServerFeature(shelter, res.shelter, "кворум DQ-3 підтверджено");
        SkyGuard.UI.showToast(`✓ 200 OK · кворум DQ-3 досягнуто (вага ${res.quorum.collected} з ${res.quorum.required}): статус застосовано`, "success");
      } else {
        SkyGuard.UI.showToast(`⏳ 200 OK · звіт прийнято (${Math.round(res.distance_m)} м): потребує підтвердження ${res.quorum.collected}/${res.quorum.required}`, "info");
      }
      this.updateQuorumDisplay(shelter.id);
      SkyGuard.UI.openShelterDetails(shelter.id);
      return;
    }

    const err = result.error || {};
    const ref = err.audit_entry_id ? ` · запис аудиту #${err.audit_entry_id}` : "";
    if (result.offline) {
      SkyGuard.UI.showToast("⚠️ Сервер недоступний: звіт не надіслано", "error");
    } else if (result.status === 422) {
      SkyGuard.UI.showToast(`⛔ HTTP 422 ${err.error}: ${err.message}${ref}`, "error");
    } else if (result.status === 403 && err.error === "DENIED_403_CONSENT") {
      SkyGuard.UI.showToast(`🔒 HTTP 403: ${err.message}${ref}`, "warning");
      SkyGuard.Security.openConsentModal();
    } else if (result.status === 403) {
      SkyGuard.UI.showToast(`🚫 HTTP 403 ${err.error}: роль ${err.role} не може подавати звіти${ref}`, "error");
    } else if (result.status === 401) {
      SkyGuard.UI.showToast("🔐 HTTP 401: увійдіть, щоб подати звіт", "warning");
    } else if (result.status === 429) {
      SkyGuard.UI.showToast(`⏳ HTTP 429: ${err.message}`, "warning");
    } else {
      SkyGuard.UI.showToast(`⚠️ HTTP ${result.status}: ${err.message || "помилка сервера"}`, "error");
    }
  },

  /** Copies the server's public view of a shelter (GeoJSON Feature) into the map state. */
  applyServerFeature(shelter, feature, note) {
    if (!feature || !feature.properties) return;
    const p = feature.properties;
    shelter.status = p.status === "FULL" ? "LIMITED" : p.status;
    if (typeof p.occupancy === "number") shelter.current_occupancy = p.occupancy;
    else if (shelter.status === "CLOSED") shelter.current_occupancy = 0;
    shelter.confirmed_at = `Щойно (${note})`;
    SkyGuard.State.persistShelters();
    SkyGuard.Map.renderShelters();
    SkyGuard.UI.updateStats();
  }
};
