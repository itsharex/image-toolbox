import { createApp } from "vue";
import App from "./App.vue";
import "./style.css"; 

// Disable context menu
document.addEventListener('contextmenu', event => event.preventDefault());

createApp(App).mount("#app");
