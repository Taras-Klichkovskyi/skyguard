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

    // Clear previous toasts on mobile to avoid stacking on screen
    if (window.innerWidth <= 768) {
      container.innerHTML = "";
    }

    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = window.innerWidth <= 768 ? "translateY(-10px)" : "translateX(50px)";
      toast.style.transition = "all 0.3s ease";
      setTimeout(() => toast.remove(), 250);
    }, 2200);
  },

  /**
   * Updates quick statistics counter in bottom banner & header status
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
        : (SkyGuard.State.consent ? "Штатний режим" : "Геолокація вимкнена");
    }

    // Header Status Pill
    const headerPill = document.getElementById("headerStatusPill");
    const headerText = document.getElementById("headerStatusText");
    if (headerPill && headerText) {
      if (SkyGuard.State.alarmActive) {
        headerPill.style.background = "rgba(239, 68, 68, 0.15)";
        headerPill.style.borderColor = "rgba(239, 68, 68, 0.4)";
        headerPill.style.color = "#f87171";
        headerText.textContent = "🚨 Повітряна тривога";
      } else {
        headerPill.style.background = "rgba(16, 185, 129, 0.1)";
        headerPill.style.borderColor = "rgba(16, 185, 129, 0.3)";
        headerPill.style.color = "#34d399";
        headerText.textContent = "Львів · Штатний режим";
      }
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

    // Smart Geofence Presence Card (Anonymous GPS Check-in)
    this.updateGeofencePresence(shelter);

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

    // Commander Privacy Gate (RBAC & Consent Check)
    const commanderContent = document.getElementById("commanderDetailsContent");
    const commanderTag = document.getElementById("commanderClassTag");
    if (commanderContent) {
      if (SkyGuard.State.role === "OPERATOR") {
        commanderContent.className = "";
        document.getElementById("detailCommanderName").textContent = shelter.commander.name;
        document.getElementById("detailCommanderPhone").textContent = `📞 ${shelter.commander.phone}`;
        document.getElementById("detailCommanderId").textContent = `Службовий жетон: ${shelter.commander.id}`;
        if (commanderTag) {
          commanderTag.textContent = "Прямий контакт ДСНС";
          commanderTag.className = "classification-tag tag-l3";
        }
      } else if (SkyGuard.State.role === "MANAGER") {
        commanderContent.className = "";
        document.getElementById("detailCommanderName").textContent = shelter.commander.name;
        document.getElementById("detailCommanderPhone").textContent = `📞 ${shelter.commander.phone}`;
        document.getElementById("detailCommanderId").textContent = `Службовий жетон: ${shelter.commander.id}`;
        if (commanderTag) {
          commanderTag.textContent = "Комендант укриття";
          commanderTag.className = "classification-tag tag-l2";
        }
      } else if (SkyGuard.State.consent && SkyGuard.State.role !== "ANONYMOUS") {
        commanderContent.className = "";
        document.getElementById("detailCommanderName").textContent = shelter.commander.name;
        document.getElementById("detailCommanderPhone").textContent = `📞 ${shelter.commander.phone}`;
        document.getElementById("detailCommanderId").textContent = `Службовий жетон: ${shelter.commander.id}`;
        if (commanderTag) {
          commanderTag.textContent = "Службовий контакт";
          commanderTag.className = "classification-tag tag-l2";
        }
      } else {
        commanderContent.className = "blurred-content";
        document.getElementById("detailCommanderName").textContent = "Ковальчук П. О.";
        document.getElementById("detailCommanderPhone").textContent = "📞 +380 67 ••• •• ••";
        document.getElementById("detailCommanderId").textContent = "Службовий жетон: DSNS-LV-••••";
        if (commanderTag) {
          commanderTag.textContent = "Приховано (увімкніть геопозицію)";
          commanderTag.className = "classification-tag tag-l1";
        }
      }
    }

    // Telemetry Gate
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
        document.getElementById("detailLockId").textContent = `Модуль: LOCK-••••-••• (Службовий доступ)`;
      }
    }

    // Role-Specific Action Control Cards
    const citizenBox = document.getElementById("citizenActionsBox");
    const dsnsBox = document.getElementById("dsnsActionsBox");
    const managerBox = document.getElementById("managerActionsBox");

    if (citizenBox) citizenBox.style.display = "none";
    if (dsnsBox) dsnsBox.style.display = "none";
    if (managerBox) managerBox.style.display = "none";

    if (SkyGuard.State.role === "OPERATOR") {
      if (dsnsBox) dsnsBox.style.display = "block";
    } else if (SkyGuard.State.role === "MANAGER") {
      if (managerBox) {
        managerBox.style.display = "block";
        const statusSelect = document.getElementById("managerStatusSelect");
        const occInput = document.getElementById("managerOccupancyInput");
        if (statusSelect) statusSelect.value = shelter.status;
        if (occInput) {
          occInput.value = shelter.current_occupancy;
          occInput.max = shelter.capacity;
        }
      }
    } else {
      // CITIZEN, VOLUNTEER, AUDITOR, ANONYMOUS
      if (citizenBox) citizenBox.style.display = "flex";
    }

    if (sidebar) {
      sidebar.classList.add("open");
      document.body.classList.add("sidebar-open");
    }
    // Reset bottom sheet to Peek mode on mobile
    if (sidebar) {
      sidebar.classList.remove("expanded");
      const expandBtn = document.getElementById("btnMobileExpand");
      if (expandBtn) expandBtn.textContent = "▲ Деталі";
    }
    const mobileRouteBtn = document.getElementById("btnMobileRoute");
    if (mobileRouteBtn) {
      if (SkyGuard.State.routeLine) {
        mobileRouteBtn.textContent = "✕ Скинути маршрут";
        mobileRouteBtn.classList.add("active");
      } else {
        mobileRouteBtn.textContent = "🚶 Прокласти маршрут";
        mobileRouteBtn.classList.remove("active");
      }
    }
  },

  /**
   * Applies official status & occupancy update as Shelter Manager (No Quorum Required)
   */
  applyManagerShelterUpdate() {
    const shelter = SkyGuard.State.getShelterById(SkyGuard.State.selectedShelterId);
    if (!shelter) return;

    const statusSelect = document.getElementById("managerStatusSelect");
    const occInput = document.getElementById("managerOccupancyInput");

    const newStatus = statusSelect ? statusSelect.value : shelter.status;
    const newOccupancy = occInput ? parseInt(occInput.value, 10) : shelter.current_occupancy;

    shelter.status = newStatus;
    shelter.current_occupancy = isNaN(newOccupancy) ? shelter.current_occupancy : Math.min(newOccupancy, shelter.capacity);
    shelter.confirmed_at = "Щойно (комендант)";

    SkyGuard.Map.renderShelters();
    this.updateStats();
    this.openShelterDetails(shelter.id);

    this.showToast(`✓ Офіційний статус «${shelter.name}» оновлено (${newStatus}, заповнено: ${shelter.current_occupancy})`, "success");
    SkyGuard.Audit.logEvent("OFFICIAL_STATUS_UPDATE", `shelter/${shelter.id}/status`, "INTERNAL", 200);
  },

  /**
   * Forces status override by DSNS Operator (Emergency Dispatch)
   */
  forceDsnsStatus(newStatus) {
    const shelter = SkyGuard.State.getShelterById(SkyGuard.State.selectedShelterId);
    if (!shelter) return;

    shelter.status = newStatus;
    shelter.confirmed_at = "Щойно (ДСНС)";

    // 1. Instant sync across tabs in same browser (DSNS tab -> Citizen tab)
    SkyGuard.State.broadcastShelterUpdate(shelter.id, newStatus, shelter.confirmed_at);

    // 2. Transmit to live backend API & WebSocket stream
    if (SkyGuard.Api && typeof SkyGuard.Api.sendShelterStatusUpdate === "function") {
      SkyGuard.Api.sendShelterStatusUpdate(shelter.id, newStatus);
    }

    SkyGuard.Map.renderShelters();
    this.updateStats();
    this.openShelterDetails(shelter.id);

    const actionText = newStatus === "OPEN" ? "ВІДЧИНЕНО ДЛЯ ЕВАКУАЦІЇ" : "ОПЕЧАТАНО / ЗАЧИНЕНО";
    this.showToast(`🚒 ДСНС оперативно змінив статус: ${actionText} (200 OK)`, newStatus === "OPEN" ? "success" : "warning");
    SkyGuard.Audit.logEvent("DSNS_FORCE_STATUS_OVERRIDE", `shelter/${shelter.id}/force_status`, "CONFIDENTIAL", 200);
  },

  /**
   * Closes details sidebar
   */
  
  /**
   * Updates Smart Geofence Presence Card (Anonymous GPS Check-in)
   */
  updateGeofencePresence(shelter) {
    const card = document.getElementById("geofencePresenceCard");
    const statusIcon = document.getElementById("presenceStatusIcon");
    const statusText = document.getElementById("presenceStatusText");
    const toggleBtn = document.getElementById("btnTogglePresence");
    if (!card || !statusText || !toggleBtn) return;

    const isCheckedIn = (SkyGuard.State.checkedInShelterId === shelter.id);

    // Calculate real distance
    let dist = 1000;
    if (SkyGuard.State.consent && SkyGuard.State.userLocation) {
      dist = SkyGuard.Geo.calculateHaversineDistance(
        SkyGuard.State.userLocation.lat,
        SkyGuard.State.userLocation.lon,
        shelter.lat,
        shelter.lon
      );
    }

    if (isCheckedIn) {
      if (statusIcon) statusIcon.textContent = "🟢";
      statusText.innerHTML = `<b>Ви всередині укриття:</b> GPS-периметр (≤ 30 м) підтверджено. Вас автоматично зараховано до заповненості (+1).`;
      statusText.style.color = "#34d399";
      toggleBtn.innerHTML = "🚪 Зімітувати вихід з укриття (-1 місце)";
      toggleBtn.className = "btn-presence-toggle checked-in";
    } else if (dist <= 50) {
      if (statusIcon) statusIcon.textContent = "🟡";
      statusText.innerHTML = `<b>Ви біля входу (${SkyGuard.Geo.formatDistance(dist)}):</b> Перетніть поріг для авточекіну.`;
      statusText.style.color = "#fbbf24";
      toggleBtn.innerHTML = "📍 Підтвердити перебування всередині (+1)";
      toggleBtn.className = "btn-presence-toggle near";
    } else {
      if (statusIcon) statusIcon.textContent = "🚶‍♂️";
      statusText.innerHTML = `<b>Ви на дистанції ${SkyGuard.Geo.formatDistance(dist)}:</b> Авточекін активується автоматично при наближенні ≤ 30 м.`;
      statusText.style.color = "var(--text-muted)";
      toggleBtn.innerHTML = "📍 Зімітувати перебування всередині (≤ 30 м)";
      toggleBtn.className = "btn-presence-toggle";
    }
  },

  /**
   * Toggles Geofence Presence Check-in / Check-out
   */
  toggleGeofencePresence() {
    const shelter = SkyGuard.State.getShelterById(SkyGuard.State.selectedShelterId);
    if (!shelter) return;

    if (SkyGuard.State.checkedInShelterId === shelter.id) {
      // User is checking OUT
      SkyGuard.State.checkedInShelterId = null;
      shelter.current_occupancy = Math.max(0, shelter.current_occupancy - 1);
      shelter.confirmed_at = "Щойно (GPS вихід)";
      this.showToast(`🚪 Фіксація виходу: ви покинули укриття «${shelter.name}» (-1 місце)`, "info");
      SkyGuard.Audit.logEvent("GEOFENCE_PRESENCE_CHECKOUT", `shelter/${shelter.id}`, "INTERNAL", 200);
    } else {
      // User is checking IN
      if (SkyGuard.State.checkedInShelterId) {
        const prev = SkyGuard.State.getShelterById(SkyGuard.State.checkedInShelterId);
        if (prev) prev.current_occupancy = Math.max(0, prev.current_occupancy - 1);
      }
      SkyGuard.State.checkedInShelterId = shelter.id;
      shelter.current_occupancy = Math.min(shelter.capacity, shelter.current_occupancy + 1);
      shelter.confirmed_at = "Щойно (GPS чекін ≤ 30м)";
      this.showToast(`📍 GPS-авточекін: вашу присутність зараховано (+1 людина до «${shelter.name}»)!`, "success");
      SkyGuard.Audit.logEvent("GEOFENCE_PRESENCE_CHECKIN", `shelter/${shelter.id}`, "INTERNAL", 200);
    }

    // Broadcast live across tabs
    SkyGuard.State.broadcastShelterUpdate(shelter.id, shelter.status, shelter.confirmed_at);
    if (SkyGuard.Api && typeof SkyGuard.Api.sendShelterStatusUpdate === "function") {
      SkyGuard.Api.sendShelterStatusUpdate(shelter.id, shelter.status);
    }

    this.openShelterDetails(shelter.id);
    this.updateStats();
    SkyGuard.Map.renderShelters();
  },

  /**
   * Initializes touch swipe-down gestures for mobile bottom sheet
   */
  initMobileGestures() {
    const handle = document.getElementById("sheetDragHandle");
    const sidebar = document.getElementById("detailsSidebar");
    if (!handle || !sidebar) return;

    let startY = 0;
    let currentY = 0;

    handle.addEventListener("touchstart", (e) => {
      startY = e.touches[0].clientY;
    }, { passive: true });

    handle.addEventListener("touchmove", (e) => {
      currentY = e.touches[0].clientY;
      const dy = currentY - startY;
      if (dy > 0) {
        sidebar.style.transform = `translateY(${dy}px)`;
      }
    }, { passive: true });

    handle.addEventListener("touchend", () => {
      const dy = currentY - startY;
      sidebar.style.transform = "";
      if (dy > 60) {
        this.closeShelterDetails();
      }
    });
  },

    /**
   * Toggles mobile bottom sheet between Peek (compact ~140px) and Expanded (78vh) modes
   */
  toggleMobileExpand() {
    const sidebar = document.getElementById("detailsSidebar");
    const expandBtn = document.getElementById("btnMobileExpand");
    if (!sidebar) return;

    const isExpanded = sidebar.classList.toggle("expanded");
    if (expandBtn) {
      expandBtn.textContent = isExpanded ? "▼ Згорнути" : "▲ Деталі";
    }
  },

  closeShelterDetails() {
    const sidebar = document.getElementById("detailsSidebar");
    if (sidebar) {
      sidebar.classList.remove("open");
      document.body.classList.remove("sidebar-open");
    }
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
