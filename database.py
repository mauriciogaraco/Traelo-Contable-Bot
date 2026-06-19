import logging
import time
from datetime import date, datetime
from typing import Optional

from supabase import create_client, Client

logger = logging.getLogger(__name__)

_supabase: Optional[Client] = None


def init_db(url: str, key: str) -> None:
    global _supabase
    _supabase = create_client(url, key)
    logger.info("Conexión a Supabase inicializada.")


def _db() -> Client:
    if _supabase is None:
        raise RuntimeError("Base de datos no inicializada. Llama init_db() primero.")
    return _supabase


def _reintentar(func, intentos: int = 3, espera: float = 2.0):
    """Ejecuta func hasta `intentos` veces ante excepciones, con pausa entre intentos."""
    ultimo_error = None
    for i in range(intentos):
        try:
            return func()
        except Exception as e:
            ultimo_error = e
            logger.warning(f"Intento {i + 1}/{intentos} fallido: {e}")
            if i < intentos - 1:
                time.sleep(espera)
    logger.error(f"Operación fallida tras {intentos} intentos: {ultimo_error}")
    raise ultimo_error


# ---------------------------------------------------------------------------
# Insertar pedido
# ---------------------------------------------------------------------------

def guardar_pedido(datos: dict, message_id: int, fecha: date, hora: str) -> Optional[int]:
    """
    Inserta el pedido en la tabla `pedidos` y sus negocios en `pedidos_negocios`.
    Retorna el id del pedido insertado, o None si ya existía (duplicado por message_id).
    """
    def _insertar():
        resp = (
            _db()
            .table("pedidos")
            .insert(
                {
                    "numero_pedido": datos["numero_pedido"],
                    "fecha": fecha.isoformat(),
                    "hora": hora,
                    "cliente": datos.get("cliente"),
                    "telefono": datos.get("telefono"),
                    "mensajero": None,
                    "monto_mensajeria": datos.get("monto_mensajeria"),
                    "total": datos.get("total"),
                    "message_id": message_id,
                }
            )
            .execute()
        )
        return resp

    # Verificar si ya existe
    existe = (
        _db()
        .table("pedidos")
        .select("id")
        .eq("message_id", message_id)
        .execute()
    )
    if existe.data:
        logger.info(f"Pedido con message_id={message_id} ya existe, ignorando.")
        return None

    resp = _reintentar(_insertar)
    if not resp.data:
        return None

    pedido_id = resp.data[0]["id"]

    # Insertar negocios
    for negocio in datos.get("negocios", []):
        def _ins_negocio(n=negocio, pid=pedido_id):
            _db().table("pedidos_negocios").insert(
                {"pedido_id": pid, "negocio": n["negocio"], "subtotal": n["subtotal"]}
            ).execute()

        _reintentar(_ins_negocio)

    logger.info(f"Pedido #{datos['numero_pedido']} guardado con id={pedido_id}.")
    return pedido_id


# ---------------------------------------------------------------------------
# Asignar mensajero
# ---------------------------------------------------------------------------

def asignar_mensajero(message_id: int, mensajero: str) -> Optional[str]:
    """
    Actualiza el mensajero del pedido identificado por message_id.
    Retorna el numero_pedido actualizado, o None si no se encontró.
    """
    def _actualizar():
        return (
            _db()
            .table("pedidos")
            .update({"mensajero": mensajero})
            .eq("message_id", message_id)
            .execute()
        )

    resp = _reintentar(_actualizar)
    if resp.data:
        return resp.data[0].get("numero_pedido")
    return None


# ---------------------------------------------------------------------------
# Estadísticas
# ---------------------------------------------------------------------------

def stats_hoy() -> dict:
    hoy = date.today().isoformat()

    def _query():
        return _db().table("pedidos").select("total, monto_mensajeria").eq("fecha", hoy).execute()

    resp = _reintentar(_query)
    rows = resp.data or []
    return {
        "pedidos": len(rows),
        "mensajeria": sum(r.get("monto_mensajeria") or 0 for r in rows),
        "total": sum(r.get("total") or 0 for r in rows),
    }


def stats_mes() -> dict:
    hoy = date.today()
    inicio = date(hoy.year, hoy.month, 1).isoformat()

    def _query():
        return (
            _db()
            .table("pedidos")
            .select("total, monto_mensajeria")
            .gte("fecha", inicio)
            .execute()
        )

    resp = _reintentar(_query)
    rows = resp.data or []
    return {
        "pedidos": len(rows),
        "mensajeria": sum(r.get("monto_mensajeria") or 0 for r in rows),
        "total": sum(r.get("total") or 0 for r in rows),
    }


def stats_negocios_mes() -> list[dict]:
    """Retorna lista de {negocio, subtotal} ordenada de mayor a menor."""
    hoy = date.today()
    inicio = date(hoy.year, hoy.month, 1).isoformat()

    def _query():
        # Obtener ids de pedidos del mes
        pedidos_resp = (
            _db()
            .table("pedidos")
            .select("id")
            .gte("fecha", inicio)
            .execute()
        )
        ids = [r["id"] for r in (pedidos_resp.data or [])]
        if not ids:
            return []
        negocios_resp = (
            _db()
            .table("pedidos_negocios")
            .select("negocio, subtotal")
            .in_("pedido_id", ids)
            .execute()
        )
        return negocios_resp.data or []

    rows = _reintentar(_query)

    acumulado: dict[str, int] = {}
    for r in rows:
        nombre = r["negocio"]
        acumulado[nombre] = acumulado.get(nombre, 0) + (r.get("subtotal") or 0)

    return sorted(
        [{"negocio": k, "subtotal": v} for k, v in acumulado.items()],
        key=lambda x: x["subtotal"],
        reverse=True,
    )


def stats_mensajero_mes(mensajero: str) -> dict:
    hoy = date.today()
    inicio = date(hoy.year, hoy.month, 1).isoformat()

    def _query():
        return (
            _db()
            .table("pedidos")
            .select("monto_mensajeria")
            .gte("fecha", inicio)
            .ilike("mensajero", mensajero)
            .execute()
        )

    resp = _reintentar(_query)
    rows = resp.data or []
    return {
        "pedidos": len(rows),
        "mensajeria": sum(r.get("monto_mensajeria") or 0 for r in rows),
    }


def stats_mensajeros_mes() -> list[dict]:
    """Retorna ranking de mensajeros del mes con sus pedidos y ganancias."""
    hoy = date.today()
    inicio = date(hoy.year, hoy.month, 1).isoformat()

    def _query():
        return (
            _db()
            .table("pedidos")
            .select("mensajero, monto_mensajeria")
            .gte("fecha", inicio)
            .not_.is_("mensajero", "null")
            .execute()
        )

    resp = _reintentar(_query)
    rows = resp.data or []

    acumulado: dict[str, dict] = {}
    for r in rows:
        nombre = r["mensajero"] or "Sin asignar"
        if nombre not in acumulado:
            acumulado[nombre] = {"pedidos": 0, "mensajeria": 0}
        acumulado[nombre]["pedidos"] += 1
        acumulado[nombre]["mensajeria"] += r.get("monto_mensajeria") or 0

    return sorted(
        [{"mensajero": k, **v} for k, v in acumulado.items()],
        key=lambda x: x["mensajeria"],
        reverse=True,
    )
