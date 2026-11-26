<template>
  <div class="map-wrapper">
    <capacitor-google-map ref="mapElement"></capacitor-google-map>
    <p v-if="selectedMarkerTitle" class="marker-title" role="status">
      {{ selectedMarkerTitle }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { GoogleMap } from '@capacitor/google-maps';
import { Geolocation, type Position } from '@capacitor/geolocation';
import { Capacitor } from '@capacitor/core';
import { onBeforeUnmount, onMounted, ref, useId } from 'vue';
import { GeoEvents } from '../geo_events';
import { MapControler } from '../map/MapControler';
import { watch } from 'vue';
import { fetchAPI } from '@/services/APIService';

const mapElement = ref<HTMLElement | null>(null);
const selectedMarkerTitle = ref('');
const mapId = `busuff-map-${useId()}`;
const interval = 1000;
const broker_address = import.meta.env.VITE_MQTT_BROKER_ADDRESS ?? 'ws://localhost:8000/mqtt'
let map: GoogleMap | undefined;
let geoEvents: GeoEvents | undefined;
let interval_ID: number;
let sending = false;
 
const props = defineProps<{
     role: 'driver' | 'student';
     routeId: string;
     vehicleId: string;
}>();


async function initMap(): Promise<GoogleMap | undefined> {
    // O aluno pode acompanhar os ônibus sem compartilhar a própria localização.
    let center = { lat: -22.9, lng: -43.12 };
    try {
	const position = await getCurrPosition();
	center = { lat: position.coords.latitude, lng: position.coords.longitude };
    } catch (error) {
	if (props.role === 'driver') throw error;
    }
    if (!mapElement.value?.isConnected) return;

    return await GoogleMap.create({
	id: mapId,
	element: mapElement.value,
	apiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY ?? '',
	config: {
	center,
	zoom: 14,
	},
    });
} 
 
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
	if (Capacitor.isNativePlatform() && props.role === 'driver') {
	    const permission = await Geolocation.requestPermissions();
	    if (permission.location !== 'granted' && permission.coarseLocation !== 'granted') {
		console.error('Location permission denied');
		return;
	    }
	}

	const rotas = await fetchAPI('/rotas') ?? [];
	const veiculos = await fetchAPI('/veiculos') ?? [];

	map = await initMap();
	if (!map) return;
	await map.setOnMarkerClickListener(({ title }) => {
	    selectedMarkerTitle.value = title;
	});

	const mapController = new MapControler(map);
	const events = new GeoEvents(broker_address, props.routeId, props.vehicleId,
	    async (topic, payload) => {
			const [prefix, routeId, vehicleId] = topic.split('/');
			if (prefix !== 'rotas' || routeId !== props.routeId || !vehicleId) return;
			if (props.role === 'driver' && vehicleId !== props.vehicleId) return;
			if (!mapElement.value?.isConnected) return;

			try {
				const position: Position = JSON.parse(payload.toString());
				const rota = rotas.find((rota) => rota.id === routeId);
				const veiculo = veiculos.find((veiculo) => veiculo.id === vehicleId);
				const titulo = `${rota?.nome ?? routeId} — ${veiculo?.nome ?? vehicleId}`;

				await mapController.updateMarkerPosition(topic, position, titulo);
			} catch (error) {
				console.error('Failed to update marker:', error);
			}
		}
	);

	geoEvents = events;

	if (props.role === 'driver') {
	    interval_ID = window.setInterval(() => {
		void sendCurrPosition(events);
	    }, interval); 
	}
	
	watch(
	    () => props.routeId,
	    (newRouteId, previousRouteId) => {
		if (!newRouteId || newRouteId === previousRouteId) return;
		if (!geoEvents) return;
		selectedMarkerTitle.value = '';
		geoEvents.changeRoute(newRouteId);
		mapController.removeAllMarkers();
	    }
	);
	

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
.map-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
}

capacitor-google-map {
  display: block;
  width: 100%;
  height: 100%;
  min-height: 300px;
}

.marker-title {
  position: absolute;
  bottom: 24px;
  left: 16px;
  z-index: 1;
  max-width: calc(100% - 32px);
  margin: 0;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--ion-background-color, white);
  color: var(--ion-text-color, black);
  pointer-events: none;
}
</style>
