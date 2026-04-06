<script setup>
import { ref } from 'vue'

const props = defineProps({
  disabled: Boolean
})

const emit = defineEmits(['submit'])

const input = ref('')

function submit() {
  if (input.value.trim() && !props.disabled) {
    emit('submit', input.value.trim())
    input.value = ''
  }
}
</script>

<template>
  <div class="chat-input">
    <input
      v-model="input"
      type="text"
      placeholder="输入你的编程问题..."
      :disabled="disabled"
      @keyup.enter="submit"
    />
    <button @click="submit" :disabled="disabled || !input.trim()">
      发送
    </button>
  </div>
</template>

<style scoped>
.chat-input {
  display: flex;
  gap: 12px;
  padding: 16px;
  background: var(--bg1);
  border-radius: 12px;
}

.chat-input input {
  flex: 1;
  padding: 14px 18px;
  background: var(--bg0);
  border: 1px solid var(--bg3);
  border-radius: 8px;
  color: var(--fg);
  font-size: var(--font-base);
}

.chat-input input::placeholder {
  color: var(--grey1);
  font-size: var(--font-base);
}

.chat-input input:focus {
  outline: none;
  border-color: var(--blue);
}

.chat-input input:disabled {
  opacity: 0.5;
}

.chat-input button {
  padding: 14px 28px;
  background: var(--blue);
  color: var(--bg0);
  border: none;
  border-radius: 8px;
  font-size: var(--font-base);
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.chat-input button:hover:not(:disabled) {
  background: var(--aqua);
}

.chat-input button:disabled {
  background: var(--bg3);
  color: var(--grey1);
  cursor: not-allowed;
}
</style>
