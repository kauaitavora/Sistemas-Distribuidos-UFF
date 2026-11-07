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
let map: GoogleMap | undefined;

onMounted(async () => {

  if (!mapElement.value) return;

  const map = await GoogleMap.create({
    id: mapId,
    element: mapElement.value,
    apiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY ?? '',
    config: {
      center: { lat: -22.8833, lng: -43.1036 },
      zoom: 14,
    },
  });

  try {
    

    if (Capacitor.isNativePlatform()) {
      await Geolocation.requestPermissions();
    }

    const position = await Geolocation.getCurrentPosition({
      enableHighAccuracy: true,
      timeout: 10000,
    });

    if (!mapElement.value?.isConnected) return;

    const coordinate = {
      lat: position.coords.latitude,
      lng: position.coords.longitude,
    };

    await map.addMarker({
      coordinate,
      title: 'Você está aqui',
    });

    await map.setCamera({
      coordinate,
      zoom: 16,
    });

  } catch (error) {
    console.error('Não foi possível mostrar a localização do usuário:', error);
  }

});

onBeforeUnmount(async () => {
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
