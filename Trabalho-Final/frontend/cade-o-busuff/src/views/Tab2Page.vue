<template>
  <ion-page>
    <ion-header>
      <ion-toolbar>
        <ion-title>Horários</ion-title>
      </ion-toolbar>
    </ion-header>
    <ion-content class="ion-padding">
      <ion-select
        v-model="selectedRoute"
        label="Rota"
        label-placement="stacked"
        interface="popover"
        placeholder="Selecione a rota"
        :disabled="carregandoRotas || erroRotas || !rotas.length"
        @ionChange="carregarHorarios"
      >
        <ion-select-option v-for="rota in rotas" :key="rota.id" :value="rota.id">
          {{ rota.nome }}
        </ion-select-option>
      </ion-select>

      <p v-if="carregandoRotas" role="status">Carregando rotas...</p>
      <div v-else-if="erroRotas">
        <p role="alert">Não foi possível carregar as rotas.</p>
        <ion-button fill="clear" @click="carregarRotas">Tentar novamente</ion-button>
      </div>
      <p v-else-if="!rotas.length" role="status">Nenhuma rota disponível.</p>

      <section v-else-if="selectedRoute">
        <h2>Saídas programadas</h2>
        <p v-if="carregandoHorarios" role="status">Carregando horários...</p>
        <div v-else-if="erroHorarios">
          <p role="alert">Não foi possível carregar os horários.</p>
          <ion-button fill="clear" @click="carregarHorarios">Tentar novamente</ion-button>
        </div>
        <p v-else-if="!horarios.length" role="status">Nenhum horário cadastrado para esta rota.</p>
        <div v-else>
          <ion-list aria-label="Horários de saída">
            <ion-item v-for="horario in horarios" :key="horario.id">
              <ion-label>
                <time :datetime="horario.hora_saida">{{ horario.hora_saida.slice(0, 5) }}</time>
              </ion-label>
            </ion-item>
          </ion-list>
          <p>Horário de Brasília.</p>
        </div>
      </section>
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import {
  IonPage, IonHeader, IonToolbar, IonTitle, IonContent, IonSelect,
  IonSelectOption, IonList, IonItem, IonLabel, IonButton, onIonViewWillEnter,
} from '@ionic/vue';
import { ref } from 'vue';
import { fetchAPI } from '@/services/APIService';

const selectedRoute = ref('');
const rotas = ref<{ id: string; nome: string }[]>([]);
const horarios = ref<{ id: number; rota_id: string; hora_saida: string }[]>([]);
const carregandoRotas = ref(false);
const carregandoHorarios = ref(false);
const erroRotas = ref(false);
const erroHorarios = ref(false);

const carregarHorarios = async () => {
  const rotaId = selectedRoute.value;
  horarios.value = [];
  erroHorarios.value = false;
  carregandoHorarios.value = false;
  if (!rotaId) return;

  carregandoHorarios.value = true;
  const dados = await fetchAPI(`/rotas/${encodeURIComponent(rotaId)}/horarios`);

  // Uma resposta antiga não deve substituir os horários de outra rota.
  if (rotaId !== selectedRoute.value) return;

  carregandoHorarios.value = false;
  erroHorarios.value = dados === null;
  if (dados !== null) horarios.value = dados;
};

const carregarRotas = async () => {
  carregandoRotas.value = true;
  erroRotas.value = false;

  const dados = await fetchAPI('/rotas');
  carregandoRotas.value = false;
  erroRotas.value = dados === null;
  if (dados === null) return;

  rotas.value = dados;
  if (!rotas.value.some((rota) => rota.id === selectedRoute.value)) {
    selectedRoute.value = rotas.value[0]?.id ?? '';
  }
  await carregarHorarios();
};

onIonViewWillEnter(carregarRotas);
</script>
