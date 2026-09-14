import { createApp } from 'vue'
import App from './App.vue'
import { i18n } from './i18n'
import router from './router'
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'

const app = createApp(App)
app.use(i18n)
app.use(router)

app.config.errorHandler = (err, _instance, info) => {
  console.error('Vue Error:', err, info)
}

app.mount('#app')
