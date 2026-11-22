<template>
  <ion-page>
    <ion-header>
	<ion-toolbar>
	    <ion-select
		v-model="selectedRoute"
		label="Rota"
		interface="popover"
		class="ion-padding-horizontal"
	    >
		<ion-select-option value="rota1">Rota 1</ion-select-option>
		<ion-select-option value="rota2">Rota 2</ion-select-option>
		<ion-select-option value="rota3">Rota 3</ion-select-option>
	    </ion-select>
	</ion-toolbar>
    </ion-header>
    <ion-content class="map-content" :scroll-y="false">
	<MapsContainer
	    v-if="mapVisible"
	    :key="`${role}:${selectedRoute}`"
	    :role="role"
	    :route-id="selectedRoute"
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

import { computed, ref } from 'vue';
import { useRoute } from 'vue-router';

import MapsContainer from '@/components/MapsContainer.vue';

const mapVisible = ref(false);

const route = useRoute();
const role = computed(() =>
    route.query.role === 'driver' ? 'driver' : 'student'
);

const selectedRoute = ref('rota1');



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
</style>
