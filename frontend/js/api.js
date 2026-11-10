/**
 * SkyGuard — Backend API Service Client (SG-10 / SG-21 Integration)
 * Discipline: ПІС 2026 | Group: ОІ-33 | Team: corelogic
 * Module: js/api.js
 */

window.SkyGuard = window.SkyGuard || {};

SkyGuard.Api = {
  baseUrl: SkyGuard.Config.API_BASE_URL,

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
        console.info("[SkyGuard API] Live shelters loaded from backend:", data.length);
        return data;
      }
    } catch (err) {
      console.warn("[SkyGuard API] Backend offline or unreachable. Using embedded GeoJSON catalog.");
    }
    return SkyGuard.State.shelters;
  },

  /**
   * Submits a status change or crowdsource report to backend (SG-21)
   * Target endpoint: POST /api/v1/shelters/{id}/reports
   */
  async submitStatusReport(shelterId, reportPayload) {
    try {
      const response = await fetch(`${this.baseUrl}/shelters/${shelterId}/reports`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-User-Role": SkyGuard.State.role
        },
        body: JSON.stringify(reportPayload)
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: "Unknown error" }));
        return { success: false, status: response.status, error: errorData.detail };
      }

      return { success: true, status: response.status, data: await response.json() };
    } catch (err) {
      // Local simulation fallback
      return { success: true, status: 200, simulated: true };
    }
  },

  /**
   * Synchronizes user consent record with backend (Data Governance L1/L2)
   * Target endpoint: POST /api/v1/consent
   */
  async updateConsent(consentGranted) {
    try {
      await fetch(`${this.baseUrl}/consent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "citizen_01",
          consent_type: "GEOLOCATION_TRACKING",
          granted: consentGranted,
          timestamp: new Date().toISOString()
        })
      });
    } catch (e) {
      // Offline fallback silent
    }
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
