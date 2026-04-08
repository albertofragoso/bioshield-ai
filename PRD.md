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

* **Fase 1 (MVP):** Extracción estructurada (Ingredientes/Bio-Sync), LangGraph funcional, Semáforo visual en Next.js y caché por Barcode.
* **Fase 2 (Retail Integration):** Conexión con APIs de supermercados (Walmart/Cornershop) para análisis preventivo y caché geográfico.
* **Fase 3 (Reality Engineering):** RAG Multidimensional con ingesta de sabiduría ancestral y agente de conciliación holístico.

---

## 7. El Semáforo Visual (Output Next.js)

* **Gris:** Error de lectura/Datos insuficientes.
* **Azul:** Ingredientes limpios.
* **Amarillo:** Aditivos bajo observación (EWG/EFSA).
* **Naranja:** Conflicto detectado con biomarcadores del usuario (Bio-Sync).
* **Rojo:** Toxicidad confirmada o ingrediente prohibido.