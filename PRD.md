# PRD v5.0: BioShield AI – Sistema de Transparencia Metabólica & Reality Engineering

**Estatus:** Especificación Final de Ingeniería (MVP Listo para Desarrollo)  
**Autor:** Alberto Fragoso  
**Stack Core:** Next.js (Frontend), FastAPI (Backend), LangGraph, ChromaDB, Gemini 1.5 Flash, Open Food Facts API.  
**Licencia:** MIT License (Software) / ODbL (Datos).

---

## 1. Arquitectura Técnica y Despliegue

* **Frontend:** Next.js (React) hosteado en Vercel. Gestión de estado con SWR para cacheo de peticiones por código de barras.
* **Backend:** FastAPI (Python) hosteado en Render/Railway. Orquestación de agentes con LangGraph.
* **Modelos:** Gemini 1.5 Flash (Visión y Razonamiento) y `gemini-embedding-001` (Semántica).

---

## 2. Flujo Principal de Operación (Main Workflow)

1. **Autenticación (Auth):** Validación mediante JWT almacenado en HTTP-only cookies.
2. **Identificación Híbrida (Scanner Flow):**
   * El sistema intenta leer el **Barcode**. Si tiene éxito, consulta la API de Open Food Facts (OFF).
   * **Manejo de Errores (Scanner):** Si la cámara no logra leer el barcode tras 3 segundos de enfoque o el producto no existe en OFF, la UI muestra un botón de acción inmediata: **"Cambiar a modo Foto de Etiqueta"**.
   * El usuario toma una foto de la lista de ingredientes; el sistema procesa la imagen vía VLM y activa el flujo contributivo hacia OFF de forma asíncrona.
3. **Procesamiento Bio-Sync:** El agente accede a los biomarcadores del usuario. Para garantizar la privacidad, los datos desencriptados **existen únicamente en variables locales del proceso de evaluación** y no se persisten en logs ni en almacenamiento temporal tras finalizar la ejecución del grafo.
4. **Análisis Semántico (Embeddings):** Los ingredientes se vectorizan y comparan contra los índices de la FDA, EFSA y EWG.

---

## 3. Extracción Estructurada (Structured Outputs)

Para garantizar la integridad del JSON, tanto la extracción de etiquetas como la de estudios de laboratorio se realizan mediante esquemas de **Pydantic**.

### A. Prompt: Extractor de Ingredientes (Visión)
> "Eres un experto en tecnología de alimentos. Analiza la imagen de la etiqueta proporcionada. Extrae los ingredientes evitando claims de marketing. Corrige errores de lectura del OCR basándote en el contexto químico de los alimentos."
>
> **Esquema de Salida (Pydantic):**
> ```python
> class ProductExtraction(BaseModel):
>     ingredients: List[str]
>     has_additives: bool
>     language: str = "es"
> ```

### B. Prompt: Agente Conciliador (RAG Node)
> "Sintetiza el riesgo del ingrediente '{ingredient}' usando el contexto científico: {rag_context}. Detecta conflictos entre agencias. NO des consejos médicos; redacta como hallazgos de literatura científica."

---

## 4. Gestión de Caché y Latencia

* **MVP (SWR):** Implementación de caché en el cliente basado estrictamente en el **Barcode** (o Hash de la lista de ingredientes). Esto permite que, si un usuario re-escanea un producto en la misma sesión, la respuesta sea instantánea sin consumir cuota de API ni tokens.
* **Mejora Futura:** Capa de caché geográfica para pre-cargar en el dispositivo los 50 productos más consumidos en la zona específica del usuario (CDMX, etc.).

---

## 5. Plan de Gestión de Riesgos

