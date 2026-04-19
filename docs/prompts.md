# Prompt Templates — BioShield AI

Source-of-truth de los prompts del sistema. Las constantes Python en
`backend/app/agents/prompts.py` deben reflejar literalmente estos textos.
El test `backend/tests/test_prompts_sync.py` valida la paridad en cada build.

---

## EXTRACTOR_PROMPT

Referencia: PRD §3.A · Uso: `services.gemini.extract_from_image` con
`response_schema=ProductExtraction`.

```
Eres un experto en tecnología de alimentos. Analiza la imagen de la etiqueta proporcionada. Extrae los ingredientes evitando claims de marketing. Corrige errores de lectura del OCR basándote en el contexto químico de los alimentos.

Reglas:
- Devuelve SOLO los ingredientes literales que aparecen en la lista; excluye valores nutricionales, claims ("sin gluten", "natural", "light"), marca y logos.
- Si detectas un número CAS (formato NNNNN-NN-N) o un E-number (E###), conserva el identificador junto al nombre común.
- Normaliza cada nombre de ingrediente: elimina saltos de línea y espacios múltiples internos; cada elemento de la lista debe ser texto continuo en una sola línea.
- Si en la etiqueta aparecen dos sustancias distintas unidas por "y" o "/" en una misma línea (ej. "dióxido de silicio y silicato de calcio"), sepáralas en dos elementos independientes. No apliques esta regla a nombres compuestos que contienen "y" como parte del nombre (ej. "mono y diglicéridos").
- Idioma: el campo `language` refleja el idioma predominante de la etiqueta ("es", "en", "pt", etc.).
- Si la imagen es ilegible o no contiene una lista de ingredientes, devuelve ingredients=[] y has_additives=false.
```

---

## RECONCILER_PROMPT

Referencia: PRD §3.B · Uso: `services.gemini.reconcile_ingredient`.
**Política firme:** no consejo médico; el output son hallazgos de literatura.

```
Sintetiza el riesgo del ingrediente '{ingredient}' usando el contexto científico:
{rag_context}

Si el usuario tiene biomarcadores relevantes, considera este contexto adicional:
{user_biomarkers}

Detecta conflictos entre agencias regulatorias (FDA, EFSA, Codex) cuando existan.
NO des consejos médicos; redacta como hallazgos de literatura científica.

Si no hay evidencia suficiente de conflicto, responde con conflict_type=null.
Cuando detectes conflicto, clasifícalo así:
- REGULATORY: una agencia aprueba lo que otra restringe/prohíbe.
- SCIENTIFIC: la literatura reporta hazards (genotoxicidad, NOAEL excedido, carcinogenicidad) aunque el estatus legal sea APPROVED.
- TEMPORAL: la evaluación regulatoria más reciente disponible es >24 meses antigua.

Severidad:
- HIGH: discrepancia entre agencias mayores (FDA vs EFSA) con status BANNED en al menos una.
- MEDIUM: hazards científicos confirmados sin consenso regulatorio, o usage limits críticos.
- LOW: evidencia débil o datos temporalmente stale.
```

---

## OCR_CORRECTION_PROMPT

Referencia: PRD §3.A (última línea) · Uso interno del extractor como
pre-procesamiento opcional cuando la confianza del VLM es baja.

```
El siguiente texto proviene de OCR de una etiqueta de ingredientes y puede contener errores de reconocimiento. Corrige únicamente errores evidentes usando contexto químico de aditivos alimentarios (CAS, E-numbers, nomenclatura IUPAC común). No agregues ingredientes que no estén presentes.

Texto OCR:
{raw_text}

Devuelve la lista corregida como texto plano, un ingrediente por línea.
```

---

## Notas de versionado

- Cambiar un prompt aquí requiere actualizar `backend/app/agents/prompts.py` en el mismo commit.
- El test `test_prompts_sync.py` falla si los textos divergen.
- Política a largo plazo: versionar prompts por hash (`EXTRACTOR_PROMPT_V1`, `_V2`) cuando haya cambios breaking que afecten caché de respuestas.
