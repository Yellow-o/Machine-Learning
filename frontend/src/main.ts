import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

import App from './App.vue'
import router from './router'
import { pinia } from './stores/pinia'
import './styles/base.css'

const savedTheme = localStorage.getItem('dms_theme')
if (savedTheme === 'light' || savedTheme === 'dark') {
  document.documentElement.dataset.theme = savedTheme
}

createApp(App).use(pinia).use(router).use(ElementPlus).mount('#app')
