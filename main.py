import logging
import os
from datetime import datetime

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
from parser import parsear_pedido

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
# Handler: mensajes del grupo (detectar pedidos)
# ---------------------------------------------------------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _solo_grupo(update):
        return

    msg = update.message or update.channel_post
    if not msg or not msg.text:
        return

    datos = parsear_pedido(msg.text)
    if not datos:
        return

    ahora = datetime.now()
    try:
        pedido_id = db.guardar_pedido(
            datos=datos,
            message_id=msg.message_id,
            fecha=ahora.date(),
            hora=ahora.strftime("%H:%M:%S"),
        )
        if pedido_id:
            logger.info(
                f"Pedido #{datos['numero_pedido']} registrado (message_id={msg.message_id})."
            )
    except Exception as e:
        logger.error(f"Error al guardar pedido en Supabase: {e}", exc_info=True)


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
        numero_pedido = db.asignar_mensajero(reply_msg_id, nombre_mensajero)
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
            datos = db.stats_hoy()
            texto = (
                f"📊 *Estadísticas de hoy*\n\n"
                f"📦 Pedidos: {datos['pedidos']}\n"
                f"🛵 Mensajerías: {_fmt(datos['mensajeria'])} CUP\n"
                f"💵 Total facturado: {_fmt(datos['total'])} CUP"
            )
            await update.message.reply_text(texto, parse_mode="Markdown")

        elif subcomando == "mes":
            datos = db.stats_mes()
            texto = (
                f"📊 *Estadísticas del mes*\n\n"
                f"📦 Pedidos: {datos['pedidos']}\n"
                f"🛵 Mensajerías: {_fmt(datos['mensajeria'])} CUP\n"
                f"💵 Total facturado: {_fmt(datos['total'])} CUP"
            )
            await update.message.reply_text(texto, parse_mode="Markdown")

        elif subcomando == "negocios":
            negocios = db.stats_negocios_mes()
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
            datos = db.stats_mensajero_mes(nombre)
            texto = (
                f"🛵 *Estadísticas de {nombre} (mes actual)*\n\n"
                f"📦 Pedidos: {datos['pedidos']}\n"
                f"💰 Ganancias mensajería: {_fmt(datos['mensajeria'])} CUP"
            )
            await update.message.reply_text(texto, parse_mode="Markdown")

        elif subcomando == "mensajeros":
            mensajeros = db.stats_mensajeros_mes()
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
# Arranque
# ---------------------------------------------------------------------------

def main() -> None:
    db.init_db(SUPABASE_URL, SUPABASE_KEY)

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # ~filters.COMMAND excluye comandos para que los CommandHandlers los procesen
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Chat(GROUP_ID),
            handle_message,
        )
    )

    app.add_handler(CommandHandler("mensajero", cmd_mensajero))
    app.add_handler(CommandHandler("stats", cmd_stats))

    logger.info(f"Bot contable iniciado. Escuchando grupo {GROUP_ID}...")
    app.run_polling(
        allowed_updates=["message", "edited_message", "channel_post",
                         "edited_channel_post", "callback_query"],
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
