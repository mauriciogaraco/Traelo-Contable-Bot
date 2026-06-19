def _fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def formatear_pedido(pedido: dict) -> str:
    """
    Genera el texto del mensaje de Telegram a partir del dict del pedido.
    Produce exactamente el mismo formato que el bot original.
    """
    lineas = [
        f"🧾 Pedido #{pedido['numero_pedido']} — Tráelo",
        f"👤 Cliente: {pedido['cliente']}",
        f"📍 Dirección: {pedido['direccion']}",
    ]

    if pedido.get("referencia"):
        lineas.append(f"🧭 Referencia: {pedido['referencia']}")

    lineas += [
        f"📞 Teléfono: {pedido['telefono']}",
        f"🕒 Entrega: {pedido.get('entrega', 'Lo antes posible')}",
    ]

    for negocio in pedido.get("negocios", []):
        lineas.append(f"🏪 {negocio['nombre']}")
        for item in negocio.get("items", []):
            lineas.append(
                f"- {item['producto']} × {item['cantidad']} — {_fmt(item['precio'])} CUP"
            )
        lineas.append(f"Subtotal: {_fmt(negocio['subtotal'])} CUP")

    lineas += [
        f"🛵 Mensajería: {_fmt(pedido['mensajeria'])} CUP",
        f"💵 Total: {_fmt(pedido['total'])} CUP",
    ]

    return "\n".join(lineas)
