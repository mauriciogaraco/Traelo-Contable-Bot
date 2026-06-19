# Bot Contable — Tráelo

Bot de Telegram contable con dos modos en un solo proceso:

1. **API HTTP** — recibe pedidos de tu sistema vía `POST /pedido`, los envía al grupo de Telegram y los guarda en Supabase.
2. **Bot polling** — responde comandos `/stats` y `/mensajero` en el grupo.

---

## Variables de entorno

| Variable | Descripción |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token del bot (BotFather) |
| `TELEGRAM_GROUP_ID` | Chat ID del grupo (número negativo) |
| `SUPABASE_URL` | URL del proyecto Supabase |
| `SUPABASE_KEY` | Clave `anon` de Supabase |
| `API_SECRET_KEY` | Token secreto para autenticar llamadas al endpoint |
| `PORT` | Puerto HTTP (fps.ms lo inyecta automáticamente) |

---

## Tablas en Supabase

Ejecuta este SQL en **SQL Editor** de tu proyecto Supabase (solo si no existen):

```sql
CREATE TABLE pedidos (
  id SERIAL PRIMARY KEY,
  numero_pedido TEXT,
  fecha DATE,
  hora TIME,
  cliente TEXT,
  telefono TEXT,
  mensajero TEXT DEFAULT NULL,
  monto_mensajeria INTEGER,
  total INTEGER,
  message_id BIGINT UNIQUE
);

CREATE TABLE pedidos_negocios (
  id SERIAL PRIMARY KEY,
  pedido_id INTEGER REFERENCES pedidos(id),
  negocio TEXT,
  subtotal INTEGER
);
```

---

## Endpoint POST /pedido

### Autenticación

Todas las llamadas deben incluir el header:
```
Authorization: Bearer <API_SECRET_KEY>
```

### Formato del JSON

```json
{
  "numero_pedido": "4650",
  "cliente": "Melissa López",
  "direccion": "Ave 85 a # 9801 / 98 a y 100",
  "referencia": "La misma calle de la entrada del cementerio",
  "telefono": "54978740",
  "entrega": "Lo antes posible",
  "negocios": [
    {
      "nombre": "El Mercadito",
      "items": [
        {"producto": "Arroz 1kg", "cantidad": 2, "precio": 700},
        {"producto": "Aceite (900 mL)", "cantidad": 2, "precio": 1600}
      ],
      "subtotal": 6700
    }
  ],
  "mensajeria": 250,
  "total": 6950
}
```

### Ejemplo con curl

```bash
curl -X POST https://TU-SERVIDOR.fps.ms:PUERTO/pedido \
  -H "Authorization: Bearer MI_API_SECRET_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "numero_pedido": "4650",
    "cliente": "Melissa López",
    "direccion": "Ave 85 a # 9801",
    "telefono": "54978740",
    "entrega": "Lo antes posible",
    "negocios": [
      {
        "nombre": "El Mercadito",
        "items": [{"producto": "Arroz 1kg", "cantidad": 2, "precio": 700}],
        "subtotal": 1400
      }
    ],
    "mensajeria": 250,
    "total": 1650
  }'
```

### Respuesta exitosa (200)

```json
{"ok": true, "numero_pedido": "4650", "message_id": 12345}
```

### Verificar que el servidor está vivo

```bash
curl https://TU-SERVIDOR.fps.ms:PUERTO/health
# → {"status": "ok"}
```

---

## Comandos del bot en el grupo

Solo disponibles para **administradores** del grupo.

```
/stats hoy              → pedidos del día, mensajerías, total
/stats mes              → mismo pero del mes actual
/stats negocios         → facturación por negocio del mes
/stats mensajero Juan   → pedidos y ganancias de Juan en el mes
/stats mensajeros       → ranking de todos los mensajeros
/mensajero Juan         → (reply a un pedido) asigna el mensajero
```

---

## Deploy en fps.ms

1. Sube los archivos desde tu repo de GitHub.
2. El comando de inicio es: `python main.py`
3. Configura las variables de entorno en el panel de fps.ms:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_GROUP_ID`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `API_SECRET_KEY`
   - `PORT` (fps.ms generalmente lo inyecta solo)
4. El bot expone el endpoint HTTP en el puerto asignado por fps.ms.

---

## Archivos del proyecto

| Archivo | Función |
|---|---|
| `main.py` | Orquesta FastAPI + bot polling en un solo proceso asyncio |
| `api.py` | Endpoint `POST /pedido` y modelo Pydantic |
| `formatter.py` | Convierte el JSON del pedido al formato de mensaje de Telegram |
| `database.py` | Operaciones Supabase con reintentos automáticos |
| `requirements.txt` | Dependencias |
| `.env.example` | Plantilla de variables de entorno |
