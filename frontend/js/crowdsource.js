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
    const count = SkyGuard.State.quorumCounts[shelterId] || 1;
    const countText = document.getElementById("quorumCountText");
    const bar = document.getElementById("quorumBarFill");
    const hint = document.getElementById("quorumStatusHint");

    if (!countText || !bar || !hint) return;

    countText.textContent = `${count} / 3 свідків`;
    const pct = Math.min(100, Math.round((count / 3) * 100));
    bar.style.width = `${pct}%`;

    if (count >= SkyGuard.Config.DQ_RULES.DQ3_CONSENSUS_QUORUM) {
      countText.style.color = "#34d399";
      hint.textContent = "✓ Консенсус DQ-3 досягнуто! Статус верифіковано";
    } else {
      countText.style.color = "#fbbf24";
      const remaining = SkyGuard.Config.DQ_RULES.DQ3_CONSENSUS_QUORUM - count;
      hint.textContent = `Потрібно ще ${remaining} підтвердження від свідків поруч`;
    }
  },

  /**
   * Adds an independent witness confirmation to achieve DQ-3 consensus
   */
  addWitnessToQuorum() {
    const id = SkyGuard.State.selectedShelterId;
    if (!id) return;
    const shelter = SkyGuard.State.getShelterById(id);
    if (!shelter) return;

    SkyGuard.State.quorumCounts[id] = (SkyGuard.State.quorumCounts[id] || 1) + 1;
    const current = SkyGuard.State.quorumCounts[id];

    this.updateQuorumDisplay(id);

    if (current >= SkyGuard.Config.DQ_RULES.DQ3_CONSENSUS_QUORUM) {
      shelter.status = "OPEN";
      shelter.confirmed_at = "Щойно (кворум DQ-3 підтверджено)";
      SkyGuard.State.broadcastShelterUpdate(id, "OPEN", shelter.confirmed_at);
      if (SkyGuard.Api && typeof SkyGuard.Api.sendShelterStatusUpdate === "function") {
        SkyGuard.Api.sendShelterStatusUpdate(id, "OPEN");
      }
      SkyGuard.Map.renderShelters();
      SkyGuard.UI.openShelterDetails(id);
      SkyGuard.UI.showToast("🎉 Кворум DQ-3 досягнуто (3/3)! Укриття переведено в статус ВІДЧИНЕНО", "success");
      SkyGuard.Audit.logEvent("QUORUM_DQ3_CONSENSUS_REACHED", `shelter/${id}`, "PUBLIC", 200);
    } else {
      SkyGuard.State.persistShelters();
      const remaining = SkyGuard.Config.DQ_RULES.DQ3_CONSENSUS_QUORUM - current;
      SkyGuard.UI.showToast(`👍 Додано свідка (${current}/3). До консенсусу залишилось: ${remaining}`, "info");
      SkyGuard.Audit.logEvent("CROWDSOURCE_WITNESS_SUBMITTED", `shelter/${id}`, "PUBLIC", 200);
    }
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
   * Submits crowdsource status report with DQ-1 Haversine server-side rule enforcement
   */
  async submitReport() {
    const shelter = SkyGuard.State.getShelterById(SkyGuard.State.selectedShelterId);
    if (!shelter) return;

    const selectedRadio = document.querySelector('input[name="reportStatus"]:checked');
    const selectedStatus = selectedRadio ? selectedRadio.value : "OPEN";

    let dist = 50;
    if (SkyGuard.State.consent && SkyGuard.State.userLocation) {
      dist = SkyGuard.Geo.calculateHaversineDistance(
        SkyGuard.State.userLocation.lat,
        SkyGuard.State.userLocation.lon,
        shelter.lat,
        shelter.lon
      );
    }

    const maxAllowed = SkyGuard.Config.DQ_RULES.DQ1_MAX_DISTANCE_METRES;

    // Enforce Rule DQ-1: Reject if distance > 100 metres (Server Contract: GEOLOCATION_OUT_OF_BOUNDS)
    if (dist > maxAllowed) {
      SkyGuard.Audit.logEvent("FAILED_DQ_422", `shelter/${shelter.id}`, "PUBLIC", 422);
      SkyGuard.UI.showToast(
        `⛔ Помилка HTTP 422 GEOLOCATION_OUT_OF_BOUNDS: Відхилено за правилом DQ-1 (дистанція ${SkyGuard.Geo.formatDistance(dist)} > ${maxAllowed} м)!`,
        "error"
      );
      const modal = document.getElementById("reportModal");
      if (modal) modal.classList.remove("active");
      return;
    }

    // Success 200 OK
    shelter.status = selectedStatus;
    shelter.confirmed_at = "Щойно (краудсорсинг підтверджено)";
    if (selectedStatus === "OPEN") {
      shelter.current_occupancy = Math.min(shelter.capacity, shelter.current_occupancy + 15);
    } else if (selectedStatus === "CLOSED") {
      shelter.current_occupancy = 0;
    }

    // Broadcast across tabs in real-time
    SkyGuard.State.broadcastShelterUpdate(shelter.id, selectedStatus, shelter.confirmed_at);
    if (SkyGuard.Api && typeof SkyGuard.Api.sendShelterStatusUpdate === "function") {
      SkyGuard.Api.sendShelterStatusUpdate(shelter.id, selectedStatus);
    }

    SkyGuard.Audit.logEvent("CROWDSOURCE_STATUS_UPDATE", `shelter/${shelter.id}`, "PUBLIC", 200);
    SkyGuard.UI.showToast(`✓ Статус оновлено на ${selectedStatus} (200 OK)! Подію внесено в аудит`, "success");

    SkyGuard.Map.renderShelters();
    SkyGuard.UI.openShelterDetails(shelter.id);
    SkyGuard.UI.updateStats();

    const modal = document.getElementById("reportModal");
    if (modal) modal.classList.remove("active");
  }
};
