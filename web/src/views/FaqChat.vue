<template>
  <div>
    <h1>💬 HR FAQ 智能问答</h1>
    <p class="sub">有什么关于公司制度的问题？尽管问我！</p>

    <div class="chat-box" ref="chatBox">
      <div v-for="(m, i) in messages" :key="i" :class="['msg', m.role]">
        <div class="bubble">{{ m.content }}</div>
      </div>
      <div v-if="loading" class="msg assistant"><div class="bubble">思考中...</div></div>
    </div>

    <form @submit.prevent="send" class="input-row">
      <input v-model="input" placeholder="输入你的问题..." :disabled="loading" />
      <button type="submit" :disabled="loading || !input.trim()">发送</button>
      <button type="button" @click="messages = []" class="btn-clear">清空</button>
    </form>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import api from '../api/client.js'

const messages = ref([])
const input = ref('')
const loading = ref(false)
const chatBox = ref(null)

async function send() {
  const text = input.value.trim()
  if (!text) return
  messages.value.push({ role: 'user', content: text })
  input.value = ''
  loading.value = true
  await nextTick(); scrollBottom()
  try {
    const res = await api.faqChat(text)
    messages.value.push({ role: 'assistant', content: res.reply })
  } catch {
    messages.value.push({ role: 'assistant', content: '请求失败，请重试' })
  }
  loading.value = false
  await nextTick(); scrollBottom()
}

function scrollBottom() {
  if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight
}
</script>

<style scoped>
h1 { font-size: 22px; margin-bottom: 4px; }
.sub { color: #888; font-size: 13px; margin-bottom: 20px; }
.chat-box { background: #fff; border-radius: 8px; padding: 20px; height: 400px; overflow-y: auto; margin-bottom: 16px; }
.msg { margin-bottom: 14px; display: flex; }
.msg.user { justify-content: flex-end; }
.msg.user .bubble { background: #1890ff; color: #fff; }
.msg.assistant .bubble { background: #f0f2f5; }
.bubble { max-width: 70%; padding: 10px 14px; border-radius: 8px; font-size: 14px; line-height: 1.6; white-space: pre-wrap; }
.input-row { display: flex; gap: 8px; }
.input-row input { flex: 1; padding: 10px 14px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 14px; }
button { padding: 10px 18px; background: #1890ff; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
button:disabled { opacity: .5; cursor: not-allowed; }
.btn-clear { background: #f5f5f5; color: #666; }
</style>
