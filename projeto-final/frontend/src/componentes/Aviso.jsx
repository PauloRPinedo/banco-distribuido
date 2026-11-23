// Uma nota neutra, ou um erro (com role="alert", para o leitor de ecrã o dizer).
export default function Aviso({ children, erro = false, sucesso = false }) {
  if (!children) return null;
  const classe = erro ? "aviso aviso-erro" : sucesso ? "aviso aviso-sucesso" : "aviso";
  return (
    <div className={classe} role={erro ? "alert" : "status"}>
      <span className="ponto" aria-hidden="true">●</span>
      <span>{children}</span>
    </div>
  );
}
