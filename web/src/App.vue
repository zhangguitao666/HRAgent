<template>
  <div class="app">
    <!-- 左侧会话管理 -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <h2>HR 智能助手</h2>
        <div class="nav-tabs">
          <button :class="['nav-tab', { active: page === 'chat' }]" @click="page = 'chat'">💬 对话</button>
          <button :class="['nav-tab', { active: page === 'kb' }]" @click="page = 'kb'">📚 知识库</button>
        </div>
      </div>
      <div v-if="page === 'chat'" class="session-area">
        <button class="btn-new" @click="newSession">+ 新会话</button>
        <div class="session-list">
          <div
            v-for="s in sessions"
            :key="s.id"
            :class="['session-item', { active: s.id === currentId }]"
            @click="switchSession(s.id)"
          >
            <div class="session-title">{{ s.title }}</div>
            <div class="session-time">{{ s.time }}</div>
            <button class="btn-del" @click.stop="deleteSession(s.id)">✕</button>
          </div>
        </div>
        <div v-if="!sessions.length" class="no-sessions">点击"新会话"开始</div>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="content">
      <ChatView
        v-if="page === 'chat'"
        :session-id="currentId"
        :key="currentId"
        @update-title="updateTitle"
      />
      <KbManage v-else-if="page === 'kb'" />
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import ChatView from './views/ChatView.vue'
import KbManage from './views/KbManage.vue'

const page = ref('chat')
const sessions = ref([])
const currentId = ref('')

onMounted(() => {
  const saved = localStorage.getItem('hr_sessions')
  if (saved) {
    sessions.value = JSON.parse(saved)
    if (sessions.value.length) currentId.value = sessions.value[0].id
  }
  if (!currentId.value) newSession()
})

function newSession() {
  const id = 's_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8)
  const now = new Date().toLocaleString('zh-CN')
  sessions.value.unshift({ id, title: '新会话', time: now })
  currentId.value = id
  saveSessions()
}

function switchSession(id) {
  currentId.value = id
}

function deleteSession(id) {
  sessions.value = sessions.value.filter(s => s.id !== id)
  if (currentId.value === id) {
    currentId.value = sessions.value.length ? sessions.value[0].id : ''
  }
  saveSessions()
}

function updateTitle({ id, title }) {
  const s = sessions.value.find(s => s.id === id)
  if (s) {
    s.title = title.length > 20 ? title.slice(0, 20) + '...' : title
    saveSessions()
  }
}

function saveSessions() {
  localStorage.setItem('hr_sessions', JSON.stringify(sessions.value))
}
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f2f5; color: #333; }
.app { display: flex; min-height: 100vh; }
.sidebar {
  width: 260px; background: #fff; border-right: 1px solid #e8e8e8;
  display: flex; flex-direction: column; flex-shrink: 0;
}
.sidebar-header { padding: 20px 16px 12px; border-bottom: 1px solid #f0f0f0; }
.sidebar-header h2 { font-size: 16px; margin-bottom: 12px; }
.nav-tabs { display: flex; gap: 6px; margin-bottom: 10px; }
.nav-tab {
  flex: 1; padding: 7px 0; border: 1px solid #e8e8e8; border-radius: 6px;
  background: #fff; color: #666; font-size: 12px; cursor: pointer; transition: .15s;
}
.nav-tab.active { border-color: #1890ff; background: #e6f7ff; color: #1890ff; font-weight: 500; }
.nav-tab:hover:not(.active) { background: #fafafa; }
.session-area { display: flex; flex-direction: column; flex: 1; overflow: hidden; }
.btn-new {
  width: 100%; padding: 8px; border: 1px dashed #d9d9d9; border-radius: 8px;
  background: #fafafa; color: #555; font-size: 13px; cursor: pointer; transition: .2s;
}
.btn-new:hover { border-color: #1890ff; color: #1890ff; background: #e6f7ff; }
.session-list { flex: 1; overflow-y: auto; padding: 8px; }
.session-item {
  padding: 10px 12px; border-radius: 8px; cursor: pointer; margin-bottom: 4px;
  position: relative; transition: .15s;
}
.session-item:hover { background: #f5f5f5; }
.session-item.active { background: #e6f7ff; }
.session-title { font-size: 13px; font-weight: 500; margin-bottom: 2px; padding-right: 20px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.session-time { font-size: 11px; color: #999; }
.btn-del {
  position: absolute; right: 8px; top: 10px; width: 20px; height: 20px;
  border: none; background: none; color: #ccc; font-size: 12px; cursor: pointer;
  border-radius: 4px; display: flex; align-items: center; justify-content: center;
}
.btn-del:hover { background: #ff4d4f; color: #fff; }
.no-sessions { padding: 40px 20px; text-align: center; color: #ccc; font-size: 13px; }
.content { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
</style>
