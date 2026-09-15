# Pendiente en `dominio/`

Estos 4 archivos son una copia literal de `prototipo-1/banco/dominio/` — ya
son puros (sin red ni disco) y cubren RF-01 a RF-08. Lo que falta para cerrar
el alcance de `docs/entregables/` (no incluido en este *scaffolding*):

- [ ] `moneda` en `Conta`/`Cuenta` y validación del par de monedas en
      `transferencia` (RF-19, RF-20 — ver `docs/entregables/05-modelo-de-datos/modelo-logico.md`)
- [ ] `tipo_producto`, `tasa_interes`, `fecha_ultimo_interes`,
      `fecha_vencimiento` en `Cuenta`; bloqueo de `RETIRO`/`TRANSFERENCIA` en
      `PLAZO_FIJO` antes de vencer (RN-12)
- [ ] Operación `CAMBIO` con `tasa_aplicada` fija (RN-06) y `INTERES` (RN-13)
- [ ] Operación `TRANSFERENCIA_EXTERNA` con `sistema_externo_id` y reverso
      (RN-14)
- [ ] Contraseña en `Usuario` — vive en `autenticacion/`, no aquí (RN-15)

Se deja como TODO explícito, mismo estilo que `docs/ROADMAP.md`, en vez de
implementarlo a medias.
