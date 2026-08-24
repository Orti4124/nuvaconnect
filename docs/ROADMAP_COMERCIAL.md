# NuvaConnect — Roadmap comercial (MVP → Producto)

Este prototipo cubre el **núcleo** de un producto tipo AnyDesk/TeamViewer. Para llevarlo a mercado, esta es la ruta propuesta por fases.

## Estado actual (MVP — ✅ implementado y probado)

- [x] Servidor relay de emparejamiento por ID (funciona detrás de NAT)
- [x] Control remoto de pantalla (streaming diferencial por tiles)
- [x] Control de teclado y mouse
- [x] Transferencia de archivos con verificación de integridad
- [x] Cifrado extremo a extremo (PBKDF2 + AES autenticado)
- [x] Autenticación por contraseña (reto/respuesta)
- [x] GUI de escritorio para el controlador (PyQt6)

## Fase 1 — Robustez y experiencia (4–6 semanas)

- [ ] **Códec de video real** (VP8/VP9/H.264 vía `pyav`/WebRTC) en lugar de JPEG por tiles → menor ancho de banda, mayor FPS.
- [ ] **Multi-monitor** con selector de pantalla.
- [ ] **Portapapeles compartido** (texto e imágenes).
- [ ] **Reconexión automática** ante caídas de red.
- [ ] **Adaptación dinámica** de calidad/FPS según ancho de banda medido.
- [ ] **GUI unificada** (una sola app con pestañas "Compartir mi pantalla" / "Conectar").
- [ ] Indicador visible de sesión activa en el host (barra de "estás siendo controlado").

## Fase 2 — Seguridad de nivel producto (4–6 semanas)

- [ ] **Handshake Noise/libsodium** con claves efímeras → *forward secrecy*.
- [ ] **Verificación de identidad del relay** (pinning de certificado).
- [ ] **Registro de auditoría** (quién se conectó, cuándo, qué archivos se transfirieron).
- [ ] **Confirmación explícita** del host antes de ceder control + botón de corte inmediato.
- [ ] **2FA** para cuentas y **lista de permitidos** por dispositivo.
- [ ] Pentest externo y revisión de cumplimiento (habeas data / GDPR).

## Fase 3 — Funciones empresariales (6–10 semanas)

- [ ] **Acceso desatendido** (host como servicio de Windows / demonio macOS con credenciales persistentes).
- [ ] **Libreta de direcciones** y grupos de dispositivos.
- [ ] **Panel de administración web** (usuarios, dispositivos, sesiones, reportes).
- [ ] **Chat en sesión** y **audio/voz** (VoIP).
- [ ] **Grabación de sesión** para soporte y capacitación.
- [ ] **Wake-on-LAN** y reinicio remoto con reconexión.

## Fase 4 — Comercialización

- [ ] **Licenciamiento** (por técnico/por dispositivo/por sesiones concurrentes) y activación online.
- [ ] **Modelo de precios** y facturación (freemium + planes).
- [ ] **Instaladores firmados** (certificado de firma de código Windows + notarización Apple) → evita alertas de seguridad.
- [ ] **Clientes móviles** (Android/iOS) y **cliente web** (WebRTC en el navegador).
- [ ] **Infraestructura de relays** geo-distribuida con balanceo y selección del más cercano.
- [ ] Marca, sitio web, documentación y soporte.

## Arquitectura de escalado (referencia)

```
                       ┌──────────────┐
   Clientes ───────────▶  Load Balancer │
                       └──────┬─────────┘
             ┌────────────────┼────────────────┐
        ┌────▼────┐      ┌────▼────┐       ┌────▼────┐
        │ Relay 1 │      │ Relay 2 │  ...  │ Relay N │   (stateless, escala horizontal)
        └────┬────┘      └────┬────┘       └────┬────┘
             └────────── Redis / pub-sub para salas compartidas ──────────┘
                                   │
                            ┌──────▼──────┐
                            │  API + DB   │  (cuentas, dispositivos, licencias, auditoría)
                            └─────────────┘
```

## Recomendación de stack para producción

- **Rendimiento crítico:** migrar host/viewer a **Rust** o **C++** (como hace RustDesk) para captura/codec de bajo nivel; mantener el relay en Go/Rust por concurrencia.
- **Alternativa pragmática:** mantener Python + WebRTC (`aiortc`) para acelerar time-to-market, y optimizar por partes.
- **WebRTC** habilitaría además conexiones **P2P directas** (con el relay solo como *signaling* + TURN de respaldo), reduciendo costos de servidor.
