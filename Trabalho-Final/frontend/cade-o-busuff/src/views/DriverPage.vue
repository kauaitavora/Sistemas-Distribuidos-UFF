<template>
<ion-page>
<ion-content>
    <main class="driver-page">
	<div class="driving-settings">
	    <h1>Escolha a rota e o veículo</h1>
	    <div class="driving-options">
		<div class="selection-field">
		    <label for="driver-route">Rota</label>
		    <div class="select-wrapper">
			<select
			    id="driver-route"
			    v-model="selectedRoute"
			    name="routeId"
			    required
			>
				    <option value="" disabled>Selecione a rota</option>
			    <option value="rota-1">Rota 1</option>
			    <option value="rota-2">Rota 2</option>
			    <option value="rota-3">Rota 3</option>
			</select>
		    </div>
		</div>
		<div class="selection-field">
		    <label for="driver-vehicle">Veículo</label>
		    <div class="select-wrapper">
			<select id="driver-vehicle"
				v-model="selectedVehicle"
				name="vehicleId"
				required
			>
				    <option value="" disabled>Selecione o veículo</option>
			    <option value="onibus-01">Ônibus 1</option>
			    <option value="onibus-02">Ônibus 2</option>
			    <option value="onibus-03">Ônibus 3</option>
			</select>
		    </div>
		</div>
		<ion-button color="primary" expand="block" fill="solid"
		    :disabled="!selectedRoute || !selectedVehicle"
		    @click="startTrip"
		>
		Iniciar viagem
		</ion-button>
	    </div>
	</div>
    </main>
</ion-content>
</ion-page>
</template>

<script setup lang="ts">
import { IonContent, IonIcon, IonPage, IonButton } from '@ionic/vue';
import { busOutline, schoolOutline } from 'ionicons/icons';
import { useRouter } from 'vue-router';
import { computed, ref } from 'vue';
import { useRoute } from 'vue-router';
    
const router = useRouter();
const route = useRoute();
const selectedRoute = ref('');
const selectedVehicle = ref('');

function startTrip() {
  if (!selectedRoute.value || !selectedVehicle.value) return;

  return router.push({
    path: '/tabs/tab1',
    query: {
      role: route.query.role,
      routeId: selectedRoute.value,
      vehicleId: selectedVehicle.value,
    },
  });
}

</script>

<style scoped>

.driver-page {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100%;
    padding: calc(32px + var(--ion-safe-area-top, 0px)) 24px calc(32px + var(--ion-safe-area-bottom, 0px));
}

.driving-settings {
    width: 100%;
    max-width: 560px;
    text-align: center;
}

h1 {
    margin: 0;
    font-size: clamp(26px, 5vw, 36px);
    font-weight: 700;
    line-height: 1.2;
}

.driving-options {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 16px;
    margin-top: 32px;
}

.selection-field {
    min-width: 0;
    text-align: left;
}

.selection-field label {
    display: block;
    margin-bottom: 10px;
    color: var(--ion-text-color, #171c26);
    font-size: 16px;
    font-weight: 600;
}

.select-wrapper {
    position: relative;
}

.select-wrapper::after {
    content: '';
    position: absolute;
    top: 50%;
    right: 20px;
    width: 8px;
    height: 8px;
    border-right: 2px solid var(--ion-color-primary, #0054e9);
    border-bottom: 2px solid var(--ion-color-primary, #0054e9);
    transform: translateY(-70%) rotate(45deg);
    pointer-events: none;
}

.selection-field select {
    appearance: none;
    box-sizing: border-box;
    width: 100%;
    min-height: 60px;
    padding: 16px 48px 16px 16px;
    border: 2px solid var(--ion-background-color-step-150, #e1e5eb);
    border-radius: 16px;
    background: var(--ion-background-color-step-50, #f7f9fc);
    color: var(--ion-text-color, #171c26);
    font: inherit;
    font-size: 16px;
    cursor: pointer;
}

.selection-field select:invalid {
    color: var(--ion-text-color-step-400, #666);
}

.selection-field select:focus-visible {
    border-color: var(--ion-color-primary, #0054e9);
    outline: 3px solid var(--ion-color-primary, #0054e9);
    outline-offset: 3px;
}

@media (hover: hover) {
    .selection-field select:hover {
        border-color: var(--ion-color-primary, #0054e9);
    }
}

</style>
