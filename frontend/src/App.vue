<script setup lang="ts">
import FooterBar from './components/FooterBar.vue'
import NavBar from './components/NavBar.vue'
import ServerBanner from './components/ServerBanner.vue'
</script>

<template>
  <NavBar />
  <ServerBanner />
  <main class="mx-auto w-full max-w-6xl px-4 pb-16 pt-6 sm:px-6">
    <RouterView v-slot="{ Component }">
      <Transition name="page" mode="out-in">
        <component :is="Component" />
      </Transition>
    </RouterView>
  </main>
  <FooterBar />
</template>

<style>
.page-enter-active,
.page-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}
.page-enter-from,
.page-leave-to {
  opacity: 0;
  transform: translateY(6px);
}
</style>
