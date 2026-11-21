<template>
  <capacitor-google-map ref="mapElement"></capacitor-google-map>
</template>

<script setup lang="ts">
import { GoogleMap } from '@capacitor/google-maps';
import { Geolocation, type Position } from '@capacitor/geolocation';
import { Capacitor } from '@capacitor/core';
import { onBeforeUnmount, onMounted, ref, useId } from 'vue';
import { GeoEvents } from '../geo_events';
import { MapControler } from '../map/MapControler';

const mapElement = ref<HTMLElement | null>(null);
const mapId = `busuff-map-${useId()}`;
const interval = 1000;

let map: GoogleMap | undefined;
let geoEvents: GeoEvents | undefined;
let interval_ID: number;
let sending = false;

function getCurrPosition() {
  return Geolocation.getCurrentPosition({
    enableHighAccuracy: true,
    timeout: 10000,
  });
}

async function sendCurrPosition(geoEvents: GeoEvents): Promise<void> {
  if (sending) return;
  sending = true;

  try {
    const position = await getCurrPosition();
    if (!mapElement.value?.isConnected) return;

    geoEvents.sendPosition(JSON.stringify(position));
  } catch (error) {
    console.error('Failed to share location:', error);
  } finally {
    sending = false;
  }
}

onMounted(async () => {
  if (!mapElement.value) return;

  try {

    if (Capacitor.isNativePlatform()) {
	const permission = await Geolocation.requestPermissions();
	if (permission.location !== 'granted' && permission.coarseLocation !== 'granted') {
            console.error('Location permission denied');
            return;
	}
    }

    const position = await getCurrPosition();
    if (!mapElement.value?.isConnected) return;

    map = await GoogleMap.create({
      id: mapId,
      element: mapElement.value,
      apiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY ?? '',
      config: {
        center: { lat: position.coords.latitude, lng: position.coords.longitude },
        zoom: 14,
      },
    });

    if (!mapElement.value?.isConnected) {
	await map.destroy();
	return;
    }

    const mapController = new MapControler(map);

    const events = new GeoEvents('rota1', async (rota, payload) => {

        if (!mapElement.value?.isConnected) return;

	try {
            const position: Position = JSON.parse(payload.toString());
            await mapController.updateMarkerPosition(rota, position);
	} catch (error) {
            console.error('Failed to update marker:', error);
	}
    });
      
    geoEvents = events;

    interval_ID = window.setInterval(() => {
	void sendCurrPosition(events);
    }, interval);

  } catch (error) {
    console.error('Não foi possível mostrar a localização do usuário:', error);
  }
     
});

onBeforeUnmount(async () => {
  window.clearInterval(interval_ID);
  geoEvents?.stop();
  await map?.destroy();
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
