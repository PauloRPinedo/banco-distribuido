import { cloneElement, useId } from "react";

// Rótulo e controlo. Sem filhos, é um <input> com as props que vierem; com um
// <select> como filho, o rótulo liga-se a ele pelo mesmo id.
export default function Campo({ rotulo, ajuda, children, ...props }) {
  const id = useId();
  return (
    <div className="campo">
      <label htmlFor={id}>{rotulo}</label>
      {children ? cloneElement(children, { id }) : <input id={id} {...props} />}
      {ajuda && <p className="ajuda">{ajuda}</p>}
    </div>
  );
}
