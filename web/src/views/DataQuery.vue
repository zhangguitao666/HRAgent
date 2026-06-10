<template>
  <div class="page">
    <div class="chat-area">
      <!-- 消息列表 -->
      <div v-for="(m, i) in messages" :key="i" class="mb-6">
        <!-- 用户消息：右边绿色气泡 -->
        <div v-if="m.role === 'user'" class="flex justify-end mb-3">
          <div class="user-bubble">
            <div class="text-sm leading-relaxed text-white">{{ m.content }}</div>
          </div>
        </div>

        <!-- 助手消息 -->
        <div v-else class="min-w-0">
          <!-- 思考过程（琥珀色折叠区） -->
          <div v-if="m.thinking?.length" class="mb-3">
            <div class="think-wrapper">
              <button class="think-header" @click="m._thinkOpen = !m._thinkOpen">
                <div class="flex items-center space-x-2">
                  <span class="think-icon">💡</span>
                  <span class="text-sm font-semibold">AI思考过程</span>
                  <span class="think-badge">思考完成</span>
                </div>
                <span class="think-arrow" :class="{ open: m._thinkOpen }">▼</span>
              </button>
              <div v-if="m._thinkOpen" class="think-body">
                <div v-for="(s, j) in m.thinking" :key="j" class="think-item">
                  <template v-if="s.type === 'tool_call'">
                    <div class="text-xs text-amber-600 mb-1">查询</div>
                    <div class="text-sm text-amber-800">{{ s.content }}</div>
                  </template>
                <template v-else-if="s.type === 'result'">
                  <div class="text-xs text-amber-600">{{ s.content }}</div>
                </template>
                <template v-else-if="s.type === 'think'">
                  <div class="text-xs text-amber-700 opacity-60 italic">{{ s.content }}</div>
                </template>
                  <template v-else-if="s.type === 'error'">
                    <div class="text-xs text-red-500">⚠️ {{ s.content }}</div>
                  </template>
                </div>
              </div>
            </div>
          </div>

          <!-- 正式回答（白色卡片） -->
          <div class="answer-card" v-html="renderMd(m.content)"></div>
        </div>
      </div>

      <!-- 加载中（复用消息列表位置，不额外创建） -->
      <div v-if="loading && !hasLoadingMsg" class="mb-6 min-w-0">
        <div v-if="streamThinking.length" class="mb-3">
          <div class="think-wrapper">
            <button class="think-header">
              <div class="flex items-center space-x-2">
                <span class="think-icon">💡</span>
                <span class="text-sm font-semibold">AI思考过程</span>
                <span class="think-badge live">执行中</span>
              </div>
            </button>
            <div class="think-body">
              <div v-for="(s, j) in streamThinking" :key="j" class="think-item">
                <template v-if="s.type === 'tool_call'">
                  <div class="text-xs text-amber-600 mb-1">查询</div>
                  <div class="text-sm text-amber-800">{{ s.content }}</div>
                </template>
                <template v-else-if="s.type === 'result'">
                  <div class="text-xs text-amber-600">{{ s.content }}</div>
                </template>
              </div>
            </div>
          </div>
        </div>
        <div class="answer-card loading-text">Agent 正在推理...</div>
      </div>
    </div>

    <!-- 底部输入栏 -->
    <div class="input-bar">
      <input v-model="input" placeholder="输入查询，例如：目前在职多少人？" :disabled="loading" @keyup.enter="send" />
      <button @click="send" :disabled="loading || !input.trim()" class="btn-send">发送</button>
      <button @click="messages=[]" class="btn-clear">清空</button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import { marked } from 'marked'
import api from '../api/client.js'

marked.setOptions({ breaks: true, gfm: true })

const messages = ref([])
const input = ref('')
const loading = ref(false)
const streamThinking = ref([])
const hasLoadingMsg = ref(false)
const sessionId = 'query_' + Date.now() + '_' + Math.random().toString(36).slice(2)

