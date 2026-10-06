"""Registo e início de sessão — RF-26, CU-17.

O registo passa pelo log, como qualquer escrita (ver
`ServicoDeEscrita.registar_usuario`): o utilizador tem de existir nos três nós
para conseguir entrar depois de um failover. O início de sessão não escreve
nada — lê o utilizador e assina um token que qualquer nó valida sem rede.
"""

from banco.autenticacao import emitir_token, verificar_senha
from banco.dominio.erros import ValorInvalido
from banco.servico.erros import CredenciaisInvalidas


class ServicoAutenticacao:

    def __init__(self, repo_usuarios, escrita=None) -> None:
        self._usuarios = repo_usuarios
        self._escrita = escrita

    def registar_usuario(self, nome: str, email: str, senha: str) -> dict:
        if not nome.strip() or "@" not in email or len(senha) < 6:
            raise ValorInvalido(
                "registo inválido: nome não vazio, email com @ e senha com 6+ caracteres")
        return self._escrita.registar_usuario(nome.strip(), email.strip().lower(), senha)

    def iniciar_sessao(self, email: str, senha: str) -> str:
        usuario = self._usuarios.procurar_por_email(email.strip().lower())
        # A mesma mensagem quer o email não exista quer a senha não coincida
        # (E1/E2 de CU-17): não revela que emails estão registados.
        if usuario is None or not verificar_senha(senha, usuario["hash_senha"]):
            raise CredenciaisInvalidas("email ou senha incorretos")
        return emitir_token(usuario["id"])
