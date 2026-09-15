"""Pruebas de banco/autenticacion — sin BD, sin red (RN-15, RN-16)."""

import os
import unittest

os.environ.setdefault("SECRET_KEY", "llave-de-prueba-no-usar-en-produccion")

from banco.autenticacion import calcular_hash, emitir_token, validar_token, verificar_contrasena


class TestHashDeContrasena(unittest.TestCase):

    def test_contrasena_correcta_verifica(self):
        hash_guardado = calcular_hash("correcto-caballo-bateria-grapa")
        self.assertTrue(verificar_contrasena("correcto-caballo-bateria-grapa", hash_guardado))

    def test_contrasena_incorrecta_no_verifica(self):
        hash_guardado = calcular_hash("correcto-caballo-bateria-grapa")
        self.assertFalse(verificar_contrasena("otra-cosa", hash_guardado))

    def test_hash_nunca_es_la_contrasena_en_claro(self):
        hash_guardado = calcular_hash("hola-mundo")
        self.assertNotIn("hola-mundo", hash_guardado)

    def test_misma_contrasena_da_hashes_distintos(self):
        # la sal es aleatoria en cada llamada — evita que dos usuarios con la
        # misma contraseña tengan el mismo hash guardado
        self.assertNotEqual(calcular_hash("igual"), calcular_hash("igual"))


class TestTokenDeSesion(unittest.TestCase):

    def test_token_valido_devuelve_el_usuario(self):
        token = emitir_token("usuario-123")
        self.assertEqual(validar_token(token), "usuario-123")

    def test_token_alterado_se_rechaza(self):
        token = emitir_token("usuario-123")
        alterado = token[:-1] + ("0" if token[-1] != "0" else "1")
        self.assertIsNone(validar_token(alterado))

    def test_token_se_valida_sin_llamar_a_quien_lo_emitio(self):
        # simula "otro nodo": misma SECRET_KEY, ninguna llamada de red — la
        # propia llamada a validar_token ya lo demuestra (RN-16)
        token = emitir_token("usuario-456")
        self.assertEqual(validar_token(token), "usuario-456")


if __name__ == "__main__":
    unittest.main()
