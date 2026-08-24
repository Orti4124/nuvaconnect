# NuvaConnect — Ciberseguridad

NuvaConnect implementa **defensa en profundidad**: varias capas independientes de seguridad, de modo que comprometer una no basta para tomar el control.

## Capas de seguridad

| # | Control | Qué protege | Estado |
|---|---------|-------------|--------|
| 1 | **Cifrado extremo a extremo** | Confidencialidad del tráfico. El relay solo ve JPEG cifrados; nadie en la red puede leer pantalla, teclas ni archivos. | ✅ probado |
| 2 | **Contraseña de sesión (1er factor)** | Sin la contraseña no se puede ni iniciar el diálogo: la clave de cifrado se deriva de ella (PBKDF2, 200k iteraciones). | ✅ probado |
| 3 | **Identidad de dispositivo (Ed25519)** | El host verifica *qué máquina* se conecta mediante una firma criptográfica, no solo que conoce la contraseña. Impide suplantación. | ✅ probado |
| 4 | **2FA (TOTP)** | Segundo factor de tiempo, compatible con Google Authenticator / Authy / Microsoft Authenticator (RFC 6238). | ✅ probado |
| 5 | **Allowlist de dispositivos** | Solo dispositivos previamente autorizados (por fingerprint) pueden controlar el host. | ✅ probado |
| 6 | **Aprobación humana** | El usuario del host acepta/rechaza cada sesión entrante (como el diálogo de TeamViewer). | ✅ implementado |
| 7 | **Anti fuerza bruta** | Bloqueo temporal tras N intentos fallidos, con ventana y lockout configurables. | ✅ probado |
| 8 | **Bitácora de auditoría** | Registro append-only (JSONL) de conexiones, autenticaciones, transferencias y rechazos. | ✅ probado |

## Flujo de autenticación reforzado

```
 VIEWER                              RELAY                         HOST
   │  register(id) ───────────────────▶│◀─────────────── register(id)
   │◀──────────── peer_joined ─────────┼──── peer_joined ──────────▶│
   │                                   │        (¿bloqueado por fuerza bruta? → auth_locked)
   │◀───────── auth_challenge(nonce, need_2fa) ─────────────────────│
   │  [descifra el reto ⇒ contraseña correcta]                      │
   │  firma el nonce con su clave Ed25519                           │
   │── auth_response(nonce, device_pub, signature) ────────────────▶│
   │                                   │   verifica: nonce + firma + fingerprint
   │                                   │   (allowlist? 2FA? aprobación humana?)
   │◀──────────── auth_2fa (si aplica) ─────────────────────────────│
   │── auth_2fa_code(code) ────────────────────────────────────────▶│  verifica TOTP
   │◀──────────────── auth_ok ──────────────────────────────────────│  registra en auditoría
   │◀════════════ pantalla cifrada ═════════════════════════════════│
```

Cualquier fallo (nonce, firma, 2FA, allowlist o rechazo humano) cuenta como intento fallido y alimenta el anti-fuerza-bruta.

## Configuración (variables de entorno)

| Variable | Default | Efecto |
|----------|---------|--------|
| `NUVA_REQUIRE_APPROVAL` | `1` | El host aprueba manualmente cada sesión |
| `NUVA_REQUIRE_2FA` | `0` | Exige código TOTP además de la contraseña |
| `NUVA_ENFORCE_ALLOWLIST` | `0` | Solo dispositivos en la allowlist |
| `NUVA_MAX_AUTH_ATTEMPTS` | `5` | Intentos antes del bloqueo |
| `NUVA_LOCKOUT_SECONDS` | `300` | Duración del bloqueo |

Ejemplo — host de máxima seguridad:
```bash
NUVA_REQUIRE_2FA=1 NUVA_ENFORCE_ALLOWLIST=1 python run_host.py
```

## Administración

```bash
python -m nuvaconnect.admin whoami          # fingerprint de este equipo
python -m nuvaconnect.admin list            # dispositivos de confianza
python -m nuvaconnect.admin trust <fp> "PC de soporte"
python -m nuvaconnect.admin revoke <fp>
python -m nuvaconnect.admin audit 100       # últimos 100 eventos de auditoría
```

El estado persistente vive en `~/.nuvaconnect/`:
- `device_key.bin` — clave privada del dispositivo (permisos `600`).
- `totp_secret.txt` — secreto 2FA del host (permisos `600`).
- `allowlist.json` — dispositivos de confianza.
- `audit.log` — bitácora de auditoría.

## Modelo de amenazas (resumen)

| Amenaza | Mitigación |
|---------|-----------|
| Espionaje de red / MITM en el relay | Cifrado E2E: el relay nunca tiene la clave |
| Robo de la contraseña de sesión | 2FA + allowlist de dispositivos + aprobación humana |
| Suplantación de dispositivo | Firma Ed25519 del reto; el atacante no tiene la clave privada |
| Adivinación de contraseña/código | Anti fuerza bruta con bloqueo temporal |
| Acceso no autorizado | Aprobación manual del host por cada sesión |
| Repudio / falta de trazabilidad | Bitácora de auditoría append-only |

## Pendiente para producción (ver ROADMAP_COMERCIAL.md, Fase 2)

- Handshake con **claves efímeras** (Noise/libsodium) → *forward secrecy*.
- **Pinning** del certificado del relay.
- Cifrado del `device_key.bin` en reposo (keychain del SO / DPAPI).
- Pentest externo y revisión de cumplimiento (habeas data / GDPR).
