import { createApp } from 'vue'
// шрифт – локально, без запросов к Google Fonts; в нём есть все казахские буквы (ә ғ қ ң ө ұ ү һ і)
import '@fontsource-variable/onest'
import App from './App.vue'
import { i18n, initialLocale } from './i18n'
import router from './router'
import './style.css'

document.documentElement.lang = initialLocale

createApp(App).use(router).use(i18n).mount('#app')
