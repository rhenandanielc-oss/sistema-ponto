// Service worker mínimo: só existe para o Chrome oferecer "Instalar app" (tela cheia, sem barra de endereço).
// Não guarda nada em cache: o sistema sempre usa a versão do servidor.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {});
