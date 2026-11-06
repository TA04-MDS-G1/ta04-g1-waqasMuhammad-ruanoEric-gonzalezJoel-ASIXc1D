'''
TA04 - ASIXc1

Integrantes:
- Joel González 
- Eric Ruiz
- Muhammad Waqas

Descripción:
Este script automatiza el llenado y envío de formularios de Google Forms.

Analiza la estructura del formulario, genera respuestas aleatorias pero
COHERENTES entre sí (un mismo "contexto" por envío: persona, equipo, tipo de
incidencia, etc.) utilizando la biblioteca Faker, y envía las respuestas.

Uso:
1. Instalar las dependencias necesarias:
   pip install requests faker 
2. Ejecutar el script:
   python bot.py   

'''

import re
import json
import time
import random
import unicodedata
import requests
from faker import Faker

fake = Faker('es_ES')


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def norm(texto):
    """Minúsculas y sin tildes, para comparar textos sin problemas."""
    t = unicodedata.normalize("NFD", str(texto).lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


# ---------------------------------------------------------------------------
# Datos para generar incidencias IT coherentes
# ---------------------------------------------------------------------------

DEPARTAMENTOS = [
    "Administración", "Recursos Humanos", "Informática",
    "Contabilidad", "Comercial", "Logística", "Marketing",
]

SISTEMAS = ["Windows 10 Pro", "Windows 11 Pro", "Ubuntu 22.04", "Windows 10 Home"]

# tipo -> (prioridad habitual, [(asunto, descripción), ...])
INCIDENCIAS = {
    "Hardware": ("Media", [
        ("El equipo no enciende",
         "Al pulsar el botón de encendido no da señal de vídeo y se oyen pitidos."),
        ("Pantalla sin imagen",
         "El monitor se queda en negro tras iniciar el equipo, el LED parpadea."),
        ("Teclado no responde",
         "Algunas teclas dejan de funcionar de forma intermitente."),
    ]),
    "Red": ("Alta", [
        ("Sin conexión a internet",
         "El equipo no obtiene IP y no puede acceder a la red corporativa."),
        ("Red muy lenta",
         "La navegación y el acceso a carpetas compartidas van extremadamente lentos."),
        ("No accede al servidor de archivos",
         "Al abrir la unidad de red aparece error de ruta no encontrada."),
    ]),
    "Software": ("Media", [
        ("Aplicación se cierra sola",
         "El programa se cierra inesperadamente al abrir ciertos archivos."),
        ("Error al actualizar Windows",
         "La actualización falla con el error 0x80070002 y se revierte."),
        ("Necesito instalar un programa",
         "Solicito la instalación de software para tareas del departamento."),
    ]),
    "Impresora": ("Baja", [
        ("La impresora no imprime",
         "Los trabajos se quedan en cola y no salen por la impresora."),
        ("Atasco de papel",
         "La impresora indica atasco aunque no se ve papel atascado."),
    ]),
    "Cuenta / Acceso": ("Alta", [
        ("No puedo iniciar sesión",
         "El usuario aparece bloqueado tras varios intentos fallidos."),
        ("Restablecer contraseña",
         "He olvidado la contraseña del dominio y necesito restablecerla."),
    ]),
}


def generar_contexto():
    """Crea un 'contexto' coherente que se reutiliza en todas las respuestas
    de un mismo envío (misma persona, mismo equipo, misma incidencia...)."""
    nombre, apellido = fake.first_name(), fake.last_name()
    tipo = random.choice(list(INCIDENCIAS))
    prioridad, casos = INCIDENCIAS[tipo]
    asunto, descripcion = random.choice(casos)
    usuario = f"{norm(nombre)}.{norm(apellido)}".replace(" ", "")

    return {
        "nombre": f"{nombre} {apellido}",
        "usuario": usuario,
        "email": f"{usuario}@empresa.local",
        "departamento": random.choice(DEPARTAMENTOS),
        "pc": f"PC-{random.randint(1, 300):03d}",
        "ip": f"192.168.{random.randint(1, 20)}.{random.randint(2, 254)}",
        "so": random.choice(SISTEMAS),
        "tipo": tipo,
        "prioridad": prioridad,
        "asunto": asunto,
        "descripcion": descripcion,
    }


# ---------------------------------------------------------------------------
# Reglas: palabra clave en la pregunta -> valor del contexto
# Orden: de MÁS específica a MÁS genérica (la primera que coincida gana).
# ---------------------------------------------------------------------------

REGLAS = [
    (["id del", "id equipo", "equipo", "ordenador", "pc", "hostname", "etiqueta"],
        lambda c: c["pc"]),
    (["ip", "direccion ip"],
        lambda c: c["ip"]),
    (["sistema operativo", "so "],
        lambda c: c["so"]),
    (["correo", "email", "mail"],
        lambda c: c["email"]),
    (["usuario", "login"],
        lambda c: c["usuario"]),
    (["telefono", "tlf", "movil", "extension"],
        lambda c: fake.phone_number()),
    (["departamento", "empresa", "seccion", "area"],
        lambda c: c["departamento"]),
    (["fecha", "dia"],
        lambda c: str(fake.date_this_year())),
    (["hora"],
        lambda c: fake.time(pattern="%H:%M")),
    (["asunto", "titulo", "resumen"],
        lambda c: c["asunto"]),
    (["descripcion", "detalle", "problema", "incidencia", "comentario", "observacion"],
        lambda c: c["descripcion"]),
    (["nombre", "persona", "tecnico", "solicitante", "apellido"],
        lambda c: c["nombre"]),
]


def elegir_opcion(titulo, opciones, ctx):
    """Para preguntas cerradas: intenta elegir la opción que encaja con el
    contexto; si no hay coincidencia, elige una al azar."""
    t = norm(titulo)

    if "prioridad" in t or "urgencia" in t or "gravedad" in t:
        objetivo = norm(ctx["prioridad"])
    elif "tipo" in t or "categoria" in t:
        objetivo = norm(ctx["tipo"])
    elif "departamento" in t or "seccion" in t:
        objetivo = norm(ctx["departamento"])
    elif "sistema" in t:
        objetivo = norm(ctx["so"])
    else:
        objetivo = None

    if objetivo:
        for o in opciones:
            if objetivo in norm(o) or norm(o) in objetivo:
                return o

    return random.choice(opciones)


def generar_valor_faker(titulo_pregunta, opciones, ctx):
    if opciones:
        return elegir_opcion(titulo_pregunta, opciones, ctx)

    t = " " + norm(titulo_pregunta) + " "
    for claves, funcion in REGLAS:
        if any(f" {k}" in t for k in claves):
            return funcion(ctx)

    # Si no reconoce la pregunta, una frase relacionada con la incidencia
    return ctx["descripcion"]


# ---------------------------------------------------------------------------
# Lectura del formulario y envío
# ---------------------------------------------------------------------------

def obtener_estructura_formulario(url_form):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url_form, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Error al acceder al formulario: HTTP {response.status_code}")

    match = re.search(r'FB_PUBLIC_LOAD_DATA_\s*=\s*(.*?);</script>', response.text, re.DOTALL)
    if not match:
        raise Exception("No se pudo extraer la estructura del Google Form.")

    data = json.loads(match.group(1))
    preguntas_raw = data[1][1]

    estructura = []
    for p in preguntas_raw:
        if p is None or len(p) < 5 or not p[4]:
            continue

        titulo_pregunta = p[1]
        entry_id = f"entry.{p[4][0][0]}"

        # Extraer opciones de preguntas cerradas (desplegable, tipo test)
        opciones = []
        if len(p[4][0]) > 1 and p[4][0][1]:
            opciones = [opt[0] for opt in p[4][0][1]]

        estructura.append({
            "id": entry_id,
            "titulo": titulo_pregunta,
            "opciones": opciones
        })

    return estructura


def autocompletar_y_enviar(url_form, total_envios=1):
    url_post = re.sub(r'/viewform.*', '/formResponse', url_form)
    if '/formResponse' not in url_post:
        url_post = url_form.rstrip('/') + '/formResponse'

    # 1. Analizar la estructura una sola vez
    print("Obteniendo la estructura del formulario...")
    preguntas = obtener_estructura_formulario(url_form)

    exitosos = 0
    fallidos = 0

    # 2. Bucle para realizar la cantidad de envíos solicitada
    for i in range(1, total_envios + 1):
        print(f"\n--- Preparando envío {i} de {total_envios} ---")

        # Un contexto nuevo por envío: todas las respuestas son coherentes entre sí
        ctx = generar_contexto()

        payload = {}
        for p in preguntas:
            valor = generar_valor_faker(p["titulo"], p["opciones"], ctx)
            payload[p["id"]] = valor
            print(f"[{p['id']}] {p['titulo']} -> {valor}")

        response = requests.post(url_post, data=payload)

        if response.status_code == 200:
            exitosos += 1
            print(f" Respuesta {i} enviada correctamente.")
        else:
            fallidos += 1
            print(f" Error al enviar respuesta {i}. HTTP Status: {response.status_code}")

        # Pausa aleatoria entre 1 y 3 segundos entre envíos
        if i < total_envios:
            pausa = random.uniform(1.0, 3.0)
            print(f"Esperando {pausa:.1f} segundos antes del siguiente envío...")
            time.sleep(pausa)

    print(f"\n==========================================")
    print(f"Resumen: {exitosos} enviados con éxito, {fallidos} fallidos.")
    print(f"==========================================")


if __name__ == "__main__":
    URL_FORMULARIO = "https://docs.google.com/forms/d/e/1FAIpQLScjsOc83IFf_b-iMMMTpMtPmvBxBe1F6If-_LKqL8efzMb-zA/viewform?usp=header"

    # Preguntar al usuario por consola cuántos envíos hacer
    try:
        num = int(input("¿Cuántos formularios quieres enviar?: "))
    except ValueError:
        print("Entrada no válida, se enviará 1 por defecto.")
        num = 1

    autocompletar_y_enviar(URL_FORMULARIO, total_envios=num)