# NuvaConnect — Compilación automática con GitHub Actions

Con esto **no necesitas máquinas Windows ni Mac**: GitHub compila el `.exe` y el `.dmg` en la nube, publica la imagen Docker del servidor y crea un Release descargable.

## Qué hace cada workflow

| Archivo | Cuándo corre | Qué produce |
|---------|--------------|-------------|
| `.github/workflows/tests.yml` | En cada push / PR | Corre las pruebas del núcleo (red, cifrado, seguridad, archivos) |
| `.github/workflows/build-installers.yml` | Manual o al crear un tag `vX.Y.Z` | `NuvaConnect-Setup.exe`, `NuvaConnect.dmg`, imagen Docker en GHCR y un Release |

## Conexión paso a paso

### 1. Sube el proyecto a GitHub

Desde la raíz del proyecto:

```bash
git init
git add .
git commit -m "NuvaConnect: primer commit"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/nuvaconnect.git
git push -u origin main
```

> Al hacer push, el workflow **Tests** corre solo. Míralo en la pestaña **Actions** del repo.

### 2. Genera los instaladores (2 opciones)

**Opción A — Manual (cuando quieras):**
Ve a **Actions → Build Installers → Run workflow**. En unos minutos tendrás los instaladores como *artifacts* descargables al final del run.

**Opción B — Por versión (recomendada):** crea un tag y GitHub compila y publica un **Release**:

```bash
git tag v0.1.0
git push origin v0.1.0
```

Al terminar, en **Releases** del repo aparecerán `NuvaConnect-Setup.exe` y `NuvaConnect.dmg` listos para descargar y distribuir.

### 3. Imagen Docker del servidor (automática)

El mismo run publica la imagen en GitHub Container Registry. Para desplegar el relay en cualquier servidor:

```bash
docker run -d -p 9765:9765 --restart unless-stopped \
  ghcr.io/TU_USUARIO/nuvaconnect/relay:latest
```

> La primera vez, en **Settings → Packages** del repo, marca la imagen como pública si quieres descargarla sin login.

## Firma de código en CI (para producción)

Los instaladores salen **sin firmar** (GitHub no tiene tus certificados). Para firmarlos automáticamente y evitar alertas de SmartScreen/Gatekeeper, agrega tus secretos en **Settings → Secrets and variables → Actions** y amplía el workflow:

- **Windows:** guarda el certificado `.pfx` (base64) y su contraseña como secretos; añade un paso con `signtool sign` sobre el `.exe`.
- **macOS:** guarda el `Developer ID`, el `.p12` y las credenciales de `notarytool`; el script `build_dmg.sh` ya usa `SIGN_IDENTITY` y `NOTARY_PROFILE` si los defines como variables de entorno del job.

Puedo dejarte esos pasos de firma listos cuando tengas los certificados.

## Requisitos previos en el repo

- Actions habilitado (por defecto lo está).
- Permisos del workflow: **Settings → Actions → General → Workflow permissions → Read and write** (necesario para crear Releases y publicar en GHCR). El workflow ya declara `permissions: contents: write, packages: write`.
