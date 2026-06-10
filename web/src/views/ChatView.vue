
<template>
  <div class="chat-container">
    <!-- 消息区域 -->
    <div class="chat-area" ref="chatArea">
      <div v-for="(m, i) in messages" :key="i" class="msg-block">
        <!-- 用户消息 -->
        <div v-if="m.role === 'user'" class="msg-row user-row">
          <div class="user-bubble">{{ m.content }}</div>
        </div>

        <!-- 助手消息 -->
        <div v-else class="msg-row assistant-row">
          <!-- 思考过程 -->
          <div v-if="m.thinking?.length" class="think-outer">
            <div class="think-wrapper">
              <button class="think-header" @click="m._thinkOpen = !m._thinkOpen">
                <div class="think-header-left">
                  <span>💡</span>
                  <span class="think-label">AI 思考过程</span>
                  <span class="think-dot" :class="{ live: loading }"></span>
                </div>
                <span class="think-arrow" :class="{ open: m._thinkOpen }">▼</span>
              </button>
              <div v-if="m._thinkOpen" class="think-body">
                <div v-for="(s, j) in m.thinking" :key="j" class="think-item">
                  <template v-if="s.type === 'tool_call'">
                    <div class="think-tool">🔧 {{ s.content }}</div>
                  </template>
                  <template v-else-if="s.type === 'result'">
                    <div class="think-result">✅ {{ s.content }}</div>
                  </template>
                  <template v-else-if="s.type === 'think'">
                    <div class="think-text">{{ s.content }}</div>
                  </template>
                  <template v-else-if="s.type === 'error'">
                    <div class="think-error">⚠️ {{ s.content }}</div>
                  </template>
                </div>
              </div>
            </div>
          </div>

          <!-- 回答内容 -->
          <div class="answer-card" v-html="renderMd(m.content)"></div>
        </div>
      </div>

      <!-- 加载中 -->
      <div v-if="loading && !hasLoadingMsg" class="msg-row assistant-row">
        <div v-if="streamThinking.length" class="think-outer">
          <div class="think-wrapper">
            <div class="think-header">
              <div class="think-header-left">
                <span>💡</span>
                <span class="think-label">AI 思考过程</span>
                <span class="think-dot live"></span>
              </div>
            </div>
            <div class="think-body">
              <div v-for="(s, j) in streamThinking" :key="j" class="think-item">
                <template v-if="s.type === 'tool_call'">
                  <div class="think-tool">🔧 {{ s.content }}</div>
                </template>
                <template v-else-if="s.type === 'result'">
                  <div class="think-result">✅ {{ s.content }}</div>
                </template>
              </div>
            </div>
          </div>
        </div>
        <div class="answer-card loading-text">思考中...</div>
      </div>
    </div>

    <!-- 输入栏 -->
    <div class="input-bar">
      <textarea
        v-model="input"
        placeholder="输入问题，AI 自动判断查制度还是查数据..."
        :disabled="loading"
        @keydown.enter.exact.prevent="send"
        rows="1"
      ></textarea>
      <button @click="send" :disabled="loading || !input.trim()" class="btn-send">发送</button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, watch, onMounted, onUnmounted } from 'vue'
import { marked } from 'marked'

marked.setOptions({ breaks: true, gfm: true })

const props = defineProps({ sessionId: String })
const emit = defineEmits(['update-title'])

const messages = ref([])
const input = ref('')
const loading = ref(false)
const streamThinking = ref([])
const hasLoadingMsg = ref(false)
const chatArea = ref(null)

function getSessionKey() { return 'hr_msgs_' + (props.sessionId || 'default') }

onMounted(() => {
  const saved = localStorage.getItem(getSessionKey())
  if (saved) messages.value = JSON.parse(saved)
})

onUnmounted(() => {
  // persist before switch
})

watch(() => props.sessionId, (newId) => {
  const key = 'hr_msgs_' + (newId || 'default')
  const saved = localStorage.getItem(key)
  messages.value = saved ? JSON.parse(saved) : []
})

function saveMsgs() {
  localStorage.setItem(getSessionKey(), JSON.stringify(messages.value.slice(-50)))
}

function renderMd(text) {
  if (!text) return '<span style="color:#999">等待回答...</span>'
  return marked.parse(text)
}

function scrollBottom() {
  nextTick(() => {
    if (chatArea.value) chatArea.value.scrollTop = chatArea.value.scrollHeight
  })
}

let abortCtrl = null

