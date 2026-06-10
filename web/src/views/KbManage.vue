
<template>
  <div class="kb-page">
    <div class="kb-header">
      <h2>📚 知识库管理</h2>
      <span class="doc-count">{{ totalDocs }} 文档块</span>
    </div>

    <!-- 文件上传区 -->
    <div
      class="upload-zone"
      :class="{ dragging }"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
    >
      <input ref="fileInput" type="file" accept=".txt,.md,.pdf,.docx" multiple @change="onFileSelect" hidden />
      <div class="upload-inner" @click="$refs.fileInput.click()">
        <div class="upload-icon">📁</div>
        <div class="upload-text">拖拽文件到此处，或点击选择</div>
        <div class="upload-hint">支持 .txt .md .pdf .docx，自动分块嵌入</div>
      </div>
    </div>

    <!-- 文本粘贴区 -->
    <details class="text-zone">
      <summary class="text-zone-title">📝 手动粘贴文本</summary>
      <textarea v-model="newText" placeholder="粘贴制度文本..." rows="5"></textarea>
      <div class="text-zone-row">
        <input v-model="newSource" placeholder="来源名称" />
        <button @click="addText" :disabled="!newText.trim() || adding">添加</button>
      </div>
    </details>

    <!-- 来源列表 -->
    <div class="source-list">
      <div v-if="loading" class="loading">加载中...</div>
      <div v-else-if="!sources.length" class="empty">知识库为空，请上传文档</div>

      <div v-for="src in sources" :key="src.source" class="source-card">
        <div class="source-header">
          <div class="source-info">
            <span class="source-name">{{ src.source }}</span>
            <span class="source-meta">{{ src.chunk_count }} 个块 · {{ formatSize(src.total_chars) }}</span>
          </div>
          <div class="source-actions">
            <button class="btn-sm" @click="toggleChunks(src.source)">{{ expandedSrc === src.source ? '收起' : '分块详情' }}</button>
            <button class="btn-sm" @click="openRechunk(src)">⚙ 重新分块</button>
            <button class="btn-sm danger" @click="delSource(src.source)">删除</button>
          </div>
        </div>
        <div class="source-preview">{{ src.sample }}</div>

        <!-- 分块详情 -->
        <div v-if="expandedSrc === src.source" class="chunks-panel">
          <div v-if="chunksLoading" class="loading-sm">加载块...</div>
          <div v-for="chunk in chunks" :key="chunk.id" class="chunk-item">
            <div class="chunk-header">
              <span class="chunk-label">块 {{ chunks.indexOf(chunk) + 1 }} / {{ chunks.length }}</span>
              <span class="chunk-size">{{ chunk.length }} 字符</span>
              <button class="btn-xs" @click="toggleChunkView(chunk.id)">
                {{ viewingChunk === chunk.id ? '收起' : '全文' }}
              </button>
              <button class="btn-xs danger" @click="delChunk(chunk.id)">✕</button>
            </div>
            <div class="chunk-preview">{{ chunk.preview }}</div>
            <div v-if="viewingChunk === chunk.id" class="chunk-full">
              <pre>{{ chunkDetail?.content || '加载中...' }}</pre>
            </div>
          </div>
          <div v-if="!chunks.length && !chunksLoading" class="loading-sm">无块数据</div>
        </div>
      </div>
    </div>

    <!-- 重新分块弹窗 -->
    <div v-if="rechunkSrc" class="modal-overlay" @click.self="rechunkSrc = null">
      <div class="modal-box">
        <h3>重新分块 — {{ rechunkSrc.source }}</h3>
        <div class="form-row">
          <label>块大小：<input v-model.number="rechunkSize" type="number" min="100" max="2000" /></label>
          <label>重叠：<input v-model.number="rechunkOverlap" type="number" min="0" max="500" /></label>
        </div>
        <div class="modal-actions">
          <button class="btn-modal cancel" @click="rechunkSrc = null">取消</button>
          <button class="btn-modal" @click="doRechunk" :disabled="rechunking">执行</button>
        </div>
      </div>
    </div>

    <div v-if="msg" class="toast" :class="{ error: msgError }">{{ msg }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const fileInput = ref(null)
const sources = ref([])
const totalDocs = ref(0)
const loading = ref(true)
const dragging = ref(false)

const newText = ref('')
const newSource = ref('')
const adding = ref(false)

const expandedSrc = ref('')
const chunks = ref([])
const chunksLoading = ref(false)
const viewingChunk = ref('')
const chunkDetail = ref(null)

const rechunkSrc = ref(null)
const rechunkSize = ref(500)
const rechunkOverlap = ref(80)
const rechunking = ref(false)

const msg = ref('')
const msgError = ref(false)

async function loadSources() {
  loading.value = true
  try {
    const res = await fetch('/api/knowledge/sources').then(r => r.json())
    sources.value = res.sources || []
    totalDocs.value = res.total_docs || 0
  } catch (e) { toast('加载失败: ' + e.message, true) }
  loading.value = false
}

// ── 文件上传 ──

function onDrop(e) {
  dragging.value = false
  uploadFiles(e.dataTransfer.files)
}
function onFileSelect(e) {
  uploadFiles(e.target.files)
  e.target.value = ''
}
async function uploadFiles(files) {
  for (const file of files) {
    const form = new FormData()
    form.append('file', file)
    try {
      const res = await fetch('/api/knowledge/upload-file', { method: 'POST', body: form }).then(r => r.json())
      if (res.ok) toast(`✅ ${res.source} — ${res.chunks_added} 个块`)
      else toast(res.error, true)
    } catch (e) { toast('上传失败: ' + e.message, true) }
  }
  await loadSources()
}

// ── 文本添加 ──

async function addText() {
  adding.value = true
  try {
    const res = await fetch('/api/knowledge/add-text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: newText.value, source: newSource.value || '手动输入' }),
    }).then(r => r.json())
    toast(`已添加 ${res.chunks_added} 个块`)
    newText.value = ''
    newSource.value = ''
    await loadSources()
  } catch (e) { toast('添加失败', true) }
  adding.value = false
}

