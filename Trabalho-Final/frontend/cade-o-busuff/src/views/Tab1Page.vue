<template>
  <ion-page>
    <ion-header v-if="role == 'student'">
	<ion-toolbar>
	    <ion-select
		v-model="selectedRoute"
		label="Rota"
		name="routeId"
		interface="popover"
		class="ion-padding-horizontal"
	    >
		<ion-select-option value="rota-1">Rota 1</ion-select-option>
		<ion-select-option value="rota-2">Rota 2</ion-select-option>
		<ion-select-option value="rota-3">Rota 3</ion-select-option>
	    </ion-select>
	</ion-toolbar>
    </ion-header>
    <ion-header v-if="role == 'driver'">
	<ion-toolbar>
	    <div class="text-wrapper">
		<p><b>Rota:</b> <span>{{ selectedRoute }}</span></p>
		<p><b>Ônibus:</b> <span>{{ selectedVehicle }}</span></p>
	    </div>
	</ion-toolbar>
    </ion-header>
    <ion-content class="map-content" :scroll-y="false">
	<MapsContainer
	    v-if="mapVisible"
	    :key="role"
	    :role="role"
	    :route-id="selectedRoute"
	    :vehicle-id="selectedVehicle"
	/>
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
 
import {
    IonPage,
    IonHeader,
    IonToolbar,
    IonSelect,
    IonSelectOption,
    IonContent,
    onIonViewDidEnter,
    onIonViewWillLeave,
} from '@ionic/vue';

import { computed, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import MapsContainer from '@/components/MapsContainer.vue';

const mapVisible = ref(false);

const route = useRoute();
const role = computed(() =>
    route.query.role === 'driver' ? 'driver' : 'student'
 );

const selectedRoute = ref('');
const selectedVehicle = ref('');
 
watch(
  () => [route.query.routeId, route.query.vehicleId],
  ([routeId, vehicleId]) => {
    selectedRoute.value =
      typeof routeId === 'string' ? routeId : 'rota-1';
    
    selectedVehicle.value =
      typeof vehicleId === 'string' ? vehicleId : '';
  },
  { immediate: true }
);

onIonViewDidEnter(() => {
    mapVisible.value = true;
});

onIonViewWillLeave(() => {
    mapVisible.value = false;
});

</script>

<style scoped>
 .map-content {
     --background: transparent;
 }

 .text-wrapper {
     display: flex;
     flex-direction: row;
     justify-content: space-around;
 }
</style>