| Riesgo | Impacto | Estrategia de Mitigación |
| :--- | :--- | :--- |
| **Privacidad de Datos** | Crítico | Encriptación AES-256 en reposo. Uso exclusivo de variables locales en memoria volátil para datos desencriptados (no persistencia en logs). |
| **Falla de Scanner** | Medio | Flujo de fallback manual: del escaneo de barcode al modo "Foto de Etiqueta" con un solo clic. |
| **Vendor Lock-in** | Alto | Arquitectura modular que permite sustituir Gemini por modelos locales como **BGE-M3** o **Qwen3-Embedding** en caso de deprecación. |
| **Sesgo en PDF Parsing** | Alto | Uso de Structured Outputs en Gemini Flash para forzar la validación de tipos de datos en resultados de laboratorio. |

---

## 6. Roadmap de Desarrollo

* **Fase 1 (MVP):** Extracción estructurada (Ingredientes/Bio-Sync), LangGraph funcional, Semáforo visual en Next.js y caché por Barcode. **Bloqueante de lanzamiento:** publicación de Política de Privacidad y Términos de Uso (ver §9) antes de abrir registro público.
* **Fase 2 (Retail Integration):** Conexión con APIs de supermercados (Walmart/Cornershop) para análisis preventivo y caché geográfico.
* **Fase 3 (Reality Engineering):** RAG Multidimensional con ingesta de sabiduría ancestral y agente de conciliación holístico.

---

## 7. El Semáforo Visual (Output Next.js)

* **Gris:** Error de lectura/Datos insuficientes.
* **Azul:** Ingredientes limpios.
* **Amarillo:** Aditivos bajo observación (EWG/EFSA).
* **Naranja:** Conflicto detectado con biomarcadores del usuario (Bio-Sync).
* **Rojo:** Toxicidad confirmada o ingrediente prohibido.

---

## 8. Plan de Frontend (MVP)

### 8.1 Stack
* **Next.js 14 (App Router) + TypeScript**, desplegado en Vercel.
* **SWR** para caché por barcode (ya definido en §4).
* **Tailwind CSS + shadcn/ui** para UI (sin vendor lock-in, tree-shakeable).
* **@zxing/browser** (o `html5-qrcode`) para lectura de barcode en navegador.
* **react-hook-form + zod** — schemas espejo de los Pydantic del backend.
* **PWA-first** con `next-pwa` para acceso a cámara móvil sin app store.
* **Auth:** `fetch` con `credentials: 'include'` contra cookies HTTP-only del backend.

### 8.2 Estructura de carpetas
```
frontend/
├── app/
│   ├── (auth)/login, register
│   ├── (app)/scan            ← barcode + fallback foto
│   ├── (app)/result/[id]     ← semáforo + detalle ingredientes
│   └── (app)/biomarkers      ← subir PDFs de laboratorio
├── components/
│   ├── Scanner/              ← barcode reader + modo foto (§2)
│   ├── TrafficLight/         ← 5 estados del §7
│   └── IngredientCard/
└── lib/api/                  ← cliente tipado contra FastAPI
```

### 8.3 Orden de implementación
1. **Bootstrap + Auth UI** — login/register contra `/auth/*` (ya funcional en backend).
2. **Pantalla Scan** con fallback manual a foto (mitiga riesgo "Falla de Scanner" del §5).
3. **Componente TrafficLight** con los 5 estados — mockeable antes del backend de análisis.
4. **Integración real** cuando `/scan` y el grafo LangGraph estén listos.
5. **Pantalla Biomarkers** (upload de PDFs) — depende de Structured Outputs del §3.

### 8.4 Decisión pendiente
* **PWA vs. Capacitor (nativo):** PWA cubre MVP y Android/CDMX; iOS Safari tiene limitaciones en cámara standalone. Revisar en Fase 2 si el mix de usuarios lo requiere.

---

## 9. Cumplimiento Legal y Documentos Públicos

BioShield procesa **datos sensibles de salud** (biomarcadores de sangre) y **contenido de usuario** (fotos de etiquetas). La publicación de Política de Privacidad y Términos de Uso es **bloqueante para abrir registro público** (ver §6, Fase 1).

### 9.1 Ubicación y artefactos

```
docs/legal/
├── privacy-policy.md        ← consumo humano + renderizado en /privacy
├── terms-of-service.md      ← consumo humano + renderizado en /terms
└── data-processing.md       ← anexo técnico: flujo de datos y terceros
```

