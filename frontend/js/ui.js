/**
 * SkyGuard — User Interface Controller (Sidebar, Stats, Toasts, Air Raid Alert)
 * Discipline: ПІС 2026 | Group: ОІ-33 | Team: corelogic
 * Module: js/ui.js
 */

window.SkyGuard = window.SkyGuard || {};

SkyGuard.UI = {
  /**
   * Displays temporary toast notification
   */
  showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    if (!container) return;

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
  },

  /**
   * Updates quick statistics counter in bottom banner
   */
  updateStats() {
    const total = SkyGuard.State.shelters.length;
    const open = SkyGuard.State.shelters.filter(s => s.status === "OPEN").length;
    const capacity = SkyGuard.State.shelters.reduce((acc, s) => acc + s.capacity, 0);

    const elTotal = document.getElementById("statsTotal");
    const elOpen = document.getElementById("statsOpen");
    const elCap = document.getElementById("statsCapacity");
    const elMode = document.getElementById("statsMode");

    if (elTotal) elTotal.textContent = total;
    if (elOpen) elOpen.textContent = open;
    if (elCap) elCap.textContent = capacity.toLocaleString("uk-UA");
    if (elMode) {
      elMode.textContent = SkyGuard.State.alarmActive 
        ? "🚨 ПОВІТРЯНА ТРИВОГА" 
        : (SkyGuard.State.consent ? "Штатний (L1/L2)" : "Обмежений (L1)");
    }
  },

  /**
   * Opens sidebar with full shelter information and privacy gates (L1/L2/L3)
   */
  openShelterDetails(shelterId) {
    SkyGuard.State.setSelectedShelter(shelterId);
    const shelter = SkyGuard.State.getShelterById(shelterId);
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

    if (title) title.textContent = shelter.name;
    if (address) address.innerHTML = `📍 ${shelter.address} <span style="color: var(--text-dim);">(${shelter.district} р-н)</span>`;
    if (confTime) confTime.textContent = `Останнє підтвердження: ${shelter.confirmed_at}`;

    // Status Badge
    if (badge) {
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
    }

    // Occupancy
    if (occText) occText.textContent = `${shelter.current_occupancy} / ${shelter.capacity}`;
    if (occBar) {
      const pct = Math.min(100, Math.round((shelter.current_occupancy / shelter.capacity) * 100));
      occBar.style.width = `${pct}%`;
    }

    // Distance & Navigation Card
    if (distEl && routeBtn && routeEstText) {
      if (SkyGuard.State.consent && SkyGuard.State.userLocation) {
        const dist = SkyGuard.Geo.calculateHaversineDistance(
          SkyGuard.State.userLocation.lat,
          SkyGuard.State.userLocation.lon,
          shelter.lat,
          shelter.lon
        );
        const mins = SkyGuard.Geo.calculateWalkingMinutes(dist);
        distEl.innerHTML = `🎯 <b>${SkyGuard.Geo.formatDistance(dist)}</b> від вашої позиції`;
        distEl.style.display = "inline-flex";
        routeEstText.textContent = `🚶 ~${mins} хв пішки (${SkyGuard.Geo.formatDistance(dist)})`;
        routeBtn.style.display = "block";
        document.getElementById("routeCard").style.display = "block";
      } else {
        distEl.innerHTML = `🔒 <i>Відстань приховано (потрібна згода на GPS)</i>`;
        distEl.style.display = "inline-flex";
        document.getElementById("routeCard").style.display = "none";
      }
    }

    // Quorum Consensus Card (DQ-3)
    SkyGuard.Crowdsource.updateQuorumDisplay(shelter.id);

    // Amenities Grid
    const amenitiesGrid = document.getElementById("detailAmenitiesGrid");
    if (amenitiesGrid) {
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
    }

    // Commander (L2) Privacy Gate
    const commanderContent = document.getElementById("commanderDetailsContent");
    if (commanderContent) {
      if (SkyGuard.State.consent || SkyGuard.State.role !== "ANONYMOUS") {
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
    }

    // Telemetry (L3) Gate
    const isPrivileged = ["MANAGER", "OPERATOR", "AUDITOR"].includes(SkyGuard.State.role);
    const telemetryContent = document.getElementById("telemetryDetailsContent");
    if (telemetryContent) {
      if (isPrivileged) {
        telemetryContent.className = "";
        document.getElementById("detailLockStatus").textContent = `Стан: ${shelter.lock.state} · Батарея: ${shelter.lock.battery}`;
        document.getElementById("detailLockId").textContent = `Модуль: ${shelter.lock.id} (Сигнал: ${shelter.lock.rssi})`;
      } else {
        telemetryContent.className = "blurred-content";
        document.getElementById("detailLockStatus").textContent = `Стан: •••••••• · Батарея: ••%`;
        document.getElementById("detailLockId").textContent = `Модуль: LOCK-••••-••• (Захищено RBAC L3)`;
      }
    }

    if (sidebar) sidebar.classList.add("open");
  },

  /**
   * Closes details sidebar
   */
  closeShelterDetails() {
    const sidebar = document.getElementById("detailsSidebar");
    if (sidebar) sidebar.classList.remove("open");
    SkyGuard.Map.clearRouteLine();
  },

  /**
   * Toggles Air Raid Siren Alarm Mode (🚨)
   */
  toggleAlarmMode() {
    SkyGuard.State.setAlarmActive(!SkyGuard.State.alarmActive);
    const banner = document.getElementById("alertBanner");
    const triggerBtn = document.getElementById("btnAlarmTrigger");
    const triggerText = document.getElementById("alarmBtnText");

    if (SkyGuard.State.alarmActive) {
      if (banner) banner.classList.add("active");
      if (triggerBtn) triggerBtn.classList.add("alarm-active");
      if (triggerText) triggerText.textContent = "Вимкнути тривогу";

      // Filter map strictly to OPEN shelters
      SkyGuard.State.activeFilter = "OPEN";
      document.querySelectorAll(".filter-chips .chip").forEach(c => {
        c.classList.toggle("active", c.dataset.status === "OPEN");
      });

      // Auto-find nearest open shelter
      const openShelters = SkyGuard.State.shelters.filter(s => s.status === "OPEN");
      if (openShelters.length > 0 && SkyGuard.State.userLocation) {
        let nearest = openShelters[0];
        let minDist = SkyGuard.Geo.calculateHaversineDistance(
          SkyGuard.State.userLocation.lat,
          SkyGuard.State.userLocation.lon,
          nearest.lat,
          nearest.lon
        );

        openShelters.forEach(s => {
          const d = SkyGuard.Geo.calculateHaversineDistance(
            SkyGuard.State.userLocation.lat,
            SkyGuard.State.userLocation.lon,
            s.lat,
            s.lon
          );
          if (d < minDist) {
            minDist = d;
            nearest = s;
          }
        });

        // Auto-route and open details
        SkyGuard.Map.renderShelters();
        this.openShelterDetails(nearest.id);
        SkyGuard.Map.drawRouteToShelter(nearest.id);

        this.showToast(
          `🚨 ПОВІТРЯНА ТРИВОГА! Найближче укриття: ${nearest.name} (${SkyGuard.Geo.formatDistance(minDist)})`,
          "error"
        );
      }

      SkyGuard.Audit.logEvent("AIR_RAID_ALERT_ACTIVATED", "dsns/lviv_region", "SENSITIVE", 200);
    } else {
      if (banner) banner.classList.remove("active");
      if (triggerBtn) triggerBtn.classList.remove("alarm-active");
      if (triggerText) triggerText.textContent = "Симуляція тривоги";

      SkyGuard.Map.clearRouteLine();
      SkyGuard.State.activeFilter = "ALL";
      document.querySelectorAll(".filter-chips .chip").forEach(c => {
        c.classList.toggle("active", c.dataset.status === "ALL");
      });

      SkyGuard.Map.renderShelters();
      this.showToast("✓ Відбій повітряної тривоги. Відновлено штатний режим роботи", "success");
      SkyGuard.Audit.logEvent("AIR_RAID_ALERT_DEACTIVATED", "dsns/lviv_region", "INTERNAL", 200);
    }

    this.updateStats();
  }
};
