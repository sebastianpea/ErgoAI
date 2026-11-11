# Jabil Inc. - Manual de Identidad Visual y Guía de Estilo Web

Este documento especifica los lineamientos formales de diseño, paleta de colores, tipografía, uso de logotipo y componentes de interfaz gráfica (UI) para la marca **Jabil** (versión adaptada para canales corporativos y sitio web `www.jabil.mx`).

---

## 1. Misión, Visión y Esencia de Marca

* **Propósito:** Ser el proveedor de soluciones de manufactura más avanzado tecnológicamente y de mayor confianza en el mundo.
* **Tono de Voz:** Profesional, tecnológico, preciso, innovador y orientado a la sostenibilidad e ingeniería humana.
* **Valores Visuales:** Limpieza, tecnología de precisión, estructura modular y claridad en la comunicación.

---

## 2. El Logotipo Corporativo

### 2.1. Estructura y Composición
El logotipo de Jabil es una marca denominativa (*wordmark*) que comunica solidez, innovación tecnológica y precisión.

* **Tipografía del Logo:** Tipografía sans-serif personalizada con ángulos rectos y cortes limpios.
* **Proporciones:** Proporción fija e inalterable entre caracteres.

### 2.2. Variaciones del Logo
1. **Versión Principal (Fondo Claro):**
   * **Color de letras:** *Jabil Navy Blue* (`#002B49`).
   * **Uso:** Sitios web con fondos blancos, papelería institucional, documentos impresos oficiales.
2. **Versión Negativo / Inversa (Fondo Oscuro):**
   * **Color de letras:** Blanco puro (`#FFFFFF`) o combinación con *Jabil Tech Blue* (`#3CB4E5`).
   * **Uso:** Encabezados de sitios web oscuros, banners promocionales y sobre fotografía de alto contraste.
3. **Versión Monocromática (Blanco y Negro):**
   * **Color de letras:** Negro sólido (`#000000`) o Blanco sólido (`#FFFFFF`).
   * **Uso:** Sistemas de impresión donde no se permiten colores directos (ej. grabado en piezas, serigrafía técnica).

### 2.3. Área de Respeto (Clear Space) y Tamaño Mínimo
* **Área de Respeto:** La zona de exclusión libre de texto u otros elementos visuales equivale al alto de la **"J"** del logotipo alrededor de sus 4 lados.
* **Tamaño Mínimo Web:** 100 px de ancho.
* **Tamaño Mínimo Impreso:** 20 mm de ancho.

### 2.4. Usos Prohibidos del Logo
* ❌ No deformar, estirar ni escalar asimétricamente el logotipo.
* ❌ No cambiar los colores corporativos por otros no autorizados.
* ❌ No agregar efectos de sombra paralela (*drop shadows*), relieves o resplandores.
* ❌ No colocar el logotipo sobre fondos saturados o fotografías con poco contraste.
* ❌ No alterar la tipografía individual ni mover las letras.

---

## 3. Paleta de Colores Oficiales

### 3.1. Colores Primarios Corporativos

| Nombre del Color | Código HEX | RGB | Pantone / CMYK | Uso Principal |
| :--- | :--- | :--- | :--- | :--- |
| **Jabil Navy Blue** | `#002B49` | `rgb(0, 43, 73)` | PMS 534 C / C100 M80 Y30 K35 | Encabezados, tipografía principal, footers y barra de navegación. |
| **Jabil Tech Blue** | `#3CB4E5` | `rgb(60, 180, 229)` | PMS 298 C / C68 M3 Y0 K0 | Acentos interactivos, hover de enlaces, iconos y elementos destacados. |

### 3.2. Colores Secundarios y de Soporte

| Nombre del Color | Código HEX | RGB | Uso Principal |
| :--- | :--- | :--- | :--- |
| **Slate Dark Grey** | `#1A1A1A` | `rgb(26, 26, 26)` | Texto de cuerpo web de alto contraste. |
| **Medium Grey** | `#6C757D` | `rgb(108, 117, 125)` | Subtítulos, fechas, metadatos y bordes secundarios. |
| **Light Grey Background** | `#F4F6F8` | `rgb(244, 246, 248)` | Fondos de secciones, tarjetas (*cards*) y bloques de código. |
| **Pure White** | `#FFFFFF` | `rgb(255, 255, 255)` | Fondo general del sitio web y texto sobre fondo azul. |
| **Accent Green (Sostenibilidad)** | `#008A5E` | `rgb(0, 138, 94)` | Gráficos de ESG, métricas de impacto ambiental y certificaciones. |

