/**
 * SkyGuard — Backend API Service Client (SG-10 / SG-21 Integration)
 * Discipline: ПІС 2026 | Group: ОІ-33 | Team: corelogic
 * Module: js/api.js
 */

window.SkyGuard = window.SkyGuard || {};

SkyGuard.Api = {
  baseUrl: SkyGuard.Config.API_BASE_URL,

  /** Bearer token of the signed-in user (null for an anonymous visitor). */
  currentToken() {
    return (SkyGuard.Security && SkyGuard.Security.token) ||
           localStorage.getItem("skyguard_token") ||
           localStorage.getItem("skyguard_jwt_token") || null;
  },

  authHeaders(extra = {}) {
    const token = this.currentToken();
    return {
      "Accept": "application/json",
      ...(token ? { "Authorization": `Bearer ${token}` } : {}),
      ...extra
    };
  },

  /** Unified call: never throws; returns {ok, status, data} or {ok:false, offline:true}. */
  async request(method, path, body = undefined) {
    try {
      const resp = await fetch(`${this.baseUrl}${path}`, {
        method,
        headers: this.authHeaders(body !== undefined ? { "Content-Type": "application/json" } : {}),
        body: body !== undefined ? JSON.stringify(body) : undefined
      });
      const data = await resp.json().catch(() => ({}));
      return { ok: resp.ok, status: resp.status, data };
    } catch (e) {
      return { ok: false, offline: true, status: 0, data: { message: e.message } };
    }
  },

  /**
   * Fetches shelters list from FastAPI backend (or falls back to local data)
   * Target endpoint: GET /api/v1/shelters (SG-10)
   */
  async fetchShelters() {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), SkyGuard.Config.API_TIMEOUT_MS);

      const response = await fetch(`${this.baseUrl}/shelters`, {
        signal: controller.signal,
        headers: { "Accept": "application/json" }
      });
      clearTimeout(timeoutId);

      if (response.ok) {
        const data = await response.json();
        // If data is RFC 7946 FeatureCollection from FastAPI
        if (data && data.features) {
          const mapped = data.features.map(f => ({
            id: f.properties.id || f.id,
            name: f.properties.name,
            address: f.properties.address,
            district: f.properties.district,
            lat: f.geometry.coordinates[1],
            lon: f.geometry.coordinates[0],
            capacity: f.properties.capacity,
            current_occupancy: f.properties.occupancy || 0,
            status: f.properties.status === "FULL" ? "LIMITED" : f.properties.status,
            wheelchair: f.properties.resources ? f.properties.resources.ramp : false,
            generator: f.properties.resources ? f.properties.resources.generator : false,
            starlink: f.properties.resources ? f.properties.resources.starlink : false,
            water: f.properties.resources ? f.properties.resources.water : false,
            confirmed_at: f.properties.status_updated_at || "Щойно (Live API)",
            commander: { name: "Черговий комендант", phone: "+380 67 111 22 33", id: "DSNS-LV" },
            lock: { id: "LOCK-ESP32-101", battery: "95%", rssi: "-65 dBm", state: "UNLOCKED" }
          }));
          console.info("[SkyGuard API] Live shelters loaded from backend:", mapped.length);
          return mapped;
        }
        return data;
      }
    } catch (err) {
      console.warn("[SkyGuard API] Backend offline or unreachable. Using embedded GeoJSON catalog.");
    }
    return SkyGuard.State.shelters;
  },

  /**
   * Broadcasts official status change to backend API (SG-21)
   */
  async sendShelterStatusUpdate(shelterId, status, occupancy = null) {
    // Acts strictly as the signed-in user: the server decides by role (RBAC) whether
    // the change is allowed. No hidden sign-in under another account.
    const backendStatus = (status === "LIMITED" ? "FULL" : status);
    const payload = { status: backendStatus };
    if (typeof occupancy === "number" && !isNaN(occupancy)) {
      payload.occupancy = occupancy;
    }
    const sObj = SkyGuard.State && SkyGuard.State.getShelterById(shelterId);
    const targetId = (sObj && sObj.backendId) || shelterId;
    const res = await this.request("POST", `/shelters/${targetId}/status`, payload);
    if (res.ok) {
      console.info(`[SkyGuard API] Status persisted: ${targetId} → ${backendStatus}`, res.data);
      return { success: true, status: res.status, data: res.data };
    }
    console.warn(`[SkyGuard API] Status update rejected (${res.status}):`, res.data);
    return { success: false, status: res.status, error: res.data, offline: !!res.offline };
  },

  wsActive: false,

  /**
   * Initializes live WebSocket connection for instant push updates (SG-21)
   */
  initWebSocket() {
    if (!SkyGuard.Config.ENABLE_WEBSOCKET_STREAM) {
      console.info("[SkyGuard API] Прототип працює в автономному режимі (SG-9). Фоновий WebSocket вимкнено для стабільності демонстрації.");
      return;
    }
    try {
      const base = SkyGuard.Config.API_BASE_URL || "http://localhost:8000/api/v1";
      const wsProto = base.startsWith("https") ? "wss" : "ws";
      const host = base.replace(/^https?:\/\//, "").replace(/\/api\/v1\/?$/, "");
      const wsUrl = `${wsProto}://${host}/ws/v1/shelters`;
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        this.wsActive = true;
        console.info("[SkyGuard WS] Connected to live backend stream:", wsUrl);
        SkyGuard.UI.showToast("⚡ Підключено до Live WebSocket сервера", "success");
      };

      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          // Handle Shelter status updates
          if (msg.type === "shelter.updated" && msg.shelter) {
            const f = msg.shelter;
            const updatedId = f.properties.id || f.id;
            const existing = SkyGuard.State.getShelterById(updatedId, f.properties?.name);
            if (existing) {
              const newStatus = (f.properties.status === "FULL" ? "LIMITED" : f.properties.status);
              existing.status = newStatus;
              if (typeof f.properties.occupancy === "number") {
                existing.current_occupancy = f.properties.occupancy;
              } else if (newStatus === "CLOSED") {
                existing.current_occupancy = 0;
              }
              existing.confirmed_at = "Щойно (Live WebSocket)";
              SkyGuard.State.persistShelters();
              SkyGuard.Map.renderShelters();
              SkyGuard.UI.updateStats();

              if (SkyGuard.State.selectedShelterId && 
                  (String(SkyGuard.State.selectedShelterId).toLowerCase() === String(existing.id).toLowerCase() ||
                   String(SkyGuard.State.selectedShelterId).toLowerCase() === String(updatedId).toLowerCase())) {
                SkyGuard.UI.openShelterDetails(existing.id);
              }

              const label = newStatus === "OPEN" ? "ВІДЧИНЕНО" : (newStatus === "CLOSED" ? "ЗАЧИНЕНО" : "ОБМЕЖЕНО");
              SkyGuard.UI.showToast(`⚡ Live WebSocket: Статус «${existing.name}» змінено на ${label}!`, "info");
              SkyGuard.Audit.logEvent("WS_LIVE_SHELTER_SYNC", `shelter/${updatedId}`, "PUBLIC", 200);

              // If Auditor console is open, sync audit trail in real time
              if (SkyGuard.State.role === "AUDITOR") {
                const modal = document.getElementById("auditModal");
                if (modal && modal.classList.contains("active")) {
                  SkyGuard.Audit.fetchLiveAuditTrail(true);
                }
              }
            }
          }

          // Handle Air Raid Alert push notification from alerts.in.ua (SG-23)
          if (msg.type === "air_raid_alert.updated" && SkyGuard.Config.ENABLE_LIVE_ALERTS_API) {
            const isCurrentlyAlarm = SkyGuard.State.alarmActive;
            if (msg.active && !isCurrentlyAlarm) {
              SkyGuard.UI.toggleAlarmMode();
              SkyGuard.UI.showToast(`🚨 Отримано сигнал повітряної тривоги від alerts.in.ua (${msg.location})!`, "error");
            } else if (!msg.active && isCurrentlyAlarm) {
              SkyGuard.UI.toggleAlarmMode();
              SkyGuard.UI.showToast(`✓ Відбій повітряної тривоги (${msg.location})`, "success");
            }
          }
        } catch (err) {}
      };

      ws.onerror = () => {
        this.wsActive = false;
        console.debug("[SkyGuard WS] Offline (fallback to local mock events)");
      };

      ws.onclose = () => {
        this.wsActive = false;
        console.debug("[SkyGuard WS] Live stream closed. Auto-reconnecting in 4s...");
        setTimeout(() => this.initWebSocket(), 4000);
      };
    } catch (e) {}
  },

  /**
   * Submits a status change or crowdsource report to backend (SG-21)
   * Target endpoint: POST /api/v1/shelters/{id}/reports
   */
  async submitStatusReport(shelterId, reportPayload) {
    const res = await this.request("POST", `/shelters/${shelterId}/reports`, reportPayload);
    if (res.ok) return { success: true, status: res.status, data: res.data };
    return { success: false, status: res.status, error: res.data, offline: !!res.offline };
  },

  /**
   * Commander contacts — CONFIDENTIAL (L3). Allowed: DSNS operator; shelter manager for own shelter.
   * Target endpoint: GET /api/v1/shelters/{id}/contacts (SG-10)
   */
  async fetchShelterContacts(shelterId) {
    return this.request("GET", `/shelters/${shelterId}/contacts`);
  },

  /**
   * Synchronizes user consent record with backend (Data Governance L1/L2)
   * Target endpoints: POST /api/v1/consents, DELETE /api/v1/consents/{purpose} (Bearer token)
   */
  async updateConsent(consentGranted, purposes = ["ROUTE_GPS", "REPORT_GEOFENCE"]) {
    if (!this.currentToken()) {
      return [];  // anonymous visitor: consent stays in the browser only
    }
    const results = [];
    for (const purpose of purposes) {
      const res = consentGranted
        ? await this.request("POST", "/consents", { purpose })
        : await this.request("DELETE", `/consents/${purpose}`);
      results.push({ purpose, ...res });
    }
    return results;
  },

  /**
   * Generates and downloads RFC 7946 GeoJSON FeatureCollection
   * @param {Array} shelters 
   */
  downloadGeoJson(shelters) {
    const geojson = {
      type: "FeatureCollection",
      name: "SkyGuard_Lviv_Shelters_Export",
      crs: { type: "name", properties: { name: "urn:ogc:def:crs:OGC:1.3:CRS84" } },
      features: shelters.map(s => ({
        type: "Feature",
        properties: {
          id: s.id,
          name: s.name,
          address: s.address,
          district: s.district,
          capacity: s.capacity,
          current_occupancy: s.current_occupancy,
          status: s.status,
          wheelchair_accessible: s.wheelchair,
          has_power_generator: s.generator,
          has_starlink: s.starlink,
          potable_water: s.water,
          last_confirmed: s.confirmed_at
        },
        geometry: { type: "Point", coordinates: [s.lon, s.lat] }
      }))
    };

    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(geojson, null, 2));
    const dlAnchor = document.createElement("a");
    dlAnchor.setAttribute("href", dataStr);
    dlAnchor.setAttribute("download", "skyguard_lviv_shelters.geojson");
    dlAnchor.click();
  }
};
