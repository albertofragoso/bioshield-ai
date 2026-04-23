# Flujo Contributivo a Open Food Facts (Fase 2)

**Versión:** 1.0  
**Última actualización:** 2026-04-23  
**Estatus:** Implementado

---

## 1. Propósito

Cuando un usuario escanea una foto de etiqueta de un producto que no existe en Open Food Facts (OFF), BioShield AI puede contribuir los ingredientes extraídos vía Gemini Vision + la imagen al servidor de OFF de forma asíncrona, ampliando la base de datos colaborativa de OFF.

El flujo **requiere consentimiento explícito por escaneo** (opt-in, no global) y cumple con la licencia ODbL (Open Data Commons Open Database License) de OFF.

---

## 2. Arquitectura Técnica

### 2.1 Flujo de Usuario

```
1. Usuario toma foto de etiqueta en /scan
   ↓
2. Gemini Vision extrae ingredientes
   ↓
3. Backend devuelve ScanResponse exitoso (source=photo)
   ↓
4. UI muestra toggle "Contribuir a Open Food Facts (ODbL)" — OFF por defecto
   ↓
5a. Si toggle ENCENDIDO + user da ok:
    - FE: POST /scan/contribute { barcode, ingredients, image_base64?, consent: true }
    - BE: Crea row off_contributions (status=PENDING)
    - BE: BackgroundTask envía a OFF (ej. 202 Accepted)
    - FE: Toast "Gracias por contribuir a Open Food Facts"
    
5b. Si toggle APAGADO:
    - No se dispara /scan/contribute
    - Análisis del scan termina normalmente
```

### 2.2 Componentes Backend

| Componente | Dónde | Responsabilidad |
|---|---|---|
| **Config** | `app/config.py` | `off_contrib_enabled`, `off_contributor_user`, `off_contributor_password`, `off_write_base_url` |
| **ORM** | `app/models/off_contribution.py` | Tabla `off_contributions` — audit trail |
| **API Client** | `app/services/off_client.py` | `contribute_product()`, `upload_product_image()` → POST a OFF |
| **Endpoint** | `app/routers/scan.py` | `POST /scan/contribute` (202) + `_run_off_contribution_impl()` |
| **Schemas** | `app/schemas/models.py` | `OFFContributeRequest`, `OFFContributeResponse` |
| **Migration** | `alembic/versions/` | `off_contributions` table + indices |

### 2.3 Componentes Frontend

| Componente | Dónde | Responsabilidad |
|---|---|---|
| **Toggle** | `components/scanner/OFFContributeToggle.tsx` | Switch + label ODbL + tooltip |
| **Post-Scan Hook** | `app/(app)/scan/page.tsx` | Disparar `/scan/contribute` si toggle=on |
| **API Client** | `lib/api/scan.ts` | `contributeToOff(body)` |
| **Types** | `lib/api/types.ts` | `OFFContributeRequest`, `OFFContributeResponse` |

---

## 3. Consentimiento y ODbL

### 3.1 Requisitos Legales

La licencia ODbL de OFF requiere:

1. **Consentimiento explícito:** El usuario debe **activar un toggle** antes de cada contribución (no es consentimiento global).
2. **Transparencia:** La UI debe indicar claramente qué datos se envían (ingredientes + imagen, sin datos personales).
3. **Identificación:** BioShield AI está registrado como contributor en OFF con credenciales de cuenta de aplicación.

### 3.2 Implementación

**Toggle UI:**
```
[OFF] "Contribuir esta foto a Open Food Facts (ODbL)"
      Ayuda a que otros usuarios encuentren este producto.
      Solo enviamos ingredientes + imagen, sin datos personales.
      [?] ¿Qué significa ODbL? → tooltip
```

**Audit Log (`off_contributions` table):**
- `consent_at`: timestamp de cuándo el usuario consintió (momento del toggle).
- `barcode`: código del producto enviado.
- `ingredients_text`: lista de ingredientes exacta.
- `image_submitted`: si la imagen se subió con éxito.
- `status`: PENDING | SUBMITTED | FAILED.
- `off_response_url`: URL del producto en OFF (si éxito).
- `off_error`: mensaje de error si falló.

---

## 4. Configuración en Desarrollo y Producción

### 4.1 Variables de Entorno

```bash
# .env
OFF_CONTRIB_ENABLED=false                        # Feature flag — false en dev
OFF_WRITE_BASE_URL="https://world.openfoodfacts.org/cgi"
OFF_APP_NAME="BioShieldAI"
OFF_APP_VERSION="1.0"
OFF_CONTRIBUTOR_USER=""                         # Registrar cuenta en OFF
OFF_CONTRIBUTOR_PASSWORD=""                     # Contraseña de la cuenta
OFF_CONTRIB_TIMEOUT_SECONDS=15
OFF_CONTRIB_SYNC_FOR_TESTS=false               # Sincrónico solo en pytest
```

### 4.2 Registro de Cuenta en OFF

1. Crear cuenta en https://world.openfoodfacts.org/user/sign_up
2. Confirmar email.
3. Usar email + password en `OFF_CONTRIBUTOR_USER` y `OFF_CONTRIBUTOR_PASSWORD`.
4. En producción, usar un manejador de secretos (AWS Secrets Manager, Render Secrets, etc.)

---

## 5. Flujo Técnico Detallado

### 5.1 Request → Endpoint

```python
POST /scan/contribute HTTP/1.1
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "barcode": "photo:abc123abc123abc1",
  "ingredients": ["azúcar", "agua", "sal"],
  "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  "consent": true,
  "scan_history_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 5.2 Respuesta Inmediata (202 Accepted)

```python
HTTP/1.1 202 Accepted
Content-Type: application/json

