"""Pruebas de banco/api/seguridad.py — sin BD, sin red."""

import os
import unittest

os.environ.setdefault("SECRET_KEY", "llave-de-prueba-no-usar-en-produccion")

from fastapi import HTTPException

from banco.autenticacion import emitir_token
from banco.api.seguridad import exigir_dueno, usuario_autenticado


class TestUsuarioAutenticado(unittest.TestCase):

    def test_sin_encabezado_rechaza_401(self):
        with self.assertRaises(HTTPException) as ctx:
            usuario_autenticado(authorization=None)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_encabezado_sin_bearer_rechaza_401(self):
        with self.assertRaises(HTTPException) as ctx:
            usuario_autenticado(authorization="Token abc123")
        self.assertEqual(ctx.exception.status_code, 401)

    def test_token_valido_devuelve_usuario_id(self):
        token = emitir_token("usuario-1")
        self.assertEqual(usuario_autenticado(authorization=f"Bearer {token}"), "usuario-1")

    def test_token_invalido_rechaza_401(self):
        with self.assertRaises(HTTPException) as ctx:
            usuario_autenticado(authorization="Bearer token-falso")
        self.assertEqual(ctx.exception.status_code, 401)


class TestExigirDueno(unittest.TestCase):

    def test_dueno_correcto_no_lanza_nada(self):
        exigir_dueno({"usuario_id": "usuario-1"}, "usuario-1")  # no debe lanzar

    def test_dueno_incorrecto_rechaza_403(self):
        with self.assertRaises(HTTPException) as ctx:
            exigir_dueno({"usuario_id": "usuario-1"}, "usuario-2")
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
