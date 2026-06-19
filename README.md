# Bot Contable — Tráelo

Bot de Telegram que escucha los pedidos del grupo y lleva contabilidad automática en Supabase. No interfiere con el bot de pedidos existente.

---

## Paso 1 — Crear el bot en BotFather

1. Abre Telegram y busca `@BotFather`.
2. Envía `/newbot`.
3. Elige un nombre para el bot (ej. `Tráelo Contable`).
4. Elige un username que termine en `bot` (ej. `traelo_contable_bot`).
5. BotFather te dará un **token** con este formato: `123456789:ABCDefgh...`
6. Guarda ese token — es tu `TELEGRAM_BOT_TOKEN`.

---

## Paso 2 — Añadir el bot al grupo como administrador

1. Abre el grupo en Telegram.
2. Ve a **Configuración del grupo → Administradores → Añadir administrador**.
3. Busca el username del bot que acabas de crear y agrégalo.
4. Los permisos mínimos necesarios son: **Leer mensajes** (los bots los leen siempre) y **Enviar mensajes**.

> El bot necesita ser admin para poder verificar si quien usa los comandos es admin del grupo.

---

## Paso 3 — Obtener el CHAT_ID del grupo

1. Añade temporalmente `@userinfobot` al grupo.
2. Escribe cualquier mensaje en el grupo.
3. `@userinfobot` responderá con el **Chat ID** del grupo (número negativo, ej. `-1001234567890`).
4. Retira `@userinfobot` si quieres.
5. Ese número negativo es tu `TELEGRAM_GROUP_ID`.

**Alternativa:** Habla con `@RawDataBot` o envía un mensaje al grupo y revisa la URL si usas Telegram Web.

---

## Paso 4 — Crear cuenta en Supabase (sin tarjeta)

1. Ve a [https://supabase.com](https://supabase.com) y haz clic en **Start your project**.
2. Regístrate con GitHub o email — no pide tarjeta de crédito.
3. El plan gratuito incluye 500 MB de base de datos, más que suficiente.

---

## Paso 5 — Crear el proyecto y las tablas

1. En el dashboard de Supabase, haz clic en **New project**.
2. Elige un nombre (ej. `traelo-contable`), una contraseña para la DB y la región más cercana.
3. Espera ~1 minuto a que se cree el proyecto.
4. Ve a **SQL Editor** (icono de terminal en el menú izquierdo).
5. Pega y ejecuta este SQL:

```sql
-- Tabla principal de pedidos
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

-- Tabla de negocios por pedido
CREATE TABLE pedidos_negocios (
  id SERIAL PRIMARY KEY,
  pedido_id INTEGER REFERENCES pedidos(id),
  negocio TEXT,
  subtotal INTEGER
);
```

6. Haz clic en **Run** (o Ctrl+Enter). Deberías ver "Success. No rows returned."

---

## Paso 6 — Obtener SUPABASE_URL y SUPABASE_KEY

1. En el menú de tu proyecto Supabase, ve a **Settings → API**.
2. Copia la **Project URL** → es tu `SUPABASE_URL`.
3. En la sección **Project API keys**, copia la clave `anon` `public` → es tu `SUPABASE_KEY`.

> Usa la clave `anon`, NO la `service_role`. La anon es suficiente para este bot.

---

## Paso 7 — Subir el código a GitHub

El código debe estar en un repositorio de GitHub para que Render lo despliegue.

```bash
git init
git add .
git commit -m "Bot contable Tráelo"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/traelo-bot-contable.git
git push -u origin main
```

---

## Paso 8 — Deployar en Render.com como Background Worker

1. Ve a [https://render.com](https://render.com) y crea una cuenta gratuita.
2. Haz clic en **New → Background Worker**.
3. Conecta tu cuenta de GitHub y selecciona el repositorio del bot.
4. Render detectará el `render.yaml` automáticamente. Si no:
   - **Name:** `traelo-bot-contable`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python main.py`
5. Haz clic en **Create Background Worker**.

> **¿Por qué Background Worker y no Web Service?**  
> Los Web Services gratuitos en Render se "duermen" tras 15 minutos de inactividad. Un Background Worker corre 24/7 de forma continua y es ideal para bots con polling.

---

## Paso 9 — Configurar las variables de entorno en Render

1. En el dashboard de Render, abre tu servicio.
2. Ve a la pestaña **Environment**.
3. Añade estas variables (una por una):

| Variable | Valor |
|---|---|
| `TELEGRAM_BOT_TOKEN` | El token de BotFather |
| `TELEGRAM_GROUP_ID` | El chat ID negativo del grupo |
| `SUPABASE_URL` | La Project URL de Supabase |
| `SUPABASE_KEY` | La clave anon de Supabase |

4. Haz clic en **Save Changes**. Render reiniciará el bot automáticamente.

---

## Uso del bot

### Registrar pedidos
El bot escucha automáticamente. Cada vez que el bot de pedidos publique un mensaje con el formato `🧾 Pedido #`, se guarda en Supabase sin que tengas que hacer nada.

### Asignar mensajero
Haz **reply** al mensaje del pedido y escribe:
```
/mensajero Juan
```

### Consultar estadísticas
```
/stats hoy          → pedidos del día de hoy
/stats mes          → pedidos del mes actual
/stats negocios     → facturación por negocio del mes
/stats mensajero Juan   → pedidos y ganancias de Juan en el mes
/stats mensajeros   → ranking de todos los mensajeros del mes
```

> Solo los **administradores del grupo** pueden usar estos comandos.

---

## Solución de problemas

**El bot no detecta los pedidos**  
- Verifica que el bot sea administrador del grupo.
- Comprueba que `TELEGRAM_GROUP_ID` sea el número correcto (negativo).
- Revisa los logs en Render → pestaña **Logs**.

**Error de Supabase**  
- Verifica que las tablas estén creadas (Paso 5).
- Confirma que `SUPABASE_URL` y `SUPABASE_KEY` sean correctas.

**Los comandos no responden**  
- Solo funcionan desde el grupo configurado en `TELEGRAM_GROUP_ID`.
- Solo los admins pueden usarlos — verifica que tu usuario sea admin.
