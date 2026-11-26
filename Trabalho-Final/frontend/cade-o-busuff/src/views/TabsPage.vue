<template>
  <ion-page>
    <ion-tabs>
      <ion-router-outlet></ion-router-outlet>
      <ion-tab-bar slot="bottom">
        <ion-tab-button tab="tab1" href="/tabs/map">
          <ion-icon aria-hidden="true" :icon="map" />
          <ion-label>Mapa</ion-label>
        </ion-tab-button>

        <ion-tab-button tab="tab2" href="/tabs/routes">
          <ion-icon aria-hidden="true" :icon="list" />
          <ion-label>Rotas</ion-label>
        </ion-tab-button>
      </ion-tab-bar>
    </ion-tabs>
  </ion-page>
</template>

<script setup lang="ts">
import { IonTabBar, IonTabButton, IonTabs, IonLabel, IonIcon, IonPage, IonRouterOutlet } from '@ionic/vue';
import { ellipse, list, map, square, triangle } from 'ionicons/icons';
</script>
