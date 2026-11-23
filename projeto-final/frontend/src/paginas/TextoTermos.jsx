// O texto dos termos, partilhado pelo ecrã /termos e pela cortina do registo.
export default function TextoTermos({ aoFechar }) {
  return (
    <article className="cartao termos">
      <h2>Termos e condições</h2>
      <p>
        Este banco é um trabalho de Computação Distribuída. Não é uma instituição
        financeira e não guarda dinheiro real.
      </p>
      <p>
        No registo guardam-se o teu nome, o teu email e um hash da senha (PBKDF2
        com sal), copiados para os três nós. A sessão dura 8 horas. Não há
        recuperação de senha: sem um servidor de email, não há como confirmar
        que quem a pede é o dono do email.
      </p>
      <p>
        Consultar, sacar, ver o extrato, abrir conta e transferir exigem sessão,
        e só o dono de uma conta a movimenta. Depositar numa conta e receber
        transferências fica aberto a todos, como num balcão.
      </p>
      {aoFechar && (
        <button className="botao-secundario" type="button" onClick={aoFechar}>Fechar</button>
      )}
    </article>
  );
}