El frontend debe renderizar ambos documentos en rutas públicas (`/privacy`, `/terms`) y vincularlos desde el formulario de registro con checkbox de aceptación obligatoria.

### 9.2 Decisiones pendientes

| Decisión | Opciones | Default recomendado |
| :--- | :--- | :--- |
| **Jurisdicción primaria** | México (LFPDPPP) / GDPR / ambas | México Fase 1; GDPR si Fase 2 abre a EU |
| **Profundidad inicial** | Outline para abogado / draft completo autogenerado | Outline + draft inicial con disclaimer "pendiente revisión legal" |
| **Encargado de datos** | Persona física designada / entidad legal | Definir antes de lanzar |
| **Contacto ARCO** | Email dedicado / formulario web | Email `privacy@<dominio>` |

### 9.3 Política de Privacidad — contenido requerido

1. **Datos recolectados:**
   * **Identidad:** email, contraseña (hash bcrypt, nunca en claro).
   * **Salud (sensibles):** biomarcadores de sangre subidos por el usuario.
   * **Contenido:** fotos de etiquetas nutricionales, códigos de barras escaneados.
   * **Derivados:** historial de escaneos y veredictos del Semáforo (§7).
   * **Técnicos:** IP, user-agent, timestamps (rate limiting y auditoría).

2. **Base legal (LFPDPPP / GDPR Art. 9):**
   * Consentimiento **explícito y granular** para datos de salud (checkbox separado del registro).
   * Consentimiento general para datos de identidad y contenido.

3. **Finalidades:**
   * Análisis de conflictos entre ingredientes y biomarcadores del usuario.
   * Contribución asíncrona a Open Food Facts cuando el usuario lo autoriza explícitamente (ver §9.6).
   * Mejora del servicio (métricas agregadas y anonimizadas).
   * **No se usa para publicidad, perfilado comercial ni venta a terceros.**

4. **Retención:**
   * Biomarcadores: **180 días** (§5), eliminación automática por cron job.
   * Datos de cuenta: hasta baja solicitada por el usuario.
   * Logs técnicos: 90 días.
   * Backups: 30 días adicionales tras eliminación lógica.

5. **Terceros que procesan datos (subencargados):**
   * **Google (Gemini API):** procesa fotos de etiquetas y ejecuta VLM/embeddings. No retiene datos según Google AI Terms.
   * **Open Food Facts:** recibe contribuciones de fotos/ingredientes **solo con consentimiento explícito** del usuario.
   * **Vercel:** hosting del frontend (EU/US edge).
   * **Render/Railway:** hosting del backend y base de datos.

6. **Seguridad:**
   * Encriptación AES-256-GCM en reposo para biomarcadores (§5).
   * JWT en cookies HTTP-only + SameSite.
   * Datos desencriptados existen únicamente en memoria volátil durante la ejecución del grafo (§2.3).
   * Rotación de claves AES documentada en `docs/legal/data-processing.md`.

7. **Derechos del titular (ARCO / GDPR):**
   * **Acceso:** exportación de datos en formato JSON vía `GET /account/export`.
   * **Rectificación:** edición de perfil y re-upload de biomarcadores.
   * **Cancelación:** `DELETE /biosync/data` + `DELETE /account` (pendiente implementar).
   * **Oposición:** opt-out de contribución a Open Food Facts.
   * SLA de respuesta: 20 días hábiles (LFPDPPP) / 30 días (GDPR).

8. **Transferencias internacionales:**
   * Datos procesados en servidores de Google (US) y hosting (US/EU).
   * Cláusulas contractuales tipo (SCC) aplicables cuando corresponda.

9. **Menores de edad:**
   * Servicio **no destinado a menores de 18 años**. Registro bloqueado por declaración de edad.

10. **Cambios a la política:** notificación por email 30 días antes de entrada en vigor.

11. **Contacto del encargado de datos:** email + dirección postal.

