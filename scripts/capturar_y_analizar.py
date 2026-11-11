"""
Herramienta de Captura y Análisis Ergonómico en Tiempo Real (Webcam / Cámara).
Compatible al 100% con Windows y Linux.

Uso interactivo (con ventana de cámara):
    python scripts/capturar_y_analizar.py

Uso con temporizador de 3 segundos (ideal para auto-evaluación):
    python scripts/capturar_y_analizar.py --timer 3

Uso en servidor sin monitor (headless):
    python scripts/capturar_y_analizar.py --headless --timer 2 --output captura_reba.jpg

Uso sobre una imagen existente:
    python scripts/capturar_y_analizar.py --image ruta/foto.jpg
"""

from __future__ import annotations

import argparse
import os
import platform
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.app.core_ergonomics.angle_geometry import extraer_angulos_laterales
from backend.app.core_ergonomics.modelos import ContextoTarea
from backend.app.core_ergonomics.reba_calculator import RebaCalculator
from backend.app.session_store.config_loader import NormativeConfigLoader
from backend.app.settings import CONFIG_DIR, WORKSPACE_DIR
from backend.app.vision.annotador import anotar_esqueleto
from backend.app.vision.estimador import estimador
from backend.app.vision.privacidad import proteger_imagen


def abrir_camara(indice: int = 0, ancho: int = 1280, alto: int = 720) -> cv2.VideoCapture:
    """
    Abre la cámara web utilizando el backend nativo óptimo según el sistema operativo:
    - En Windows: DirectShow (CAP_DSHOW) para evitar el retardo de 5-10s de inicio.
    - En Linux: Video4Linux2 (CAP_V4L2) para rendimiento óptimo con uvcvideo.
    """
    sistema = platform.system()
    cap = None

    if sistema == "Windows":
        cap = cv2.VideoCapture(indice, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(indice, cv2.CAP_MSMF)
    elif sistema == "Linux":
        cap = cv2.VideoCapture(indice, cv2.CAP_V4L2)

    if cap is None or not cap.isOpened():
        cap = cv2.VideoCapture(indice)

    if not cap.isOpened():
        raise RuntimeError(
            f"No se pudo abrir la cámara en el índice {indice}. "
            "Verifica que el dispositivo esté conectado y no esté en uso por otra aplicación."
        )

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, ancho)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, alto)
    return cap


def analizar_fotografia(
    img_bgr: np.ndarray,
    tipo_tarea: str = "levantamiento",
    carga_kg: float = 0.0,
) -> Tuple[np.ndarray, dict]:
    """
    Ejecuta el pipeline de visión y cálculo REBA sobre un cuadro BGR.
    Devuelve la imagen anotada y el diccionario con los resultados del análisis.
    Sin persona detectada, devuelve una imagen completamente cubierta por privacidad.
    """
    resultado_pose = estimador.analizar(img_bgr)
    if resultado_pose.personas == 0:
        return proteger_imagen(img_bgr, []), {
            "ok": False,
            "error": "No se detectó ninguna persona en la imagen con suficiente claridad.",
        }

    angulos_medidos = extraer_angulos_laterales(resultado_pose.puntos)
    grados_map = {seg: m.grados for seg, m in angulos_medidos.items()}

    # Calcular REBA determinista
    loader = NormativeConfigLoader(CONFIG_DIR)
    calc = RebaCalculator(loader.get_reba_tables())
    ctx = ContextoTarea(carga_kg=carga_kg)
    reba = calc.calcular(grados_map, ctx)

    # Anotar imagen
    img_anotada = anotar_esqueleto(
        resultado_pose.imagen_bgr,
        resultado_pose.puntos,
        reba_final=reba.final,
        reba_nivel=reba.nivel,
        angulos=grados_map,
    )

    detalles = {
        "ok": True,
        "personas": resultado_pose.personas,
        "rostro_anonimizado": resultado_pose.rostro_anonimizado,
        "reba_final": reba.final,
        "reba_nivel": reba.nivel,
        "grupo_a": reba.grupo_a,
        "grupo_b": reba.grupo_b,
        "tabla_c": reba.tabla_c,
        "angulos": {
            seg: {
                "grados": round(m.grados, 1) if m.grados is not None else None,
                "confianza": m.confianza,
                "puntaje_reba": reba.segmentos[seg].puntaje if seg in reba.segmentos else 1,
            }
            for seg, m in angulos_medidos.items()
        },
    }
    return img_anotada, detalles


