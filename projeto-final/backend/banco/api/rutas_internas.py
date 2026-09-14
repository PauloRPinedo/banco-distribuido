"""ClusterInternoController — ver docs/SPECS.md §6.2.

Hoy solo expone `/interno/estado` (lo único que el `Nodo` *stub* sabe
responder). `/interno/replicar`, `/interno/votar` y `/interno/log` se
agregan cuando el protocolo real exista (ROADMAP.md, subfases 2.x).
"""

from fastapi import APIRouter

from banco.api.dependencias import NODO

router = APIRouter(prefix="/interno", tags=["interno"])


@router.get("/estado")
def estado_del_nodo():
    return NODO.estado()
