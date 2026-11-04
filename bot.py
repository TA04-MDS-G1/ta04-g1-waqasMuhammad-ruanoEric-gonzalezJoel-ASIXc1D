'''
TA04 - ASIXc1

Integrantes:
- Joel González 
- Eric Ruiz
- Muhammad Waqas

Descripción:
Este script automatiza el llenado y envío de formularios de Google Forms.

Automáticamente analiza la estructura del formulario, genera respuestas aleatorias utilizando la biblioteca Faker y envía las respuestas al formulario.

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
import requests
from faker import Faker
 
fake = Faker('es_ES')

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

def generar_valor_faker(titulo_pregunta, opciones):
    if opciones:
        return random.choice(opciones)
    
    t = titulo_pregunta.lower()
    
    if any(k in t for k in ["nombre", "usuario", "técnico", "persona"]):
        return fake.name()
    elif any(k in t for k in ["correo", "email", "mail"]):
        return fake.company_email()
    elif any(k in t for k in ["empresa", "departamento", "sección"]):
        return fake.company()
    elif any(k in t for k in ["teléfono", "tlf", "móvil"]):
        return fake.phone_number()
    elif any(k in t for k in ["fecha", "día"]):
        return str(fake.date_this_year())
    elif any(k in t for k in ["asunto", "título", "resumen"]):
        return fake.sentence(nb_words=5)
    else:
        return fake.paragraph(nb_sentences=2)

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
        payload = {}
        for p in preguntas:
            valor = generar_valor_faker(p["titulo"], p["opciones"])
            payload[p["id"]] = valor
            print(f"[{p['id']}] {p['titulo']} -> {valor}")

        response = requests.post(url_post, data=payload)
        
        if response.status_code == 200:
            exitosos += 1
            print(f" Respuesta {i} enviada correctamente.")
        else:
            fallidos += 1
            print(f" Error al enviar respuesta {i}. HTTP Status: {response.status_code}")

        # Pausa aleatoria entre 1 y 3 segundos entre envíos (para simular tráfico natural)
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