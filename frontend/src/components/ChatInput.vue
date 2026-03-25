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
  background: #252526;
  border-radius: 12px;
}

.chat-input input {
  flex: 1;
  padding: 12px 16px;
  background: #1e1e1e;
  border: 1px solid #333;
  border-radius: 8px;
  color: #fff;
  font-size: 14px;
}

.chat-input input:focus {
  outline: none;
  border-color: #4fc3f7;
}

.chat-input input:disabled {
  opacity: 0.5;
}

.chat-input button {
  padding: 12px 24px;
  background: #4fc3f7;
  color: #000;
  border: none;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.chat-input button:hover:not(:disabled) {
  background: #81d4fa;
}

.chat-input button:disabled {
  background: #444;
  color: #888;
  cursor: not-allowed;
}
</style>
