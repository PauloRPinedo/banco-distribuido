"""ServicioAutenticacion — RF-26, CU-17.

No depende de ServicioReplicacion/Nodo: iniciar sesión no escribe una
Operación ni necesita mayoría (ver la nota en
docs/entregables/06-diseno-detallado/diagrama-de-clases-servicio.md).
"""

import uuid
from datetime import datetime, timezone

from banco.autenticacion import calcular_hash, emitir_token, validar_token, verificar_contrasena


class CredencialesInvalidas(Exception):
    pass


class ServicioAutenticacion:

    def __init__(self, repo_usuarios):
        self._usuarios = repo_usuarios

    def registrar_usuario(self, nombre: str, email: str, contrasena: str) -> dict:
        usuario = {
            "id": str(uuid.uuid4()),
            "nombre": nombre,
            "email": email,
            "password_hash": calcular_hash(contrasena),
            "fecha_creacion": datetime.now(timezone.utc),
        }
        self._usuarios.guardar(usuario)
        return {"id": usuario["id"], "email": email}

    def iniciar_sesion(self, email: str, contrasena: str) -> str:
        usuario = self._usuarios.buscar_por_email(email)
        # mismo mensaje de error tanto si el email no existe como si la
        # contraseña no coincide (E1/E2 de CU-17) — no revela qué emails
        # están registrados
        if usuario is None or not verificar_contrasena(contrasena, usuario["password_hash"]):
            raise CredencialesInvalidas("email o contraseña incorrectos")
        return emitir_token(usuario["id"])

    def validar_sesion(self, token: str) -> str:
        usuario_id = validar_token(token)
        if usuario_id is None:
            raise CredencialesInvalidas("token inválido o expirado")
        return usuario_id
