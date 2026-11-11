/**
 * SkyGuard — Leaflet.js Map Controller & Spatial Layers
 * Discipline: ПІС 2026 | Group: ОІ-33 | Team: corelogic
 * Module: js/map.js
 */

window.SkyGuard = window.SkyGuard || {};

SkyGuard.Map = {
  instance: null,
  markersLayer: null,
  userMarker: null,

  /**
   * Initializes Leaflet map with CartoDB Dark Matter tiles
   */
  init() {
    this.instance = L.map("map", {
      zoomControl: false,
      attributionControl: false
    }).setView(SkyGuard.Config.MAP_CENTER, SkyGuard.Config.MAP_DEFAULT_ZOOM);

    // Dark OLED Basemap
    L.tileLayer(SkyGuard.Config.MAP_TILE_LAYER, {
      subdomains: SkyGuard.Config.MAP_SUBDOMAINS,
      maxZoom: SkyGuard.Config.MAP_MAX_ZOOM
    }).addTo(this.instance);

    L.control.zoom({ position: "bottomright" }).addTo(this.instance);

    this.markersLayer = L.layerGroup().addTo(this.instance);

    this.updateUserMarker();
    this.renderShelters();

    // Ensure Leaflet calculates exact viewport dimensions immediately
    setTimeout(() => {
      if (this.instance) this.instance.invalidateSize();
    }, 200);

    window.addEventListener("resize", () => {
      if (this.instance) this.instance.invalidateSize();
    });
  },

  /**
   * Updates or removes user GPS location marker based on L2 consent
   */
  updateUserMarker() {
    if (!this.instance) return;

    if (this.userMarker) {
      this.markersLayer.removeLayer(this.userMarker);
      this.userMarker = null;
    }

    if (SkyGuard.State.consent && SkyGuard.State.userLocation) {
      const icon = L.divIcon({
        className: "custom-user-pin",
        html: `
          <div class="user-live-pin">
            <div class="user-live-pulse"></div>
          </div>
        `,
        iconSize: [20, 20],
        iconAnchor: [10, 10]
      });

      this.userMarker = L.marker(
        [SkyGuard.State.userLocation.lat, SkyGuard.State.userLocation.lon],
        { icon, zIndexOffset: 1000 }
      )
        .bindTooltip(`📍 ${SkyGuard.State.userLocation.name || "Ваша поточна геопозиція"}`, {
          direction: "top",
          offset: [0, -10]
        })
        .addTo(this.markersLayer);
    }
  },

  /**
   * Generates custom dynamic SVG pin depending on shelter status
   */
  createMarkerIcon(status, isHighlighted = false) {
    let pinClass = "pin-open";
    let iconEmoji = "🛡️";

    if (status === "LIMITED") {
      pinClass = "pin-limited";
      iconEmoji = "⚠️";
    } else if (status === "CLOSED") {
      pinClass = "pin-closed";
      iconEmoji = "⛔";
    }

    return L.divIcon({
      className: "custom-pin",
      html: `
        <div class="${pinClass} ${isHighlighted ? 'pin-highlighted' : ''}">
          ${status !== "CLOSED" ? '<div class="pin-pulse"></div>' : ''}
          <div class="pin-core" ${isHighlighted ? 'style="border-color: #38bdf8; box-shadow: 0 0 20px #38bdf8;"' : ''}>
            <span class="pin-icon">${iconEmoji}</span>
          </div>
        </div>
      `,
      iconSize: [36, 36],
      iconAnchor: [18, 34]
    });
  },

  /**
   * Renders shelters onto map applying active filters and air raid alarm rules
   */
  renderShelters() {
    if (!this.markersLayer) return;
    this.markersLayer.clearLayers();

    if (this.userMarker) this.markersLayer.addLayer(this.userMarker);
    if (SkyGuard.State.routeLine) this.markersLayer.addLayer(SkyGuard.State.routeLine);

    const query = SkyGuard.State.searchQuery.toLowerCase().trim();

    SkyGuard.State.shelters.forEach(shelter => {
      // Alarm Mode rule: only OPEN shelters displayed
      if (SkyGuard.State.alarmActive && shelter.status !== "OPEN") return;

      // Status Filter
      if (SkyGuard.State.activeFilter !== "ALL" && shelter.status !== SkyGuard.State.activeFilter) return;

      // Feature Toggles Filter
      if (SkyGuard.State.activeFeatures.has("wheelchair") && !shelter.wheelchair) return;
      if (SkyGuard.State.activeFeatures.has("generator") && !shelter.generator) return;
      if (SkyGuard.State.activeFeatures.has("starlink") && !shelter.starlink) return;
      if (SkyGuard.State.activeFeatures.has("water") && !shelter.water) return;

      // Search Query
      if (query) {
        const matchName = shelter.name.toLowerCase().includes(query);
        const matchAddr = shelter.address.toLowerCase().includes(query);
        const matchDistrict = shelter.district.toLowerCase().includes(query);
        if (!matchName && !matchAddr && !matchDistrict) return;
      }

      const isHighlighted = (SkyGuard.State.selectedShelterId === shelter.id);
      const icon = this.createMarkerIcon(shelter.status, isHighlighted);
      const marker = L.marker([shelter.lat, shelter.lon], { icon });

      marker.on("click", () => {
        SkyGuard.UI.openShelterDetails(shelter.id);
      });

      this.markersLayer.addLayer(marker);
    });
  },

  /**
   * Draws interactive animated route polyline to destination shelter along real street network (OSRM)
   */
  async drawRouteToShelter(shelterId) {
    const shelter = SkyGuard.State.getShelterById(shelterId);
    if (!shelter || !SkyGuard.State.userLocation) return;

    this.clearRouteLine();

    const userPoint = [SkyGuard.State.userLocation.lat, SkyGuard.State.userLocation.lon];
    const shelterPoint = [shelter.lat, shelter.lon];

    SkyGuard.UI.showToast("🗺️ Розрахунок безпечного маршруту SafeRoute...", "info");

    const routeData = await SkyGuard.Geo.getWalkingRoute(
      userPoint[0], userPoint[1], shelterPoint[0], shelterPoint[1]
    );

    // Draw animated dashed route line following real street geometry
    SkyGuard.State.routeLine = L.polyline(routeData.coordinates, {
      color: "#38bdf8",
      weight: 5,
      opacity: 0.95,
      dashArray: "10, 10",
      className: "route-pulse-line"
    }).addTo(this.markersLayer);

    // Fit view to include route
    this.instance.fitBounds(SkyGuard.State.routeLine.getBounds(), { padding: [60, 60] });

    const routeEstText = document.getElementById("routeEstText");
    if (routeEstText) {
      routeEstText.textContent = `🚶 ~${routeData.durationMinutes} хв пішки (${SkyGuard.Geo.formatDistance(routeData.distanceMetres)})`;
    }

    const typeDesc = routeData.isPedestrianNetwork ? "вулицями та тротуарами" : "по прямій (Haversine)";
    SkyGuard.UI.showToast(
      `✓ SafeRoute: ${SkyGuard.Geo.formatDistance(routeData.distanceMetres)} (${typeDesc}, ~${routeData.durationMinutes} хв)`,
      "success"
    );
  },

  /**
   * Clears currently drawn route line
   */
  clearRouteLine() {
    if (SkyGuard.State.routeLine && this.markersLayer) {
      this.markersLayer.removeLayer(SkyGuard.State.routeLine);
      SkyGuard.State.routeLine = null;
    }
  }
};
