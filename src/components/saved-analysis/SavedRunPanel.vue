<script setup lang="ts">
import type { Component } from 'vue'
defineProps<{ title: string; icon?: Component; flat?: boolean }>()
</script>

<template>
  <section class="saved-run-card">
    <header class="saved-run-card-head">
      <component :is="icon" v-if="icon" class="saved-run-card-icon" />
      <h2>{{ title }}</h2>
      <slot name="heading" />
      <div v-if="$slots.actions" class="saved-run-card-actions"><slot name="actions" /></div>
    </header>
    <div :class="{ 'saved-run-card-body': !flat }"><slot /></div>
    <footer v-if="$slots.footer" class="saved-run-card-foot"><slot name="footer" /></footer>
  </section>
</template>
