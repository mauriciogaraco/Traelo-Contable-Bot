import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def parsear_pedido(texto: str) -> Optional[dict]:
    """
    Parsea un mensaje de pedido y retorna un dict con los campos,
    o None si el mensaje no tiene el formato esperado.
    """
    try:
        if "🧾 Pedido #" not in texto:
            return None

        resultado = {
            "numero_pedido": None,
            "cliente": None,
            "telefono": None,
            "monto_mensajeria": None,
            "total": None,
            "negocios": [],
        }

        # Número de pedido
        m = re.search(r"🧾\s*Pedido\s*#(\S+)", texto)
        if m:
            resultado["numero_pedido"] = m.group(1).strip(" —-")

        # Cliente
        m = re.search(r"👤\s*Cliente:\s*(.+)", texto)
        if m:
            resultado["cliente"] = m.group(1).strip()

        # Teléfono
        m = re.search(r"📞\s*Teléfono:\s*(.+)", texto)
        if m:
            resultado["telefono"] = m.group(1).strip()

        # Mensajería
        m = re.search(r"🛵\s*Mensajer[ií]a:\s*([\d,\.]+)\s*CUP", texto, re.IGNORECASE)
        if m:
            resultado["monto_mensajeria"] = _parse_monto(m.group(1))

        # Total
        m = re.search(r"💵\s*Total:\s*([\d,\.]+)\s*CUP", texto, re.IGNORECASE)
        if m:
            resultado["total"] = _parse_monto(m.group(1))

        # Negocios y subtotales
        # Busca bloques "🏪 NombreNegocio\n...\nSubtotal: X CUP"
        bloques = re.finditer(
            r"🏪\s*(.+?)\n(.*?)Subtotal:\s*([\d,\.]+)\s*CUP",
            texto,
            re.DOTALL | re.IGNORECASE,
        )
        for bloque in bloques:
            negocio = bloque.group(1).strip()
            subtotal = _parse_monto(bloque.group(3))
            resultado["negocios"].append({"negocio": negocio, "subtotal": subtotal})

        # Validar campos mínimos obligatorios
        if not resultado["numero_pedido"] or resultado["total"] is None:
            logger.warning("Mensaje con formato de pedido pero campos insuficientes.")
            return None

        return resultado

    except Exception as e:
        logger.error(f"Error al parsear pedido: {e}", exc_info=True)
        return None


def _parse_monto(texto: str) -> int:
    """Convierte '1,020' o '1.020' o '1020' a entero."""
    limpio = texto.replace(",", "").replace(".", "").strip()
    return int(limpio)
