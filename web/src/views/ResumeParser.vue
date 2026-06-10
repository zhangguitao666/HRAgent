<template>
  <div>
    <h1>📄 简历智能解析</h1>
    <div class="grid">
      <div>
        <label>简历内容</label>
        <textarea v-model="resumeText" placeholder="请在此粘贴简历全文..." rows="12"></textarea>
        <label>岗位要求（可选）</label>
        <textarea v-model="jdText" placeholder="粘贴招聘 JD..." rows="6"></textarea>
        <button @click="parse" :disabled="loading || !resumeText.trim()">🔍 解析简历</button>
      </div>
      <div v-if="result">
        <div v-if="loading" class="loading">AI 正在解析...</div>
        <div v-else class="result-card">
          <h3>候选人信息</h3>
          <ul>
            <li><b>姓名：</b>{{ result.info.name }}</li>
            <li><b>工作年限：</b>{{ result.info.years_of_experience }}年</li>
            <li><b>学历：</b>{{ result.info.education }}</li>
            <li><b>技能：</b>{{ result.info.skills?.join('、') || '无' }}</li>
            <li><b>当前职位：</b>{{ result.info.current_position }}</li>
            <li><b>期望薪资：</b>{{ result.info.expected_salary }}</li>
          </ul>
          <p class="summary">{{ result.info.summary }}</p>
          <div v-if="result.evaluation" class="eval">
            <h3>岗位匹配评估</h3>
            <p>{{ result.evaluation }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import api from '../api/client.js'

const resumeText = ref('')
const jdText = ref('')
const loading = ref(false)
const result = ref(null)

async function parse() {
  loading.value = true
  try {
    const res = await api.resumeParse(resumeText.value, jdText.value)
    result.value = res
  } catch {
    alert('解析失败')
  }
  loading.value = false
}
</script>

<style scoped>
h1 { font-size: 22px; margin-bottom: 20px; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
label { display: block; font-size: 13px; color: #666; margin-bottom: 6px; margin-top: 12px; }
textarea { width: 100%; padding: 10px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 13px; resize: vertical; }
button { margin-top: 12px; padding: 10px 24px; background: #1890ff; color: #fff; border: none; border-radius: 6px; cursor: pointer; width: 100%; }
.result-card { background: #fff; padding: 20px; border-radius: 8px; }
.result-card h3 { font-size: 15px; margin-bottom: 10px; }
.result-card ul { list-style: none; padding: 0; }
.result-card li { padding: 4px 0; font-size: 14px; }
.summary { margin-top: 12px; padding: 10px; background: #f6ffed; border-radius: 6px; font-size: 13px; }
.eval { margin-top: 16px; padding-top: 16px; border-top: 1px solid #f0f0f0; }
.eval p { font-size: 14px; line-height: 1.8; white-space: pre-wrap; }
.loading { padding: 40px; text-align: center; color: #999; }
</style>
