<template>
  <ion-page>
    <ion-tabs>
      <ion-router-outlet></ion-router-outlet>
      <ion-tab-bar v-if="route.query.role === 'student'" slot="bottom">
        <ion-tab-button tab="tab1" href="/tabs/tab1?role=student">
          <ion-icon aria-hidden="true" :icon="map" />
          <ion-label>Mapa</ion-label>
        </ion-tab-button>
        <ion-tab-button tab="tab2" href="/tabs/tab2?role=student">
          <ion-icon aria-hidden="true" :icon="time" />
          <ion-label>Horários</ion-label>
        </ion-tab-button>
      </ion-tab-bar>
    </ion-tabs>
  </ion-page>
</template>

<script setup lang="ts">
import { IonTabBar, IonTabButton, IonTabs, IonLabel, IonPage, IonRouterOutlet } from '@ionic/vue';
import { map, time } from 'ionicons/icons';
import { useRoute } from 'vue-router';

const route = useRoute();
</script>
