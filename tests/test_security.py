"""Pruebas de las funciones de ciberseguridad de NuvaConnect."""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nuvaconnect.security import (
    TOTP, DeviceIdentity, Allowlist, AuditLog, BruteForceGuard,
)

RESULTS = []


def check(name, ok):
    RESULTS.append(ok)
    print(("  PASS " if ok else "  FAIL ") + name)


def test_totp():
    secret = TOTP.new_secret()
    t = TOTP(secret)
    at = 1_700_000_000  # instante fijo
    code = t.now(at=at)
    check("TOTP: código válido se acepta", t.verify(code, at=at))
    check("TOTP: código incorrecto se rechaza", not t.verify("000000", at=at))
    # Tolerancia de ±1 periodo (desfase de reloj)
    check("TOTP: acepta desfase de 1 periodo",
          t.verify(t.now(at=at - 30), at=at, window=1))
    # Fuera de ventana se rechaza
    check("TOTP: rechaza código muy viejo",
          not t.verify(t.now(at=at - 300), at=at, window=1))
    # Compatibilidad: código de 6 dígitos
    check("TOTP: longitud de 6 dígitos", len(code) == 6 and code.isdigit())
    # provisioning URI válido
    check("TOTP: genera URI otpauth", t.provisioning_uri("user").startswith("otpauth://totp/"))


def test_device_identity():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "key.bin")
        dev = DeviceIdentity.load_or_create(p)
        # Persistencia: recargar da la misma huella
        dev2 = DeviceIdentity.load_or_create(p)
        check("Device: clave persiste (misma huella)",
              dev.fingerprint() == dev2.fingerprint())
        # Firma/verificación
        nonce = os.urandom(16)
        sig = dev.sign(nonce)
        check("Device: firma válida se verifica",
              DeviceIdentity.verify(dev.public_bytes(), sig, nonce))
        # Nonce alterado -> falla (previene replay/spoof)
        check("Device: nonce alterado se rechaza",
              not DeviceIdentity.verify(dev.public_bytes(), sig, os.urandom(16)))
        # Firma de otra clave -> falla (previene suplantación)
        other = DeviceIdentity.load_or_create(os.path.join(d, "other.bin"))
        check("Device: firma de otro dispositivo se rechaza",
              not DeviceIdentity.verify(dev.public_bytes(), other.sign(nonce), nonce))
        # Permisos del archivo de clave (solo dueño)
        mode = oct(os.stat(p).st_mode)[-3:]
        check("Device: archivo de clave con permisos 600", mode == "600")


def test_allowlist():
    with tempfile.TemporaryDirectory() as d:
        al = Allowlist(os.path.join(d, "al.json"))
        fp = "abc123"
        check("Allowlist: desconocido no es de confianza", not al.is_trusted(fp))
        al.add(fp, "PC soporte")
        check("Allowlist: agregado es de confianza", al.is_trusted(fp))
        # Persistencia
        al2 = Allowlist(os.path.join(d, "al.json"))
        check("Allowlist: persiste en disco", al2.is_trusted(fp))
        al2.remove(fp)
        check("Allowlist: removido deja de ser de confianza", not al2.is_trusted(fp))


def test_bruteforce():
    g = BruteForceGuard(max_attempts=3, window=100, lockout=100)
    now = 1000.0
    locked1 = g.record_failure(now)
    locked2 = g.record_failure(now + 1)
    check("BruteForce: no bloquea antes del límite", not locked1 and not locked2)
    locked3 = g.record_failure(now + 2)
    check("BruteForce: bloquea al alcanzar el límite", locked3)
    check("BruteForce: queda bloqueado", g.is_locked(now + 3))
    check("BruteForce: se desbloquea tras el tiempo", not g.is_locked(now + 200))
    # Éxito limpia el contador
    g2 = BruteForceGuard(max_attempts=3, window=100, lockout=100)
    g2.record_failure(now)
    g2.record_success()
    check("BruteForce: éxito resetea intentos", not g2.is_locked(now))


def test_audit():
    with tempfile.TemporaryDirectory() as d:
        log = AuditLog(os.path.join(d, "audit.log"))
        log.record("session_start", fingerprint="xyz")
        log.record("file_incoming", name="reporte.pdf", size=1234)
        entries = log.tail(10)
        check("Audit: registra eventos", len(entries) == 2)
        check("Audit: conserva campos",
              entries[0]["event"] == "session_start" and
              entries[1]["name"] == "reporte.pdf")
        check("Audit: incluye timestamp", "ts" in entries[0])


def simulate_hardened_handshake():
    """Simula la verificación que hace el host sobre la respuesta del viewer:
    nonce firmado por la clave del dispositivo. Es el corazón de la
    autenticación de dispositivo."""
    import os as _os
    nonce = _os.urandom(16)
    with tempfile.TemporaryDirectory() as d:
        viewer_dev = DeviceIdentity.load_or_create(os.path.join(d, "v.bin"))
        # El viewer firma el nonce del reto
        signature = viewer_dev.sign(nonce)
        device_pub = viewer_dev.public_bytes()
        # El host verifica exactamente como en host._handle_auth_response
        ok = DeviceIdentity.verify(device_pub, signature, nonce)
        fp = DeviceIdentity.fingerprint_of(device_pub)
        check("Handshake reforzado: host valida firma de dispositivo", ok)
        check("Handshake reforzado: fingerprint coincide",
              fp == viewer_dev.fingerprint())
        # Atacante sin la clave privada no puede forjar la firma
        attacker = DeviceIdentity.load_or_create(os.path.join(d, "a.bin"))
        forged = attacker.sign(nonce)
        check("Handshake reforzado: firma forjada con el pub de la víctima falla",
              not DeviceIdentity.verify(device_pub, forged, nonce))


if __name__ == "__main__":
    test_totp()
    test_device_identity()
    test_allowlist()
    test_bruteforce()
    test_audit()
    simulate_hardened_handshake()
    ok = all(RESULTS)
    print("\nRESULTADO:", "TODO OK ✔" if ok else "HAY FALLOS")
    sys.exit(0 if ok else 1)
