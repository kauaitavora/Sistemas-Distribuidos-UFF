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
			    :disabled="carregandoRotas || erroRotas"
			    required
			>
				<option value="" disabled>Selecione a rota</option>
				<option
					v-for="rota in rotas"
					:key="rota.id"
					:value="rota.id"
				>
					{{ rota.nome }}
				</option>
			</select>
		    </div>
		</div>
		<div class="selection-field">
		    <label for="driver-vehicle">Veículo</label>
		    <div class="select-wrapper">
			<select id="driver-vehicle"
				v-model="selectedVehicle"
				name="vehicleId"
				:disabled="carregandoVeiculos || erroVeiculos || !veiculos.length"
				required
			>
				<option value="" disabled>Selecione o veículo</option>
				<option
					v-for="veiculo in veiculos"
					:key="veiculo.id"
					:value="veiculo.id"
				>
					{{ veiculo.nome ?? veiculo.id }}
				</option>
			</select>
		    </div>
		</div>
		<p v-if="carregandoRotas" role="status">Carregando rotas...</p>
		<div v-else-if="erroRotas">
		    <p role="alert">Não foi possível carregar as rotas.</p>
		    <ion-button fill="clear" @click="carregarRotas">Tentar novamente</ion-button>
		</div>
		<p v-else-if="!rotas.length" role="status">Nenhuma rota disponível.</p>
		<p v-if="carregandoVeiculos" role="status">Carregando veículos...</p>
		<div v-else-if="erroVeiculos">
		    <p role="alert">Não foi possível carregar os veículos.</p>
		    <ion-button fill="clear" @click="carregarVeiculos">Tentar novamente</ion-button>
		</div>
		<p v-else-if="!veiculos.length" role="status">Nenhum veículo disponível.</p>
		<ion-button color="primary" expand="block" fill="solid"
		    :disabled="carregandoRotas || carregandoVeiculos || erroRotas || erroVeiculos || !selectedRoute || !selectedVehicle"
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
import { IonButton, IonContent, IonPage, onIonViewWillEnter } from '@ionic/vue';
import { useRouter } from 'vue-router';
import { ref } from 'vue';
import { useRoute } from 'vue-router';
import { fetchAPI } from '@/services/APIService';
    
const router = useRouter();
const route = useRoute();

const selectedRoute = ref('');
const selectedVehicle = ref('');
 
const rotas = ref<{ id: string; nome: string }[]>([]);
const veiculos = ref<{ id: string; nome: string | null }[]>([]);
const carregandoRotas = ref(false);
const carregandoVeiculos = ref(false);
const erroRotas = ref(false);
const erroVeiculos = ref(false);

function startTrip() {
  if (
    carregandoRotas.value || carregandoVeiculos.value ||
    erroRotas.value || erroVeiculos.value ||
    !selectedRoute.value || !selectedVehicle.value
  ) return;

  return router.push({
    path: '/tabs/tab1',
    query: {
      role: route.query.role,
      routeId: selectedRoute.value,
      vehicleId: selectedVehicle.value,
    },
  });
}


const carregarRotas = async () => {
  carregandoRotas.value = true;
  erroRotas.value = false;

  const dados = await fetchAPI('/rotas');
  carregandoRotas.value = false;
  erroRotas.value = dados === null;
  if (dados === null) return;

  rotas.value = dados;
  if (!rotas.value.some((rota) => rota.id === selectedRoute.value)) {
    selectedRoute.value = '';
  }
};

const carregarVeiculos = async () => {
  carregandoVeiculos.value = true;
  erroVeiculos.value = false;

  const dados = await fetchAPI('/veiculos');
  carregandoVeiculos.value = false;
  erroVeiculos.value = dados === null;
  if (dados === null) return;

  veiculos.value = dados;
  if (!veiculos.value.some((veiculo) => veiculo.id === selectedVehicle.value)) {
    selectedVehicle.value = '';
  }
};

onIonViewWillEnter(carregarRotas);
onIonViewWillEnter(carregarVeiculos);

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