// ── 分块管理 ──

async function toggleChunks(source) {
  if (expandedSrc.value === source) { expandedSrc.value = ''; chunks.value = []; return }
  expandedSrc.value = source
  chunksLoading.value = true
  try {
    const res = await fetch(`/api/knowledge/chunks/${encodeURIComponent(source)}`).then(r => r.json())
    chunks.value = res.chunks || []
  } catch (e) { toast('加载块失败', true) }
  chunksLoading.value = false
}

async function toggleChunkView(id) {
  if (viewingChunk.value === id) { viewingChunk.value = ''; chunkDetail.value = null; return }
  viewingChunk.value = id
  try {
    const res = await fetch(`/api/knowledge/chunk/${id}`).then(r => r.json())
    chunkDetail.value = res.chunk
  } catch { viewingChunk.value = '' }
}

async function delChunk(id) {
  await fetch(`/api/knowledge/chunk/${id}`, { method: 'DELETE' })
  toast('已删除')
  await loadSources()
  expandedSrc.value = ''
  chunks.value = []
}

async function delSource(source) {
  if (!confirm(`确认删除 "${source}" 的所有块？`)) return
  await fetch(`/api/knowledge/source/${encodeURIComponent(source)}`, { method: 'DELETE' })
  toast('已删除')
  expandedSrc.value = ''
  chunks.value = []
  await loadSources()
}

// ── 重新分块 ──

function openRechunk(src) {
  rechunkSrc.value = src
  rechunkSize.value = 500
  rechunkOverlap.value = 80
}
async function doRechunk() {
  rechunking.value = true
  try {
    const res = await fetch('/api/knowledge/rechunk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source: rechunkSrc.value.source, chunk_size: rechunkSize.value, overlap: rechunkOverlap.value }),
    }).then(r => r.json())
    toast(`重新分块完成 — ${res.chunks} 个块`)
    rechunkSrc.value = null
    await loadSources()
  } catch (e) { toast('失败', true) }
  rechunking.value = false
}

function formatSize(chars) {
  if (chars > 10000) return (chars / 1000).toFixed(1) + 'k 字'
  return chars + ' 字'
}
function toast(text, error = false) {
  msg.value = text; msgError.value = error
  setTimeout(() => { msg.value = '' }, 3000)
}

onMounted(loadSources)
</script>

