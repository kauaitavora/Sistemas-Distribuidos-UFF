<template>
  <ion-page>
    <ion-header>
      <ion-toolbar>
        <ion-title>Tab 1</ion-title>
      </ion-toolbar>
    </ion-header>
    <ion-content class="map-content" :scroll-y="false">
      <MapsContainer v-if="mapVisible" />
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">

import {
  IonPage,
  IonHeader,
  IonToolbar,
  IonTitle,
  IonContent,
  onIonViewDidEnter,
  onIonViewWillLeave,
} from '@ionic/vue';

import { ref } from 'vue';

import MapsContainer from '@/components/MapsContainer.vue';

const mapVisible = ref(false);

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
