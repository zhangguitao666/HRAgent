import { createRouter, createWebHashHistory } from 'vue-router'
import ChatView from './views/ChatView.vue'

const routes = [
  { path: '/', component: ChatView },
]

export default createRouter({ history: createWebHashHistory(), routes })
