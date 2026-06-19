import asyncio
import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from telegram import Bot

import database as db
from formatter import formatear_pedido

logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GROUP_ID = int(os.environ["TELEGRAM_GROUP_ID"])
API_SECRET_KEY = os.environ["API_SECRET_KEY"]

fastapi_app = FastAPI(title="Tráelo Contable API", docs_url=None, redoc_url=None)
_bot = Bot(token=BOT_TOKEN)


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------

class Item(BaseModel):
    producto: str
    cantidad: int
    precio: int


class Negocio(BaseModel):
    nombre: str
    items: list[Item] = []
    subtotal: int


class PedidoRequest(BaseModel):
    numero_pedido: str
    cliente: str
    direccion: str
    referencia: Optional[str] = ""
    telefono: str
    entrega: Optional[str] = "Lo antes posible"
    negocios: list[Negocio] = []
    mensajeria: int
    total: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _verificar_token(authorization: Optional[str]) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Header Authorization requerido")
    token = authorization[len("Bearer "):].strip()
    if token != API_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Token inválido")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@fastapi_app.get("/health")
async def health():
    return {"status": "ok"}


@fastapi_app.post("/pedido")
async def recibir_pedido(
    pedido: PedidoRequest,
    authorization: Optional[str] = Header(default=None),
):
    _verificar_token(authorization)

    texto = formatear_pedido(pedido.model_dump())

    # 1. Enviar al grupo de Telegram
    try:
        msg = await _bot.send_message(chat_id=GROUP_ID, text=texto)
    except Exception as e:
        logger.error(f"Error al enviar a Telegram: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail="Error al enviar mensaje a Telegram")

    # 2. Guardar en Supabase (en hilo separado para no bloquear el event loop)
    datos_db = {
        "numero_pedido": pedido.numero_pedido,
        "cliente": pedido.cliente,
        "telefono": pedido.telefono,
        "monto_mensajeria": pedido.mensajeria,
        "total": pedido.total,
        "negocios": [
            {"negocio": n.nombre, "subtotal": n.subtotal} for n in pedido.negocios
        ],
    }
    ahora = datetime.now()

    try:
        await asyncio.to_thread(
            db.guardar_pedido,
            datos=datos_db,
            message_id=msg.message_id,
            fecha=ahora.date(),
            hora=ahora.strftime("%H:%M:%S"),
        )
    except Exception as e:
        # El mensaje ya fue enviado — loguear sin fallar el endpoint
        logger.error(f"Error al guardar pedido #{pedido.numero_pedido} en Supabase: {e}", exc_info=True)

    logger.info(f"Pedido #{pedido.numero_pedido} enviado al grupo y guardado (message_id={msg.message_id}).")
    return {"ok": True, "numero_pedido": pedido.numero_pedido, "message_id": msg.message_id}