def dibujar_guias_postura(frame: np.ndarray, cuenta_regresiva: Optional[int] = None) -> np.ndarray:
    """Dibuja guías visuales sobre el cuadro de video para ayudar al operario a encuadrarse."""
    h, w = frame.shape[:2]
    vis = frame.copy()

    # Guía vertical central y retícula suave
    color_guia = (180, 180, 180)
    cv2.line(vis, (w // 2, 0), (w // 2, h), color_guia, 1, cv2.LINE_AA)

    # Líneas de referencia (cabeza, torso, pies)
    cv2.line(vis, (w // 4, int(h * 0.15)), (3 * w // 4, int(h * 0.15)), color_guia, 1, cv2.LINE_AA)
    cv2.line(vis, (w // 4, int(h * 0.50)), (3 * w // 4, int(h * 0.50)), color_guia, 1, cv2.LINE_AA)
    cv2.line(vis, (w // 4, int(h * 0.85)), (3 * w // 4, int(h * 0.85)), color_guia, 1, cv2.LINE_AA)

    # Barra inferior con instrucciones
    barra_h = 36
    cv2.rectangle(vis, (0, h - barra_h), (w, h), (15, 35, 55), -1)
    instrucciones = "[ESPACIO] Tomar foto y analizar | [Q / ESC] Salir"
    cv2.putText(vis, instrucciones, (14, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1, cv2.LINE_AA)

    if cuenta_regresiva is not None and cuenta_regresiva > 0:
        cv2.putText(
            vis,
            str(cuenta_regresiva),
            (w // 2 - 40, h // 2 + 40),
            cv2.FONT_HERSHEY_DUPLEX,
            3.5,
            (40, 220, 255),
            4,
            cv2.LINE_AA,
        )

    return vis


def imprimir_resumen_terminal(detalles: dict) -> None:
    print("\n" + "=" * 65)
    print("  RESULTADO DE ANÁLISIS ERGONÓMICO REBA (JABIL / NOM-036)")
    print("=" * 65)
    if not detalles.get("ok"):
        print(f"✗ Error: {detalles.get('error')}")
        return

    print(f"• Puntaje REBA Final: {detalles['reba_final']}  (Nivel: {detalles['reba_nivel'].upper()})")
    print(f"• Puntuación Grupo A (Tronco/Cuello/Piernas): {detalles['grupo_a']}")
    print(f"• Puntuación Grupo B (Brazo/Antebrazo/Muñeca): {detalles['grupo_b']}")
    print(f"• Personas detectadas: {detalles['personas']} (Rostro anonimizado: {detalles['rostro_anonimizado']})")
    print("\nÁngulos articulares calculados:")
    for seg, info in detalles.get("angulos", {}).items():
        gr = f"{info['grados']}°" if info['grados'] is not None else "Sin dato"
        print(f"  - {seg.capitalize():<11}: {gr:<10} | REBA parcial: {info['puntaje_reba']} | Conf: {info['confianza']:.2f}")
    print("=" * 65 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Captura de fotografías con cámara web y análisis ergonómico REBA.")
    parser.add_argument("--camera", type=int, default=0, help="Índice de la cámara (por defecto: 0)")
    parser.add_argument("--width", type=int, default=1280, help="Ancho de captura (por defecto: 1280)")
    parser.add_argument("--height", type=int, default=720, help="Alto de captura (por defecto: 720)")
    parser.add_argument("--timer", type=int, default=0, help="Cuenta regresiva en segundos antes de capturar")
    parser.add_argument("--headless", action="store_true", help="Modo sin interfaz gráfica (para servidores o Docker)")
    parser.add_argument("--image", type=str, default=None, help="Analizar un archivo de imagen existente")
    parser.add_argument("--output", type=str, default=None, help="Ruta donde guardar la imagen analizada")
    parser.add_argument("--carga", type=float, default=0.0, help="Masa manipulada en kg (por defecto: 0.0)")
    parser.add_argument("--tarea", type=str, default="levantamiento", help="Tipo de tarea evaluada")
    args = parser.parse_args()

    carpeta_salida = WORKSPACE_DIR / "capturas_camara"
    carpeta_salida.mkdir(parents=True, exist_ok=True)

    # Modo A: Análisis de archivo existente
    if args.image:
        ruta_img = Path(args.image)
        if not ruta_img.is_file():
            print(f"Error: No existe el archivo {ruta_img}", file=sys.stderr)
            sys.exit(1)
        img = cv2.imread(str(ruta_img))
        if img is None:
            print(f"Error: Formato de imagen no soportado en {ruta_img}", file=sys.stderr)
            sys.exit(1)

        print(f"Analizando imagen: {ruta_img.name}...")
        img_anotada, detalles = analizar_fotografia(img, tipo_tarea=args.tarea, carga_kg=args.carga)
        imprimir_resumen_terminal(detalles)

        salida = Path(args.output) if args.output else carpeta_salida / f"analisis_{ruta_img.stem}.jpg"
        cv2.imwrite(str(salida), img_anotada)
        print(f"✓ Imagen anotada guardada en: {salida}")
        return

    # Modo B: Captura desde cámara web (Windows / Linux)
    print(f"Inicializando cámara {args.camera} en {platform.system()}...")
    cap = abrir_camara(args.camera, args.width, args.height)

    try:
        # Si se especificó temporizador con modo headless
        if args.headless:
            print(f"Modo headless activo. Esperando {args.timer} segundo(s)...")
            time.sleep(max(args.timer, 1))
            ret, frame = cap.read()
            if not ret or frame is None:
                print("Error: No se pudo capturar cuadro de la cámara.", file=sys.stderr)
                sys.exit(1)

            print("Procesando análisis biomecánico...")
            img_anotada, detalles = analizar_fotografia(frame, tipo_tarea=args.tarea, carga_kg=args.carga)
            imprimir_resumen_terminal(detalles)

            nombre_salida = args.output or str(carpeta_salida / f"captura_{int(time.time())}.jpg")
            cv2.imwrite(nombre_salida, img_anotada)
            print(f"✓ Imagen analizada guardada en: {nombre_salida}")
            return

        # Modo Interactivo con ventana OpenCV
        nombre_ventana = "ErgoAI · Camara en Vivo (Presiona ESPACIO para evaluar)"
        cv2.namedWindow(nombre_ventana, cv2.WINDOW_NORMAL)

        print("\nCámara activa. Encuadra al operario de perfil completo.")
        print("Instrucciones: [ESPACIO] = Capturar y analizar | [Q] = Salir\n")

        ultimo_analisis = None
        cuadro_congelado = None

        while True:
            ret, frame = cap.read()
            if not ret:
                print("Error al leer de la cámara.")
                break

            if cuadro_congelado is not None:
                # Mostrar el cuadro analizado
                cv2.imshow(nombre_ventana, cuadro_congelado)
                k = cv2.waitKey(30) & 0xFF
                if k in (ord("q"), ord("Q"), 27):
                    break
                elif k in (ord("r"), ord("R"), ord(" ")):
                    cuadro_congelado = None  # Reanudar cámara en vivo
                continue

            frame_guiado = dibujar_guias_postura(frame)
            cv2.imshow(nombre_ventana, frame_guiado)

            k = cv2.waitKey(15) & 0xFF
            if k in (ord("q"), ord("Q"), 27):
                break
            elif k == ord(" "):
                print("Capturando fotografía y analizando postura...")
                img_anotada, detalles = analizar_fotografia(frame, tipo_tarea=args.tarea, carga_kg=args.carga)
                imprimir_resumen_terminal(detalles)

                ts = int(time.time())
                salida_ruta = carpeta_salida / f"captura_{ts}.jpg"
                cv2.imwrite(str(salida_ruta), img_anotada)
                print(f"✓ Imagen guardada en: {salida_ruta}")

                cuadro_congelado = img_anotada
                ultimo_analisis = detalles

    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
