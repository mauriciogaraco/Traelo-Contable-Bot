import asyncio
import logging
import os

import uvicorn
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import database as db
from api import fastapi_app

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GROUP_ID = int(os.environ["TELEGRAM_GROUP_ID"])
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
PORT = int(os.environ.get("PORT", 8000))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")


async def _es_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        miembro = await context.bot.get_chat_member(GROUP_ID, update.effective_user.id)
        return miembro.status in ("administrator", "creator")
    except Exception as e:
        logger.warning(f"No se pudo verificar admin: {e}")
        return False


def _solo_grupo(update: Update) -> bool:
    return update.effective_chat and update.effective_chat.id == GROUP_ID


# ---------------------------------------------------------------------------
# Comando /mensajero
# ---------------------------------------------------------------------------

async def cmd_mensajero(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _solo_grupo(update):
        return
    if not await _es_admin(update, context):
        await update.message.reply_text("⛔ Solo los administradores pueden usar este comando.")
        return

    if not context.args:
        await update.message.reply_text("Uso: /mensajero <nombre> (haciendo reply al pedido)")
        return

    nombre_mensajero = " ".join(context.args).strip()

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "⚠️ Debes hacer *reply* al mensaje del pedido para asignar el mensajero.",
            parse_mode="Markdown",
        )
        return

    reply_msg_id = update.message.reply_to_message.message_id

    try:
        numero_pedido = await asyncio.to_thread(
            db.asignar_mensajero, reply_msg_id, nombre_mensajero
        )
        if numero_pedido:
            await update.message.reply_text(
                f"✅ Mensajero *{nombre_mensajero}* asignado al pedido *#{numero_pedido}*.",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                "⚠️ No encontré ese pedido en la base de datos. "
                "Asegúrate de hacer reply al mensaje del pedido original."
            )
    except Exception as e:
        logger.error(f"Error al asignar mensajero: {e}", exc_info=True)
        await update.message.reply_text("❌ Error al actualizar la base de datos. Intenta de nuevo.")


# ---------------------------------------------------------------------------
# Comando /stats
# ---------------------------------------------------------------------------

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _solo_grupo(update):
        return
    if not await _es_admin(update, context):
        await update.message.reply_text("⛔ Solo los administradores pueden usar este comando.")
        return

    if not context.args:
        await update.message.reply_text(
            "Uso:\n"
            "  /stats hoy\n"
            "  /stats mes\n"
            "  /stats negocios\n"
            "  /stats mensajero <nombre>\n"
            "  /stats mensajeros"
        )
        return

    subcomando = context.args[0].lower()

    try:
        if subcomando == "hoy":
            datos = await asyncio.to_thread(db.stats_hoy)
            texto = (
                f"📊 *Estadísticas de hoy*\n\n"
                f"📦 Pedidos: {datos['pedidos']}\n"
                f"🛵 Mensajerías: {_fmt(datos['mensajeria'])} CUP\n"
                f"💵 Total facturado: {_fmt(datos['total'])} CUP"
            )
            await update.message.reply_text(texto, parse_mode="Markdown")

        elif subcomando == "mes":
            datos = await asyncio.to_thread(db.stats_mes)
            texto = (
                f"📊 *Estadísticas del mes*\n\n"
                f"📦 Pedidos: {datos['pedidos']}\n"
                f"🛵 Mensajerías: {_fmt(datos['mensajeria'])} CUP\n"
                f"💵 Total facturado: {_fmt(datos['total'])} CUP"
            )
            await update.message.reply_text(texto, parse_mode="Markdown")

        elif subcomando == "negocios":
            negocios = await asyncio.to_thread(db.stats_negocios_mes)
            if not negocios:
                await update.message.reply_text("No hay datos de negocios para este mes.")
                return
            lineas = ["🏪 *Facturación por negocio (mes actual)*\n"]
            for i, n in enumerate(negocios, 1):
                lineas.append(f"{i}. {n['negocio']}: {_fmt(n['subtotal'])} CUP")
            await update.message.reply_text("\n".join(lineas), parse_mode="Markdown")

        elif subcomando == "mensajero":
            if len(context.args) < 2:
                await update.message.reply_text("Uso: /stats mensajero <nombre>")
                return
            nombre = " ".join(context.args[1:])
            datos = await asyncio.to_thread(db.stats_mensajero_mes, nombre)
            texto = (
                f"🛵 *Estadísticas de {nombre} (mes actual)*\n\n"
                f"📦 Pedidos: {datos['pedidos']}\n"
                f"💰 Ganancias mensajería: {_fmt(datos['mensajeria'])} CUP"
            )
            await update.message.reply_text(texto, parse_mode="Markdown")

        elif subcomando == "mensajeros":
            mensajeros = await asyncio.to_thread(db.stats_mensajeros_mes)
            if not mensajeros:
                await update.message.reply_text("No hay datos de mensajeros para este mes.")
                return
            lineas = ["🏆 *Ranking de mensajeros (mes actual)*\n"]
            for i, m in enumerate(mensajeros, 1):
                lineas.append(
                    f"{i}. {m['mensajero']}: {m['pedidos']} pedidos — {_fmt(m['mensajeria'])} CUP"
                )
            await update.message.reply_text("\n".join(lineas), parse_mode="Markdown")

        else:
            await update.message.reply_text(
                f"Subcomando desconocido: *{subcomando}*\n"
                "Opciones: hoy, mes, negocios, mensajero <nombre>, mensajeros",
                parse_mode="Markdown",
            )

    except Exception as e:
        logger.error(f"Error en /stats {subcomando}: {e}", exc_info=True)
        await update.message.reply_text("❌ Error al consultar la base de datos. Intenta de nuevo.")


# ---------------------------------------------------------------------------
# Arranque — FastAPI + bot polling en el mismo event loop
# ---------------------------------------------------------------------------

async def run() -> None:
    db.init_db(SUPABASE_URL, SUPABASE_KEY)

    # --- Bot ---
    bot_app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )
    bot_app.add_handler(CommandHandler("mensajero", cmd_mensajero))
    bot_app.add_handler(CommandHandler("stats", cmd_stats))

    # --- Uvicorn ---
    uvicorn_config = uvicorn.Config(
        fastapi_app,
        host="0.0.0.0",
        port=PORT,
        log_level="info",
    )
    uvicorn_server = uvicorn.Server(uvicorn_config)

    logger.info(f"Iniciando bot (grupo {GROUP_ID}) y API en puerto {PORT}...")

    async with bot_app:
        await bot_app.start()
        await bot_app.updater.start_polling(
            allowed_updates=["message", "edited_message", "channel_post", "edited_channel_post"],
            drop_pending_updates=True,
        )

        await uvicorn_server.serve()  # bloquea hasta Ctrl-C

        await bot_app.updater.stop()
        await bot_app.stop()


if __name__ == "__main__":
    asyncio.run(run())
