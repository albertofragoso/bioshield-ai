# Política de Privacidad

Última actualización: mayo 2026

En BioShield AI nos comprometemos a proteger tu información personal. Esta política describe qué datos recopilamos, cómo los usamos y cuáles son tus derechos.

## 1. Datos que recopilamos

- **Cuenta:** Tu dirección de email y contraseña (almacenada como hash bcrypt, nunca en texto plano).
- **Fotos de etiquetas:** Imágenes que subes para analizar ingredientes. Son procesadas por Google Gemini Vision y no se almacenan de forma permanente.
- **Datos de biomarcadores:** Los valores numéricos de tus análisis de sangre. Se encriptan con AES-256-GCM antes de guardarse y expiran automáticamente a los 180 días.

## 2. Cómo usamos tus datos

Utilizamos tus datos exclusivamente para ofrecerte el análisis nutricional personalizado dentro de la aplicación. No vendemos ni cedemos tu información a terceros con fines comerciales.

## 3. Terceros que procesan tus datos

- **Google Gemini API:** Analiza las imágenes de etiquetas y el texto de ingredientes que subes.
  **Importante:** Tus datos de biomarcadores NUNCA se envían a Gemini ni a ningún servicio de IA externo. Solo se procesan en nuestros servidores y se almacenan cifrados.
- **Open Food Facts:** Base de datos pública de productos alimenticios. Solo accedemos a ella cuando tú activas voluntariamente la opción de contribuir con ingredientes.

## 4. Retención y eliminación

- **Biomarcadores:** Se eliminan automáticamente 180 días después de subirlos.
- **Cuenta:** Para eliminar tu cuenta y todos tus datos, escríbenos a legal@bioshield.ai y lo procesaremos en un plazo de 30 días.

## 5. Seguridad

- Los datos médicos se encriptan en reposo usando AES-256-GCM.
- El acceso requiere autenticación JWT con expiración automática.
- Las contraseñas se almacenan como hashes bcrypt, nunca en texto plano.

## 6. Contacto

Para preguntas sobre esta política o para ejercer tus derechos, escríbenos a:

**legal@bioshield.ai**
