<template>
  <div>
    <h1>🚪 员工入转调离指引</h1>
    <div class="tabs">
      <button v-for="t in tabs" :key="t.key" :class="{ active: current === t.key }" @click="switchTab(t.key)">
        {{ t.label }}
      </button>
    </div>

    <div class="chat-box" ref="chatBox">
      <div v-for="(m, i) in messages" :key="i" :class="['msg', m.role]">
        <div class="bubble">{{ m.content }}</div>
      </div>
      <div v-if="loading" class="msg assistant"><div class="bubble">思考中...</div></div>
    </div>

    <form @submit.prevent="send" class="input-row">
      <input v-model="input" placeholder="请输入你的问题..." :disabled="loading" />
      <button type="submit" :disabled="loading || !input.trim()">发送</button>
    </form>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import api from '../api/client.js'

const tabs = [
  { key: 'onboarding', label: '入职引导' },
  { key: 'regularization', label: '转正引导' },
  { key: 'resignation', label: '离职引导' },
  { key: 'retirement', label: '退休引导' },
]
const current = ref('onboarding')
const messages = ref([])
const input = ref('')
const loading = ref(false)
const chatBox = ref(null)

watch(current, () => { messages.value = [] })

async function send() {
  const text = input.value.trim()
  if (!text) return
  messages.value.push({ role: 'user', content: text })
  input.value = ''
  loading.value = true
  await nextTick(); scrollBottom()
  try {
    const res = await api.lifecycleChat(current.value, text)
    messages.value.push({ role: 'assistant', content: res.reply })
  } catch {
    messages.value.push({ role: 'assistant', content: '请求失败' })
  }
  loading.value = false
  await nextTick(); scrollBottom()
}

function switchTab(key) { current.value = key }

function scrollBottom() {
  if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight
}
</script>

<style scoped>
h1 { font-size: 22px; margin-bottom: 16px; }
.tabs { display: flex; gap: 8px; margin-bottom: 16px; }
.tabs button { padding: 8px 20px; border: 1px solid #d9d9d9; background: #fff; border-radius: 6px; cursor: pointer; font-size: 13px; }
.tabs button.active { background: #1890ff; color: #fff; border-color: #1890ff; }
.chat-box { background: #fff; border-radius: 8px; padding: 20px; height: 360px; overflow-y: auto; margin-bottom: 16px; }
.msg { margin-bottom: 14px; display: flex; }
.msg.user { justify-content: flex-end; }
.msg.user .bubble { background: #1890ff; color: #fff; }
.msg.assistant .bubble { background: #f0f2f5; }
.bubble { max-width: 70%; padding: 10px 14px; border-radius: 8px; font-size: 14px; line-height: 1.6; white-space: pre-wrap; }
.input-row { display: flex; gap: 8px; }
.input-row input { flex: 1; padding: 10px 14px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 14px; }
.input-row button { padding: 10px 18px; background: #1890ff; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
.input-row button:disabled { opacity: .5; }
</style>
