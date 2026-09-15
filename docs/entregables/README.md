# Entregables — documento técnico

Empieza por [`documento-de-especificacion.md`](documento-de-especificacion.md):
es el índice completo, con enlace a cada pieza. Esta carpeta existe separada
en muchos archivos pequeños en vez de un solo documento largo, a propósito —
cada sección se puede revisar, versionar y corregir sin tocar las demás.

## Estructura

```
entregables/
├── documento-de-especificacion.md   ← empezar aquí
├── 01-requisitos/
├── 02-casos-de-uso/
├── 03-arquitectura/
├── 04-modulos/
├── 05-modelo-de-datos/
├── 06-diseno-detallado/
├── 07-tecnologia/
└── 08-pruebas-y-despliegue/
```

Las decisiones de arquitectura (por qué se eligió cada cosa, no solo qué se
eligió) están en `docs/adr/`, no aquí — este documento las referencia, no las
repite.