---

## 4. Sistema Tipográfico (Typography System)

### 4.1. Familias Tipográficas
* **Fuente Primaria Digital / Web:** **Roboto** (Google Fonts).
  * *Alternativas en Fallback:* `Arial`, `Helvetica`, `sans-serif`.
* **Fuente Corporativa Editorial / Papelería:** **Helvetica Neue** u **Open Sans**.

### 4.2. Escala Jerárquica Web (CSS Specification)

* **Heading 1 (H1):**
  * *Weight:* Bold (700)
  * *Size:* 40px / 2.5rem
  * *Line-height:* 1.2
  * *Color:* `#002B49`
* **Heading 2 (H2):**
  * *Weight:* Medium / SemiBold (600)
  * *Size:* 32px / 2rem
  * *Line-height:* 1.3
  * *Color:* `#002B49`
* **Heading 3 (H3):**
  * *Weight:* Medium (500)
  * *Size:* 24px / 1.5rem
  * *Line-height:* 1.4
  * *Color:* `#002B49`
* **Body Text (Texto Párrafo):**
  * *Weight:* Regular (400)
  * *Size:* 16px / 1rem
  * *Line-height:* 1.6
  * *Color:* `#1A1A1A`
* **Small / Captions:**
  * *Weight:* Light (300) o Regular (400)
  * *Size:* 14px / 0.875rem
  * *Color:* `#6C757D`

---

## 5. Diseño de Interfaz de Usuario (UI) y Componentes Web

### 5.1. Estructura de Maquetación
* **Grid System:** Contenedor fluido basado en 12 columnas con ancho máximo recomendado de `1200px` a `1440px`.
* **Espaciado (*Spacing*):** Sistema basado en múltiplos de 8px (`8px`, `16px`, `24px`, `32px`, `48px`, `64px`).

### 5.2. Botones y Elementos Interactivos
* **Botón Primario:**
  * *Fondo:* `#002B49`
  * *Texto:* `#FFFFFF` (Font weight 600)
  * *Border Radius:* `4px`
  * *Padding:* `12px 24px`
  * *Hover State:* Fondo cambia a `#3CB4E5` o se oscurece a `#001A2C`.
* **Botón Secundario (Outlined / Ghost):**
  * *Fondo:* Transparente
  * *Borde:* `2px solid #002B49`
  * *Texto:* `#002B49`
  * *Hover State:* Fondo `#002B49` y texto `#FFFFFF`.

### 5.3. Tarjetas y Módulos de Información (*Cards*)
* **Fondo:** `#FFFFFF` sobre contenedor `#F4F6F8`.
* **Sombra (*Box Shadow*):** Normal suave `0px 4px 12px rgba(0, 0, 0, 0.05)` y Hover `0px 8px 24px rgba(0, 0, 0, 0.12)`.
* **Borde:** `1px solid #E2E8F0` con esquinas redondeadas suavemente (`6px` a `8px`).

---

## 6. Fotografía y Estilo Gráfico

### 6.1. Estilo Fotográfico
* **Temática:** Plantas de manufactura de alta tecnología, salas limpias (*cleanrooms*), robótica, diseño electrónico, ingenieros trabajando y liderazgo colaborativo.
* **Iluminación:** Luz natural o blanca de laboratorio, clara y brillante. Evitar tonos oscuros, dramáticos o excesivamente saturados.
* **Composición:** Ángulos limpios, enfoque en la precisión, personas reales en entornos de trabajo seguros (usando equipo de protección personal / EPP si aplica).

### 6.2. Iconografía
* **Estilo:** Iconos vectoriales de trazo lineal (*stroke outline*).
* **Grosor de línea:** 1.5px a 2px.
* **Color de iconos:** `#002B49` o `#3CB4E5`.
* **Fondo de icono:** Círculos o rectángulos opcionales con opacidad baja en azul (`rgba(60, 180, 229, 0.1)`).