function renderMd(text) {
  if (!text) return '<span class="text-gray-400">等待回答...</span>'
  return marked.parse(text)
}

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

  let answerText = ''

  await api.queryAskStream(
    sessionId, text,
    async (thinking) => {
      streamThinking.value = thinking
      messages.value[msgIndex].thinking = thinking
      await nextTick()
    },
    async (token) => {
      answerText += token
      messages.value[msgIndex].content = answerText
      await nextTick()
    },
    ({ thinking, error }) => {
      if (error) messages.value[msgIndex].content = `请求失败：${error}`
      messages.value[msgIndex].thinking = thinking || []
      messages.value[msgIndex]._thinkOpen = false
    }
  )

  loading.value = false
  streamThinking.value = []
  hasLoadingMsg.value = false
}
</script>

<style scoped>
.page { display: flex; flex-direction: column; height: calc(100vh - 100px); }
.chat-area { flex: 1; overflow-y: auto; padding: 0 16px; }

/* 用户气泡 */
.user-bubble {
  max-width: 75%;
  padding: 12px 18px;
  background: linear-gradient(135deg, #009A7A, #255C54);
  border-radius: 16px 16px 4px 16px;
  box-shadow: 0 2px 12px rgba(0,154,122,.25);
}

/* 思考过程 */
.think-wrapper {
  border-radius: 12px;
  border: 1px solid rgba(251,191,36,.3);
  overflow: hidden;
  background: linear-gradient(135deg, #fffbeb, #fff7ed);
}
.think-header {
  width: 100%;
  padding: 10px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: none;
  background: none;
  cursor: pointer;
  color: #92400e;
  font-size: 14px;
}
.think-icon { font-size: 14px; }
.think-badge {
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 6px;
  background: rgba(251,191,36,.3);
  color: #92400e;
  margin-left: 8px;
}
.think-badge.live { background: #fef3c7; animation: pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.5} }
.think-arrow { font-size: 12px; transition: .3s; }
.think-arrow.open { transform: rotate(180deg); }
.think-body { padding: 0 16px 12px; border-top: 1px solid rgba(251,191,36,.2); }
.think-item { margin-top: 8px; }
.sql-block { background: #fef3c7; padding: 8px 12px; border-radius: 6px; font-size: 12px; overflow-x: auto; color: #78350f; }

/* 回答卡片 */
.answer-card {
  padding: 20px 24px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 2px 16px rgba(0,0,0,.06);
  font-size: 14px;
  line-height: 1.8;
  color: #333;
  min-height: 40px;
}
.loading-text { color: #999; font-style: italic; }

/* Markdown 内部样式 */
.answer-card :deep(h1), .answer-card :deep(h2), .answer-card :deep(h3) { font-size: 16px; margin: 10px 0 4px; color: #222; }
.answer-card :deep(p) { margin: 6px 0; }
.answer-card :deep(ul), .answer-card :deep(ol) { padding-left: 18px; margin: 4px 0; }
.answer-card :deep(code) { background: #f5f5f5; padding: 1px 5px; border-radius: 3px; font-size: 13px; }
.answer-card :deep(pre) { background: #f5f5f5; padding: 10px; border-radius: 6px; overflow-x: auto; }
.answer-card :deep(table) { border-collapse: collapse; width: 100%; margin: 8px 0; }
.answer-card :deep(th), .answer-card :deep(td) { border: 1px solid #e8e8e8; padding: 6px 10px; font-size: 13px; }
.answer-card :deep(th) { background: #fafafa; }
.answer-card :deep(strong) { color: #222; }

/* 输入栏 */
.input-bar {
  display: flex; gap: 8px; padding: 12px 16px;
  background: #fff; border-top: 1px solid #f0f0f0; border-radius: 0 0 8px 8px;
}
.input-bar input {
  flex: 1; padding: 10px 16px; border: 1px solid #e5e7eb; border-radius: 10px;
  font-size: 14px; outline: none; transition: .2s;
}
.input-bar input:focus { border-color: #009A7A; box-shadow: 0 0 0 2px rgba(0,154,122,.1); }
.btn-send {
  padding: 10px 22px; border: none; border-radius: 10px;
  background: linear-gradient(135deg, #009A7A, #255C54); color: #fff;
  font-size: 14px; cursor: pointer; transition: .2s;
}
.btn-send:disabled { opacity: .4; cursor: not-allowed; }
.btn-clear {
  padding: 10px 16px; border: 1px solid #e5e7eb; border-radius: 10px;
  background: #fff; color: #666; font-size: 14px; cursor: pointer;
}
</style>
