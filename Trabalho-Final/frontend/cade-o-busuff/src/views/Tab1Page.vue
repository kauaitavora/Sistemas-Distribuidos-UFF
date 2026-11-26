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
		:disabled="carregandoRotas || erroRotas || !rotas.length"
		placeholder="Selecione a rota"
	    >
		<ion-select-option
			v-for="rota in rotas"
			:key="rota.id"
			:value="rota.id"
		>
			{{ rota.nome }}
		</ion-select-option>
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
	<p v-if="carregandoRotas" class="ion-padding" role="status">Carregando rotas...</p>
	<div v-else-if="erroRotas" class="ion-padding">
	    <p role="alert">Não foi possível carregar as rotas.</p>
	    <ion-button fill="clear" @click="carregarRotas">Tentar novamente</ion-button>
	</div>
	<p v-else-if="!rotas.length" class="ion-padding" role="status">Nenhuma rota disponível.</p>
	<MapsContainer
	    v-if="mapVisible && selectedRoute && !carregandoRotas && !erroRotas"
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
    IonButton,
    IonPage,
    IonHeader,
    IonToolbar,
    IonSelect,
    IonSelectOption,
    IonContent,
    onIonViewWillEnter,
    onIonViewDidEnter,
    onIonViewWillLeave,
} from '@ionic/vue';

import { computed, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import MapsContainer from '@/components/MapsContainer.vue';
import { fetchAPI } from '@/services/APIService';

const mapVisible = ref(false);

const route = useRoute();
const role = computed(() =>
    route.query.role === 'driver' ? 'driver' : 'student'
 );

const selectedRoute = ref('');
const selectedVehicle = ref('');
const rotas = ref<{ id: string; nome: string }[]>([]);
const carregandoRotas = ref(false);
const erroRotas = ref(false);
 
watch(
  () => [route.query.role, route.query.routeId, route.query.vehicleId],
  ([currentRole, routeId, vehicleId]) => {
    if (currentRole !== 'driver') return;

    selectedRoute.value =
      typeof routeId === 'string' ? routeId : '';
    
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


const carregarRotas = async () => {
  carregandoRotas.value = true;
  erroRotas.value = false;

  const dados = await fetchAPI('/rotas');
  carregandoRotas.value = false;
  erroRotas.value = dados === null;
  if (dados === null) return;

  rotas.value = dados;
  if (!rotas.value.some((rota) => rota.id === selectedRoute.value)) {
    selectedRoute.value = role.value === 'student' ? rotas.value[0]?.id ?? '' : '';
  }
};

onIonViewWillEnter(carregarRotas);

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