<style scoped>
.kb-page { max-width: 860px; margin: 0 auto; padding: 24px; }
.kb-header { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 20px; }
.kb-header h2 { font-size: 20px; }
.doc-count { font-size: 13px; color: #888; }

/* 上传区 */
.upload-zone {
  border: 2px dashed #d9d9d9; border-radius: 12px; padding: 32px;
  text-align: center; cursor: pointer; transition: .2s; background: #fafafa;
  margin-bottom: 16px;
}
.upload-zone.dragging { border-color: #1890ff; background: #e6f7ff; }
.upload-zone:hover { border-color: #aaa; }
.upload-icon { font-size: 32px; margin-bottom: 8px; }
.upload-text { font-size: 14px; color: #555; }
.upload-hint { font-size: 12px; color: #aaa; margin-top: 4px; }

/* 文本粘贴 */
.text-zone {
  background: #fff; border: 1px solid #f0f0f0; border-radius: 10px;
  padding: 14px 16px; margin-bottom: 16px;
}
.text-zone-title { font-size: 13px; font-weight: 500; color: #555; cursor: pointer; }
.text-zone textarea {
  width: 100%; padding: 10px; border: 1px solid #e5e7eb; border-radius: 6px;
  font-size: 13px; font-family: inherit; resize: vertical; margin-top: 10px; outline: none;
}
.text-zone-row { display: flex; gap: 8px; margin-top: 8px; }
.text-zone-row input {
  flex: 1; padding: 7px 10px; border: 1px solid #e5e7eb; border-radius: 6px; font-size: 13px; outline: none;
}
.text-zone-row button {
  padding: 7px 18px; border: none; border-radius: 6px;
  background: #1890ff; color: #fff; font-size: 13px; cursor: pointer;
}
.text-zone-row button:disabled { opacity: .4; cursor: not-allowed; }

/* 来源卡片 */
.source-list { display: flex; flex-direction: column; gap: 10px; }
.loading, .empty { text-align: center; padding: 40px; color: #999; font-size: 14px; }
.source-card {
  background: #fff; border: 1px solid #f0f0f0; border-radius: 10px;
  padding: 14px 16px; box-shadow: 0 1px 4px rgba(0,0,0,.03);
}
.source-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.source-info { display: flex; align-items: baseline; gap: 10px; }
.source-name { font-size: 14px; font-weight: 600; }
.source-meta { font-size: 12px; color: #999; }
.source-actions { display: flex; gap: 4px; }
.source-preview { font-size: 13px; color: #888; line-height: 1.6; overflow: hidden; max-height: 44px; }

.btn-sm {
  padding: 3px 10px; border: 1px solid #d9d9d9; border-radius: 4px;
  background: #fff; font-size: 12px; cursor: pointer; color: #555;
}
.btn-sm:hover { border-color: #1890ff; color: #1890ff; }
.btn-sm.danger:hover { border-color: #ff4d4f; color: #ff4d4f; }

/* 分块面板 */
.chunks-panel {
  margin-top: 10px; border-top: 1px solid #f5f5f5; padding-top: 10px;
}
.loading-sm { text-align: center; padding: 20px; color: #aaa; font-size: 13px; }
.chunk-item {
  padding: 8px 10px; border-radius: 6px; background: #fafafa; margin-bottom: 6px;
}
.chunk-header { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
.chunk-label { font-size: 12px; font-weight: 500; color: #555; }
.chunk-size { font-size: 11px; color: #aaa; }
.btn-xs {
  padding: 1px 8px; border: 1px solid #e8e8e8; border-radius: 3px;
  background: #fff; font-size: 11px; cursor: pointer; color: #888;
}
.btn-xs:hover { border-color: #1890ff; }
.btn-xs.danger:hover { border-color: #ff4d4f; color: #ff4d4f; }
.chunk-preview { font-size: 12px; color: #777; line-height: 1.6; }
.chunk-full {
  margin-top: 6px; padding: 10px; background: #f5f5f5; border-radius: 6px;
  max-height: 300px; overflow-y: auto;
}
.chunk-full pre { font-size: 12px; line-height: 1.7; white-space: pre-wrap; margin: 0; }

/* 弹窗 */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,.3);
  display: flex; align-items: center; justify-content: center; z-index: 100;
}
.modal-box {
  background: #fff; border-radius: 12px; padding: 24px; width: 380px;
  box-shadow: 0 4px 24px rgba(0,0,0,.12);
}
.modal-box h3 { font-size: 16px; margin-bottom: 16px; }
.form-row { display: flex; gap: 12px; margin-bottom: 20px; }
.form-row label { font-size: 13px; color: #555; display: flex; align-items: center; gap: 6px; }
.form-row input {
  width: 80px; padding: 5px 8px; border: 1px solid #d9d9d9; border-radius: 4px; font-size: 13px;
}
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; }
.btn-modal {
  padding: 7px 18px; border: none; border-radius: 6px;
  background: #1890ff; color: #fff; font-size: 13px; cursor: pointer;
}
.btn-modal.cancel { background: #f5f5f5; color: #666; }
.btn-modal:disabled { opacity: .4; }

.toast {
  position: fixed; bottom: 24px; right: 24px; padding: 10px 20px;
  border-radius: 8px; background: #f6ffed; color: #389e0d; font-size: 13px;
  box-shadow: 0 2px 8px rgba(0,0,0,.1); z-index: 200;
}
.toast.error { background: #fff2f0; color: #ff4d4f; }
</style>