### 9.4 Términos de Uso — contenido requerido

1. **Disclaimer médico (cláusula crítica, destacada):**
   > "BioShield es una herramienta informativa. Los hallazgos del Semáforo y los cruces con biomarcadores **no constituyen consejo médico, diagnóstico ni tratamiento**. Consulta siempre a un profesional de salud certificado antes de tomar decisiones basadas en esta información."
   >
   > Esta cláusula es consistente con el prompt del Agente Conciliador (§3B) que instruye al modelo a redactar como hallazgos de literatura científica.

2. **Objeto del servicio:** descripción del análisis de etiquetas, escaneo de barcode/foto y cruce con biomarcadores.

3. **Cuenta de usuario:**
   * Requisitos de registro (edad, email válido).
   * Responsabilidad del usuario sobre la custodia de credenciales.
   * Causales de suspensión/terminación.

4. **Licencia y propiedad intelectual:**
   * **Software:** MIT License (código del repositorio).
   * **Datos propietarios de OFF:** ODbL.
   * **Servicio hosteado:** la licencia MIT no aplica al SaaS; BioShield retiene derechos sobre marca, UX y agregados anonimizados.

5. **Contenido de usuario (fotos de etiquetas):**
   * El usuario retiene la propiedad.
   * Otorga licencia no exclusiva a BioShield para procesarlas.
   * **Contribución a Open Food Facts bajo ODbL requiere opt-in explícito** (no por defecto).

6. **Prohibiciones:**
   * Scraping o uso automatizado fuera de rate limits oficiales.
   * Reverse-engineering del grafo LangGraph o los prompts.
   * Uso comercial sin licencia (revender análisis, integrar en productos de terceros sin acuerdo).
   * Subir datos de salud de terceros sin su consentimiento.

7. **Limitación de responsabilidad:**
   * BioShield no se hace responsable por decisiones médicas, nutricionales o de compra basadas en sus resultados.
   * Tope de responsabilidad: monto pagado por el usuario en los 12 meses previos (USD $0 en Fase 1 MVP gratuito).
   * Exclusión de daños indirectos, lucro cesante y daño moral en la máxima medida permitida.

8. **Disponibilidad del servicio:** sin SLA formal durante MVP; mantenimiento programado con aviso.

9. **Modificaciones al servicio:** derecho a pausar, modificar o discontinuar features con aviso razonable.

10. **Resolución de disputas:**
    * Negociación de buena fe como primer paso.
    * Ley aplicable: **México (CDMX)** por defecto Fase 1.
    * Jurisdicción: tribunales competentes de la Ciudad de México.

11. **Cláusulas finales:** divisibilidad, cesión, notificaciones, integridad del acuerdo.

### 9.5 Requisitos de UI/UX derivados

* **Registro:** checkbox obligatorio de aceptación de Privacidad y T&C, separado del checkbox de consentimiento para datos de salud.
* **Upload de biomarcadores:** recordatorio del disclaimer médico y la retención de 180 días antes del submit.
* **Footer global:** links persistentes a `/privacy`, `/terms`, contacto ARCO.
* **Banner de cambios:** al actualizar documentos, banner bloqueante hasta re-aceptación.

### 9.6 Flujo de contribución a Open Food Facts

El flujo contributivo asíncrono mencionado en §2.2 **requiere consentimiento explícito por escaneo** (no consentimiento global). UI debe mostrar toggle "Contribuir esta foto a Open Food Facts (ODbL)" en el modo foto, desactivado por defecto.

### 9.7 Plan de ejecución

1. Redactar drafts iniciales de ambos documentos en `docs/legal/`.
2. Revisión legal por abogado especialista en protección de datos (México).
3. Implementar endpoints de derechos ARCO (`GET /account/export`, `DELETE /account`).
4. Implementar checkboxes y flujos de consentimiento en frontend.
5. Publicar rutas `/privacy` y `/terms` con versionado en el pie de página.
6. Registrar aviso de privacidad ante INAI si la escala lo requiere (evaluar en Fase 2).