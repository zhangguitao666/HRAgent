import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

async function chatAskStream(sessionId, question, onThinking, onToken, onDone) {
  const response = await fetch('http://localhost:8000/api/chat/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, session_id: sessionId }),
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
          if (data.type === 'progress' && onThinking) {
            await onThinking(data.thinking || [])
          } else if (data.type === 'token' && onToken) {
            await onToken(data.content || '')
          } else if (data.type === 'done') {
            onDone({ thinking: data.thinking || [] })
          } else if (data.type === 'error') {
            onDone({ thinking: [], error: data.content })
          }
        } catch { /* skip */ }
      }
    }
  }
}

export default {
  faqChat(message) {
    return api.post('/faq/chat', { message }).then(r => r.data)
  },
  resumeParse(resume_text, job_requirements = '') {
    return api.post('/resume/parse', { resume_text, job_requirements }).then(r => r.data)
  },
  lifecycleChat(flow_type, message) {
    return api.post('/lifecycle/chat', { flow_type, message }).then(r => r.data)
  },
  queryAsk(question) {
    return api.post('/query/ask', { question }).then(r => r.data)
  },
  queryAskStream: chatAskStream,
  chatAskStream,
}