{
  "contribution_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "status": "PENDING",
  "message": "Contribución recibida. Se enviará a Open Food Facts en segundo plano."
}
```

El endpoint devuelve **202 Accepted** (no 201) porque la persua real a OFF ocurre en `BackgroundTasks`.

### 5.3 Tarea en Segundo Plano

```
_run_off_contribution_impl()
├─ Carga row de off_contributions desde DB
├─ Llama contribute_product(barcode, ingredients_text)
│  └─ POST form-urlencoded a world.openfoodfacts.org/cgi/product_jqm2.pl
│     ├─ code (barcode)
│     ├─ user_id (OFF account)
│     ├─ password (OFF password)
│     ├─ ingredients_text_es (ingredientes)
│     ├─ lang=es
│     └─ comment="Added via BioShieldAI"
├─ Si éxito + image_base64:
│  └─ Llama upload_product_image(barcode, image_base64)
│     └─ POST multipart a world.openfoodfacts.org/cgi/product_image_upload.pl
├─ Actualiza row: status, off_response_url, off_error, submitted_at
└─ db.commit()
```

Si `off_contrib_enabled=False` (dev), la tarea retorna `status=FAILED` con `off_error="Feature flag disabled"` sin hacer llamadas HTTP a OFF.

---

## 6. Manejo de Errores

### 6.1 Errores en Backend

| Error | Causa | Mitigación |
|---|---|---|
| 401 Unauthorized | No autenticado | Guard JWT |
| 422 Validation Error | `consent=false` o `ingredients=[]` | Validación Pydantic — cliente debe arreglarlo |
| 429 Too Many Requests | Rate limit (10/min) | Cola, retry exponencial en FE |
| OFF 5xx | Servidor de OFF no disponible | `status=FAILED`, `off_error` registrado |
| Timeout | OFF lento (>15s) | `status=FAILED`, `off_error` registrado |

### 6.2 Errores en Frontend

| Error | Mitigación |
|---|---|
| `/scan/contribute` → 5xx | Toast warning no bloqueante; resultado sigue visible |
| Network error | Retry automático con backoff (manejado por `apiFetch`) |
| Usuario deniega permisos | Toggle permanece apagado; user puede reactivar |

---

## 7. Política de Privacidad y ARCO

### 7.1 Qué se envía a OFF

✅ **SÍ se envía:**
- Código de barras (o pseudo-barcode `photo:<uuid>`)
- Lista de ingredientes (texto libre)
- Foto de la etiqueta (opcional)

❌ **NO se envía:**
- Datos de biomarcadores del usuario
- Email del usuario
- Historial de scans anteriores
- IP address (solo User-Agent estándar)

### 7.2 Derecho al Olvido (ARCO)

Si un usuario solicita eliminar una contribución:

1. **Local:** Eliminar row de `off_contributions` en BioShield.
2. **Remote:** Enviar delete request **manual** a OFF (OFF no tiene DELETE API automatizado).
   ```bash
   # Manual (a través de OFF web interface o soporte OFF)
   POST https://world.openfoodfacts.org/cgi/product_jqm2.pl
   ?code=<barcode>&user_id=<user>&password=<password>&delete=1
   ```

---

## 8. Testing

### 8.1 Test Suite (`tests/test_off_contribute.py`)

10 tests que cubren:

- **Auth:** 401 sin credentials
- **Validación Pydantic:** `consent=false` → 422, `ingredients=[]` → 422
- **Feature flag off:** row con `status=FAILED`, `off_error="Feature flag disabled"`
- **Happy path:** row con `status=SUBMITTED`, `off_response_url` poblado
- **Image upload:** `image_submitted=True` en el row
- **OFF 5xx:** row con `status=FAILED`, `off_error` registrado
- **Row integrity:** `ingredients_text` almacenado correctamente
- **Response shape:** 202 devuelve objeto `OFFContributeResponse`

### 8.2 Mocking en Tests

```python
# Se mockea httpx.AsyncClient
monkeypatch.setattr(
    httpx, "AsyncClient",
    lambda *a, **kw: _FakeAsyncClient(_FakeResponse(200))
)
```

En producción, OFF recibe el POST real a `world.openfoodfacts.org/cgi/product_jqm2.pl`.

---

## 9. Deployment Checklist

- [ ] Registrar cuenta en https://world.openfoodfacts.org/user/sign_up
- [ ] Copiar credenciales a `.env`: `OFF_CONTRIBUTOR_USER`, `OFF_CONTRIBUTOR_PASSWORD`
- [ ] Set `OFF_CONTRIB_ENABLED=true` en Render secrets (o staging first)
- [ ] Verificar que la tabla `off_contributions` existe (`alembic upgrade head`)
- [ ] En staging: probar con `world.openfoodfacts.net` (servidor de pruebas de OFF)
- [ ] Smoke test: escanear un producto inexistente, contribuir, verificar que aparece en OFF en 5-10 min
- [ ] Revisar logs para `OFFContribution SUBMITTED` rows

---

## 10. Referencias

- **PRD:** `PRD.md` §9.6 (Flujo de contribución a Open Food Facts)
- **Architecture:** `docs/architecture.md` §1.3 (off_contributions table)
- **OFF API:** https://wiki.openfoodfacts.org/API/Write
- **OFF Licensing:** https://openfoodfacts.org/terms-of-use (ODbL)
- **Code:** `backend/app/routers/scan.py` (endpoint), `backend/app/services/off_client.py` (client)
