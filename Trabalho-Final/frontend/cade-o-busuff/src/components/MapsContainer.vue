<template>
  <capacitor-google-map ref="mapElement"></capacitor-google-map>
</template>

<script setup lang="ts">
import { GoogleMap } from '@capacitor/google-maps';
import { Geolocation } from '@capacitor/geolocation';
import { Capacitor } from '@capacitor/core';
import { onBeforeUnmount, onMounted, ref, useId } from 'vue';
import { GeoEvents } from '../geo_events';

const mapElement = ref<HTMLElement | null>(null);
const mapId = `busuff-map-${useId()}`;
const interval = 1000;

let map: GoogleMap;
let interval_ID;

async function sendCurrPosition(geo_events: GeoEvents) {
  const position = await Geolocation.getCurrentPosition({
    enableHighAccuracy: true,
    timeout: 10000,
  });
    
  geo_events.sendPosition(JSON.stringify(position));
}

onMounted(async () => {

  if (!mapElement.value) return;

  map = await GoogleMap.create({
    id: mapId,
    element: mapElement.value,
    apiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY ?? '',
    config: {
      center: { lat: -22.503, lng: -41.924 },
      zoom: 14,
    },
  });

  let marker_ID;

  async function updateMarkerPosition(rota: string, position_json: Buffer) {
    if (!mapElement.value?.isConnected) return;

    let position = JSON.parse(position_json.toString());

    console.log(rota);
    console.log(position);

    const coordinate = {
      lat: position.coords.latitude,
      lng: position.coords.longitude,
    };

    await map.removeMarker(marker_ID);

    marker_ID = await map.addMarker({
      coordinate,
      title: rota,
    });
  }

  try {
    let geo_events_handler = new GeoEvents("rota1", updateMarkerPosition);

    if (Capacitor.isNativePlatform()) {
      await Geolocation.requestPermissions();
    }

    interval_ID = setInterval(sendCurrPosition, interval, geo_events_handler);
    
  } catch (error) {
    console.error('Não foi possível mostrar a localização do usuário:', error);
  }

});

onBeforeUnmount(async () => {
  clearInterval(interval_ID);
  const instance = await map;
  await instance?.destroy();
});

</script>

<style scoped>
capacitor-google-map {
  display: block;
  width: 100%;
  height: 100%;
  min-height: 300px;
}
</style>