async function send() {
  const text = input.value.trim()
  if (!text) return
  messages.value.push({ role: 'user', content: text })
  input.value = ''
  loading.value = true
  streamThinking.value = []

  const msgIndex = messages.value.length
  messages.value.push({ role: 'assistant', content: '', thinking: [], _thinkOpen: true })
  hasLoadingMsg.value = true
  saveMsgs()

  if (messages.value.length === 2) {
    const title = text.length > 20 ? text.slice(0, 20) + '...' : text
    emit('update-title', { id: props.sessionId, title })
  }

  let answerText = ''

  abortCtrl = new AbortController()
  try {
    const response = await fetch('/api/chat/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: text, session_id: props.sessionId }),
      signal: abortCtrl.signal,
    })

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            if (data.type === 'progress') {
              streamThinking.value = data.thinking || []
              messages.value[msgIndex].thinking = data.thinking || []
              await nextTick()
            } else if (data.type === 'token') {
              answerText += data.content || ''
              messages.value[msgIndex].content = answerText
              await nextTick()
              scrollBottom()
            } else if (data.type === 'done') {
              messages.value[msgIndex].thinking = data.thinking || []
              messages.value[msgIndex]._thinkOpen = false
            } else if (data.type === 'error') {
              messages.value[msgIndex].content = `请求失败：${data.content}`
            }
          } catch { /* skip malformed */ }
        }
      }
    }
  } catch (e) {
    if (e.name !== 'AbortError') {
      messages.value[msgIndex].content = '请求失败，请重试'
    }
  }

  loading.value = false
  streamThinking.value = []
  hasLoadingMsg.value = false
  abortCtrl = null
  saveMsgs()
  scrollBottom()
}
</script>

<style scoped>
.chat-container { display: flex; flex-direction: column; height: calc(100vh - 60px); margin-top: 20px; }
.chat-area { flex: 1; overflow-y: auto; padding: 0 40px 20px; max-width: 900px; margin: 0 auto; width: 100%; }

/* 消息行 */
.msg-row { margin-bottom: 20px; }
.user-row { display: flex; justify-content: flex-end; }
.assistant-row { min-width: 0; }

/* 用户气泡 */
.user-bubble {
  max-width: 75%; padding: 12px 18px; font-size: 14px; color: #fff;
  background: linear-gradient(135deg, #1890ff, #096dd9);
  border-radius: 16px 16px 4px 16px;
  box-shadow: 0 2px 12px rgba(24,144,255,.25);
}

/* 思考外层 */
.think-outer { margin-bottom: 10px; }
.think-wrapper {
  border-radius: 12px; border: 1px solid rgba(250,173,20,.25);
  overflow: hidden; background: linear-gradient(135deg, #fffbe6, #fff7e6);
}
.think-header {
  width: 100%; padding: 8px 16px; display: flex; align-items: center;
  justify-content: space-between; border: none; background: none;
  cursor: pointer; font-size: 13px; color: #ad6800;
}
.think-header-left { display: flex; align-items: center; gap: 6px; }
.think-label { font-size: 13px; font-weight: 600; }
.think-dot { width: 8px; height: 8px; border-radius: 50%; background: #ad6800; }
.think-dot.live { background: #fa8c16; animation: pulse 1.5s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
.think-arrow { font-size: 10px; transition: .3s; }
.think-arrow.open { transform: rotate(180deg); }
.think-body { padding: 4px 16px 10px; border-top: 1px solid rgba(250,173,20,.15); }
.think-item { margin-top: 6px; }
.think-tool { font-size: 12px; opacity: .6; margin-bottom: 3px; }
.think-result { font-size: 12px; color: #389e0d; }
.think-text { font-size: 12px; opacity: .5; font-style: italic; }
.think-error { font-size: 12px; color: #ff4d4f; }

/* 回答卡片 */
.answer-card {
  padding: 20px 24px; background: #fff; border-radius: 16px;
  box-shadow: 0 1px 8px rgba(0,0,0,.04); font-size: 14px;
  line-height: 1.9; color: #333; min-height: 40px;
}
.loading-text { color: #999; font-style: italic; }

/* Markdown */
.answer-card :deep(h1), .answer-card :deep(h2), .answer-card :deep(h3) { font-size: 16px; margin: 8px 0 4px; }
.answer-card :deep(p) { margin: 6px 0; }
.answer-card :deep(ul), .answer-card :deep(ol) { padding-left: 20px; margin: 4px 0; }
.answer-card :deep(code) { background: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-size: 13px; }
.answer-card :deep(pre) { background: #f5f5f5; padding: 12px; border-radius: 8px; overflow-x: auto; }
.answer-card :deep(table) { border-collapse: collapse; width: 100%; margin: 8px 0; }
.answer-card :deep(th), .answer-card :deep(td) { border: 1px solid #e8e8e8; padding: 6px 12px; font-size: 13px; }
.answer-card :deep(th) { background: #fafafa; font-weight: 600; }
.answer-card :deep(strong) { color: #222; }

/* 输入栏 */
.input-bar {
  display: flex; gap: 10px; padding: 16px 40px 20px;
  max-width: 900px; margin: 0 auto; width: 100%;
}
.input-bar textarea {
  flex: 1; padding: 12px 16px; border: 1px solid #e5e7eb; border-radius: 12px;
  font-size: 14px; font-family: inherit; outline: none; resize: none;
  transition: .2s; line-height: 1.6;
}
.input-bar textarea:focus { border-color: #1890ff; box-shadow: 0 0 0 3px rgba(24,144,255,.1); }
.btn-send {
  padding: 10px 24px; border: none; border-radius: 12px;
  background: linear-gradient(135deg, #1890ff, #096dd9); color: #fff;
  font-size: 14px; font-weight: 500; cursor: pointer; transition: .2s;
}
.btn-send:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(24,144,255,.35); }
.btn-send:disabled { opacity: .4; cursor: not-allowed; }
</style>
