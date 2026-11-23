const CLASSES = { principal: "botao-principal", secundario: "botao-secundario", perigo: "botao-perigo" };

export default function Botao({ children, variante = "principal", tipo = "submit", ...resto }) {
  return (
    <button className={CLASSES[variante]} type={tipo} {...resto}>
      {children}
    </button>
  );
}
