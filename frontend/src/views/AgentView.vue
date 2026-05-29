<script setup lang="ts">
import { onMounted } from 'vue'

import AgentPanel from '@/components/AgentPanel.vue'
import { useAgentStore } from '@/stores/agent'

const agentStore = useAgentStore()

onMounted(() => {
  agentStore.checkStatus()
})
</script>

<template>
  <div class="agent-view">
    <AgentPanel />
  </div>
</template>

<style scoped>
.agent-view {
  height: 100%;
}
</style>
