import { createApp } from 'vue'
import ArcoVue from '@arco-design/web-vue'
import zhCN from '@arco-design/web-vue/es/locale/lang/zh-cn'
import '@arco-design/web-vue/dist/arco.css'

import App from '@/App.vue'
import { router } from '@/router'
import '@/style.css'

const app = createApp(App)

app.use(router)
app.use(ArcoVue, {
  locale: zhCN,
})

app.mount('#app')
