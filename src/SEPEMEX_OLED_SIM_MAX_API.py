import network
import urequests
import ujson
from machine import Pin, RTC, UART, SPI, SoftI2C
import time
import _thread

# Definición de pines
pin0 = Pin(13, Pin.OUT)  # Verde
pin1 = Pin(27, Pin.OUT)  # Verde parpadeante (destello)
pin2 = Pin(26, Pin.OUT)  # Ámbar
pin3 = Pin(25, Pin.OUT)  # Rojo (si lo necesitas)
pin_des = Pin(32, Pin.OUT)  # Pin adicional
pin_select = Pin(4, Pin.IN)  # Cambiado a entrada

rtc = RTC()  # Configuración del RTC
uart2 = UART(2, baudrate=115200, tx=17, rx=16)  # Configuración del UART

# Variables globales
semaforos = None  # Para almacenar los tiempos actuales de los semáforos
nuevos_tiempos = None  # Para almacenar nuevos tiempos si hay cambios
tiempo_verificacion_minutos = 5  # Cada cuántos minutos verificar los tiempos
verificar_cambios = True  # Bandera para controlar la verificación de tiempos
contador = 0  # Contador para el MAX7219

# Funciones para el SIMCOM (sin cambios)
def _sendcommand(command):
    print(f"'{command}'\r\n")
    uart2.write(f"{command}\r\n")
    time.sleep(3)
    try:
        response = uart2.read()
        if response:
            return response.decode('utf-8')
        else:
            return "Respuesta vacía."
    except Exception as e:
        return e

def _start_simcom():
    print(_sendcommand("AT"))
    print(_sendcommand("AT+CPIN?"))
    # print(_sendcommand("AT+CSQ"))
    print(_sendcommand("AT+CREG?"))
    print(_sendcommand("AT+CPSI?"))

def comprobar_señal_simcom():
    _start_simcom()
    response = _sendcommand("AT+CSQ")
    print("Respuesta AT+CSQ:", response)
    return "OK" in response

def conectar_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect("WIFI_Vinculacion", "V1ncul4c10n23")
    while not wlan.isconnected():
        pass
    print("Conectado a Wi-Fi")

def request_hora():
    hora_request = urequests.get('https://worldtimeapi.org/api/timezone/America/Mexico_City')
    json_data = ujson.loads(hora_request.text)
    fecha_hora = str(json_data["datetime"])
    año = int(fecha_hora[0:4])
    mes = int(fecha_hora[5:7])
    día = int(fecha_hora[8:10])
    hora = int(fecha_hora[11:13])
    minutos = int(fecha_hora[14:16])
    segundos = int(fecha_hora[17:19])
    sub_segundos = int(round(int(fecha_hora[20:26]) / 10000))
    rtc.datetime((año, mes, día, 0, hora, minutos, segundos, sub_segundos))

def obtener_tiempos_semaforo():
    response = urequests.get('http://adminsepemex02-001-site1.gtempurl.com/tiempos/listar?Id_Interseccion=1', auth=('11187974', '60-dayfreetrial'))
    if response.status_code == 200:
        json_data = ujson.loads(response.text)
        print("Datos recibidos:", json_data)  # Para depuración
        return json_data['semaforos']  # Retorna la lista de semáforos
    else:
        print("Error al obtener los tiempos:", response.status_code)
        return None

def controlar_semaforo(verde_efectivo, verde_destello, ambar, estados, semaforo_id):
    duraciones = {
        estados[0]: verde_efectivo,
        estados[1]: verde_destello,
        estados[2]: ambar,
    }
    
    for estado in estados:
        pin_des.value(int(estado[4]))
        pin0.value(int(estado[3]))  # Verde
        pin1.value(int(estado[2]))  # Verde parpadeante
        pin2.value(int(estado[1]))  # Ámbar
        pin3.value(int(estado[0]))  # Rojo (si fuera necesario)

        if estado in duraciones:
            print(f"Estado: {estado}, Duración: {duraciones[estado]} segundos")
            time.sleep(duraciones[estado]) 

def procesar_tiempos(json_data):
    estados_semaforos = [
        ("00010", "00011", "00100"), 
        ("00110", "00111", "01000"), 
        ("01010", "01011", "01100"), 
        ("01110", "01111", "10000") 
    ]
    
    for i, semaforo in enumerate(json_data):
        tiempos = semaforo['tiempos'][0]  
        verde_efectivo = tiempos['fld_TiempoVerdeEfectivo']
        verde_destello = tiempos['fld_TiempoVerdeDestello']
        ambar = tiempos['fld_TiempoAmbar']
        
        print(f"Controlando semáforo ID: {semaforo['id_Semaforo']}")
        controlar_semaforo(verde_efectivo, verde_destello, ambar, estados_semaforos[i], semaforo['id_Semaforo'])

def verificar_tiempos():
    global nuevos_tiempos, verificar_cambios 
   
    while verificar_cambios:
        if pin_select.value() == 1:  # Si pin_select es 1
            time.sleep(tiempo_verificacion_minutos * 60) 
            print("Verificando si hay cambios en los tiempos de los semáforos...")
            nuevos_tiempos = obtener_tiempos_semaforo()  
            if nuevos_tiempos:
                print("Nuevos tiempos obtenidos. Se aplicarán después del ciclo actual.")
            else:
                print("No se pudieron obtener los nuevos tiempos.")
        
def ciclo_indefinido():
    global semaforos, nuevos_tiempos
    
    while True:
        if pin_select.value() == 0:  # Si pin_select es 0
            continue
        
        procesar_tiempos(semaforos)  
        
        if nuevos_tiempos:
            semaforos = nuevos_tiempos  
            nuevos_tiempos = None  
            print("Tiempos actualizados con éxito.") 
        
        time.sleep(1)  

if comprobar_señal_simcom():
    print("Señal SIMCOM detectada. Accediendo a las APIs...")
    
    request_hora()  
   
    semaforos = obtener_tiempos_semaforo()  
   
    if semaforos:  
        _thread.start_new_thread(verificar_tiempos, ())  
        
        ciclo_indefinido()  
else:
    print("No hay señal del módulo SIMCOM. Conectando a Wi-Fi...")
    
conectar_wifi()
request_hora() 

semaforos = obtener_tiempos_semaforo()  

if semaforos:  
   _thread.start_new_thread(verificar_tiempos, ())  
    
   ciclo_indefinido()  
else:
   print("No se pudieron obtener los tiempos de los semáforos.")