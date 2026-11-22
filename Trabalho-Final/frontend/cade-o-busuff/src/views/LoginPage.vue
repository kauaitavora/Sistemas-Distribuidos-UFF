<template>
  <ion-page>
    <ion-content>
      <main class="role-selection">
        <div class="welcome">
          <p class="app-name">Cadê o BusUFF?</p>
          <h1>Como você vai usar o app?</h1>
          <p class="subtitle">Escolha seu perfil para continuar.</p>

          <div class="role-options">
            <button type="button" class="role-card" @click="selectRole('driver')">
              <ion-icon :icon="busOutline" aria-hidden="true" />
              <span>Motorista</span>
            </button>

            <button type="button" class="role-card" @click="selectRole('student')">
              <ion-icon :icon="schoolOutline" aria-hidden="true" />
              <span>Aluno</span>
            </button>
          </div>
        </div>
      </main>
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { IonContent, IonIcon, IonPage } from '@ionic/vue';
import { busOutline, schoolOutline } from 'ionicons/icons';
import { useRouter } from 'vue-router';

const router = useRouter();

function selectRole(role: 'driver' | 'student') {
     return router.push({ path: '/tabs/tab1', query: { role } });
}

</script>

<style scoped>
.role-selection {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100%;
  padding: calc(32px + var(--ion-safe-area-top, 0px)) 24px calc(32px + var(--ion-safe-area-bottom, 0px));
}

.welcome {
  width: 100%;
  max-width: 560px;
  text-align: center;
}

.app-name {
  margin: 0 0 24px;
  color: var(--ion-color-primary);
  font-size: 18px;
  font-weight: 700;
}

h1 {
  margin: 0;
  font-size: clamp(26px, 5vw, 36px);
  font-weight: 700;
  line-height: 1.2;
}

.subtitle,
.access-note {
  color: var(--ion-text-color-step-400, #666);
  line-height: 1.5;
}

.subtitle {
  margin: 16px 0 32px;
}

.role-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.role-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
  width: 100%;
  aspect-ratio: 1;
  padding: 16px;
  border: 2px solid var(--ion-background-color-step-150, #e1e5eb);
  border-radius: 20px;
  background: var(--ion-background-color-step-50, #f7f9fc);
  color: var(--ion-text-color, #171c26);
  font: inherit;
  font-size: clamp(18px, 3vw, 24px);
  font-weight: 600;
  cursor: pointer;
}

.role-card ion-icon {
  color: var(--ion-color-primary);
  font-size: clamp(44px, 8vw, 64px);
}

@media (hover: hover) {
  .role-card:hover {
    border-color: var(--ion-color-primary);
  }
}

.role-card:focus-visible {
  outline: 3px solid var(--ion-color-primary);
  outline-offset: 4px;
}

.role-card:active {
  border-color: var(--ion-color-primary);
  background: var(--ion-background-color-step-100, #edf2f8);
}

.access-note {
  margin: 24px 0 0;
  font-size: 14px;
}
</style>
