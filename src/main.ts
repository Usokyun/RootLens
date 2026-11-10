import { createApp } from 'vue'
import { ConfigProvider, Drawer, Modal } from '@arco-design/web-vue'
import '@arco-design/web-vue/dist/arco.css'
import App from '@/App.vue'
import { router } from '@/router'
import '@/style.css'

createApp(App).use(router).use(ConfigProvider).use(Modal).use(Drawer).mount('#app')
