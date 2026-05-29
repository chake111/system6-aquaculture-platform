<script setup lang="ts">
defineProps<{
  message: string
}>()

const emit = defineEmits<{
  retry: []
}>()
</script>

<template>
  <section class="banner warning-banner" role="alert">
    <div>
      <strong>数据没拉到</strong>
      <span>{{ message }}</span>
    </div>
    <button class="banner-action" type="button" @click="emit('retry')">重试</button>
  </section>
</template>
