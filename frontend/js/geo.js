/**
 * SkyGuard — Geolocation & Haversine Mathematics
 * Discipline: ПІС 2026 | Group: ОІ-33 | Team: corelogic
 * Module: js/geo.js
 */

window.SkyGuard = window.SkyGuard || {};

SkyGuard.Geo = {
  /**
   * Calculates great-circle distance between two GPS coordinates using Haversine formula
   * @param {number} lat1 Latitude of point 1 in degrees
   * @param {number} lon1 Longitude of point 1 in degrees
   * @param {number} lat2 Latitude of point 2 in degrees
   * @param {number} lon2 Longitude of point 2 in degrees
   * @returns {number} Distance in metres (rounded)
   */
  calculateHaversineDistance(lat1, lon1, lat2, lon2) {
    const R = 6371000; // Earth radius in metres
    const toRad = deg => (deg * Math.PI) / 180;
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return Math.round(R * c);
  },

  /**
   * Formats distance into human-readable string (e.g. "350 м" or "1.4 км")
   * @param {number} metres 
   * @returns {string}
   */
  formatDistance(metres) {
    if (metres < 1000) return `${metres} м`;
    return `${(metres / 1000).toFixed(1)} км`;
  },

  /**
   * Estimates pedestrian walking duration in minutes at standard walking speed (5 km/h)
   * @param {number} metres 
   * @returns {number} minutes (minimum 1)
   */
  calculateWalkingMinutes(metres) {
    const speed = SkyGuard.Config.DQ_RULES.WALKING_SPEED_METRES_MIN || 83.3;
    return Math.max(1, Math.round(metres / speed));
  },

  /**
   * Calculates actual walking route along street sidewalks via OpenStreetMap OSRM routing service
   * Uses routing.openstreetmap.de routed-foot engine (full coverage of Ukraine / Lviv)
   * Falls back to straight Haversine line if offline
   */
  async getWalkingRoute(lat1, lon1, lat2, lon2) {
    try {
      const url = `https://routing.openstreetmap.de/routed-foot/route/v1/driving/${lon1},${lat1};${lon2},${lat2}?overview=full&geometries=geojson`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        if (data.routes && data.routes.length > 0) {
          const route = data.routes[0];
          return {
            coordinates: route.geometry.coordinates.map(pt => [pt[1], pt[0]]), // Leaflet expects [lat, lon]
            distanceMetres: Math.round(route.distance),
            durationMinutes: Math.max(1, Math.round(route.duration / 60)),
            isPedestrianNetwork: true
          };
        }
      }
    } catch (e) {
      console.warn("[SkyGuard Router] Routing service offline, falling back to Haversine line", e);
    }

    // Mathematical Haversine straight-line fallback
    const directDist = this.calculateHaversineDistance(lat1, lon1, lat2, lon2);
    return {
      coordinates: [[lat1, lon1], [lat2, lon2]],
      distanceMetres: directDist,
      durationMinutes: this.calculateWalkingMinutes(directDist),
      isPedestrianNetwork: false
    };
  },

  /**
   * Requests real GPS coordinates from browser via HTML5 Geolocation API
   * @param {Function} onSuccess Callback with (lat, lon)
   * @param {Function} onError Callback with Error
   */
  locateUser(onSuccess, onError) {
    if (!navigator.geolocation) {
      if (onError) onError(new Error("Геолокація не підтримується браузером"));
      return;
    }

    navigator.geolocation.getCurrentPosition(
      pos => {
        onSuccess(pos.coords.latitude, pos.coords.longitude);
      },
      err => {
        if (onError) onError(err);
      },
      { enableHighAccuracy: true, timeout: 6000 }
    );
  }
};
