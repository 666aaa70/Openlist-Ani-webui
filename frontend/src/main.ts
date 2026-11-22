import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { configureApiClient } from './api/client'
import { useAuthStore } from './stores/auth'
import { useDownloadsStore } from './stores/downloads'
import './style.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

const authStore = useAuthStore(pinia)
const downloadsStore = useDownloadsStore(pinia)

configureApiClient({
  getCsrfToken: () => authStore.csrfToken,
  onUnauthorized: () => {
    downloadsStore.reset()
    authStore.clearSession()
    if (router.currentRoute.value.name !== 'login') {
      void router.replace({
        name: 'login',
        query: { redirect: router.currentRoute.value.fullPath },
      })
    }
  },
})

app.mount('#app')
