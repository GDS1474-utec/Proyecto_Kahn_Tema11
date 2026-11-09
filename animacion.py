import argparse
import copy
import json
import math
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


RAIZ = Path(__file__).resolve().parent
COLORES = {
    "fondo": "#091324",
    "panel": "#12223A",
    "panel2": "#192C47",
    "borde": "#29405F",
    "blanco": "#F1F6FF",
    "gris": "#A6B9D3",
    "suave": "#6E86A5",
    "azul": "#68A9FF",
    "turquesa": "#55E1CE",
    "amarillo": "#FFC86C",
    "rojo": "#FF8094",
    "morado": "#C0A1FF",
    "linea": "#6F87A7",
}


@dataclass
class Estado:
    grados: list = field(default_factory=list)
    cola: list = field(default_factory=list)
    orden: list = field(default_factory=list)
    eliminadas: set = field(default_factory=set)
    tipo: str = "inicio"
    actual: int = -1
    destino: int = -1
    arista: int = -1
    previo: int = -1
    terminado: bool = False
    ciclo: bool = False


@dataclass
class Escena:
    clase: str
    duracion: float
    titulo: str = ""
    subtitulo: str = ""
    detalle: str = ""
    grafo: dict = None
    estado: Estado = None
    anterior: Estado = None
    evento: dict = None
    numero: int = 0
    total: int = 0


def cargar_grafo(ruta):
    with open(ruta, encoding="utf-8") as archivo:
        grafo = json.load(archivo)
    nodos = grafo["nodos"]
    nombres = [n["id"] for n in nodos]
    if not nodos or len(set(nombres)) != len(nombres):
        raise ValueError(f"Vértices vacíos o duplicados en {ruta}")
    indices = {nombre: indice for indice, nombre in enumerate(nombres)}
    aristas = []
    for inicio, fin in grafo["aristas"]:
        if inicio not in indices or fin not in indices:
            raise ValueError(f"Arista con vértice desconocido en {ruta}")
        aristas.append((indices[inicio], indices[fin]))
    grafo["indices"] = indices
    grafo["aristas_idx"] = aristas
    return grafo


def compilar():
    compilador = shutil.which("g++")
    if not compilador:
        raise RuntimeError("No se encontró g++. Instala un compilador C++17 y agrégalo a PATH.")
    destino = RAIZ / "build"
    destino.mkdir(exist_ok=True)
    ejecutable = destino / ("kahn.exe" if sys.platform == "win32" else "kahn")
    fuente = RAIZ / "src" / "kahn.cpp"
    if not ejecutable.exists() or fuente.stat().st_mtime > ejecutable.stat().st_mtime:
        comando = [compilador, "-std=c++17", "-O2", "-Wall", "-Wextra", "-pedantic", str(fuente), "-o", str(ejecutable)]
        subprocess.run(comando, check=True)
    return ejecutable


def obtener_eventos(ejecutable, grafo):
    aristas = grafo["aristas_idx"]
    datos = f"{len(grafo['nodos'])} {len(aristas)}\n"
    datos += "".join(f"{u} {v}\n" for u, v in aristas)
    proceso = subprocess.run([str(ejecutable)], input=datos, text=True, capture_output=True, check=True)
    eventos = [json.loads(linea) for linea in proceso.stdout.splitlines() if linea.strip()]
    if not eventos or eventos[0]["tipo"] != "inicio":
        raise ValueError("La implementación C++ no devolvió eventos válidos.")
    return eventos


def aplicar_evento(estado, evento, grafo):
    estado = copy.deepcopy(estado)
    tipo = evento["tipo"]
    estado.tipo = tipo
    estado.actual = evento.get("u", -1)
    estado.destino = evento.get("v", -1)
    estado.arista = evento.get("arista", -1)
    estado.previo = -1
    estado.terminado = False
    estado.ciclo = False
    n = len(grafo["nodos"])

    if tipo == "inicio":
        calculados = [0] * n
        for _, v in grafo["aristas_idx"]:
            calculados[v] += 1
        if evento["grados"] != calculados:
            raise ValueError("Los grados iniciales no coinciden con el grafo.")
        estado.grados = list(evento["grados"])
    elif tipo == "encolar":
        u = evento["u"]
        if estado.grados[u] != 0 or u in estado.cola or u in estado.orden:
            raise ValueError("Evento de inserción inválido.")
        estado.cola.append(u)
    elif tipo == "extraer":
        u = evento["u"]
        if not estado.cola or estado.cola[0] != u:
            raise ValueError("La extracción no respeta el orden FIFO.")
        estado.cola.pop(0)
        estado.orden.append(u)
    elif tipo == "reducir":
        u, v, indice = evento["u"], evento["v"], evento["arista"]
        if not estado.orden or estado.orden[-1] != u:
            raise ValueError("Se procesó una arista desde un vértice incorrecto.")
        if not 0 <= indice < len(grafo["aristas_idx"]) or grafo["aristas_idx"][indice] != (u, v):
            raise ValueError("La arista procesada no existe.")
        if indice in estado.eliminadas or estado.grados[v] <= 0:
            raise ValueError("Se intentó procesar dos veces una misma arista.")
        estado.previo = estado.grados[v]
        estado.grados[v] -= 1
        estado.eliminadas.add(indice)
        if evento["grado"] != estado.grados[v]:
            raise ValueError("El grado informado por C++ es incorrecto.")
    elif tipo in ("finalizar", "ciclo"):
        estado.terminado = True
        estado.ciclo = tipo == "ciclo"
        if estado.ciclo == (len(estado.orden) == n):
            raise ValueError("El resultado de detección de ciclos es inconsistente.")
        if not estado.ciclo:
            posiciones = {u: i for i, u in enumerate(estado.orden)}
            if len(posiciones) != n or any(posiciones[u] >= posiciones[v] for u, v in grafo["aristas_idx"]):
                raise ValueError("El resultado no es un orden topológico válido.")
    else:
        raise ValueError(f"Tipo de evento desconocido: {tipo}")
    return estado


def descripcion(evento, estado, grafo):
    nombres = [n["id"] for n in grafo["nodos"]]
    tipo = evento["tipo"]
    if tipo == "inicio":
        return "Primero calculamos cuántas aristas entran a cada vértice."
    if tipo == "encolar":
        return f"{nombres[evento['u']]} tiene grado de entrada 0: entra al final de la cola."
    if tipo == "extraer":
        return f"Sacamos {nombres[evento['u']]} del frente y lo agregamos al orden."
    if tipo == "reducir":
        return (f"Procesamos {nombres[evento['u']]} → {nombres[evento['v']]}. "
                f"El grado de {nombres[evento['v']]} baja de {estado.previo} a {evento['grado']}.")
    if tipo == "finalizar":
        secuencia = " → ".join(nombres[u] for u in estado.orden)
        return f"Terminamos: {secuencia}. Todas las dependencias se respetan."
    return "La cola está vacía y quedan vértices pendientes: el grafo contiene un ciclo."


def construir_pasos(ejecutable, grafo):
    eventos = obtener_eventos(ejecutable, grafo)
    pasos = []
    estado = Estado()
    for numero, evento in enumerate(eventos, start=1):
        anterior = copy.deepcopy(estado)
        estado = aplicar_evento(estado, evento, grafo)
        pasos.append((evento, anterior, copy.deepcopy(estado), descripcion(evento, estado, grafo)))
    if eventos[-1]["tipo"] not in ("finalizar", "ciclo"):
        raise ValueError("Falta el evento final del algoritmo.")
    return pasos


def construir_escenas(principal, ciclo, un_vertice):
    escenas = [
        Escena("portada", 6.2),
        Escena("concepto", 6.1, "¿Qué es un orden topológico?", "Un orden de tareas que respeta sus dependencias.", "Si A debe hacerse antes que C, entonces A aparece primero."),
        Escena("concepto", 6.3, "La idea de Kahn", "Comenzar por los vértices que no tienen entradas.", "Usamos una cola FIFO y actualizamos los grados de entrada."),
        Escena("seccion", 3.0, "Demostración", "Ejemplo con 7 vértices y 8 aristas.", "Seguiremos la cola, los grados de entrada y el orden final."),
    ]

    for grafo, grupo in ((principal, "principal"), (ciclo, "ciclo"), (un_vertice, "unico")):
        pasos = grafo["pasos"]
        if grupo == "ciclo":
            escenas.append(Escena("seccion", 3.4, "Caso borde: un ciclo", "A → B → C → D → B", "Si quedan vértices sin procesar, no existe un orden topológico completo."))
        if grupo == "unico":
            escenas.append(Escena("seccion", 2.7, "Caso borde: un vértice", "Sin aristas, el orden es simplemente A.", "La misma implementación funciona sin casos especiales."))
        for numero, (evento, anterior, estado, detalle) in enumerate(pasos, start=1):
            tipo = evento["tipo"]
            if grupo == "principal":
                duracion = {"inicio": 2.3, "encolar": 1.48, "extraer": 1.83,
                            "reducir": 1.73, "finalizar": 3.5, "ciclo": 3.5}[tipo]
            elif grupo == "ciclo":
                duracion = {"inicio": 1.8, "encolar": 1.25, "extraer": 1.35,
                            "reducir": 1.35, "finalizar": 2.5, "ciclo": 3.6}[tipo]
            else:
                duracion = {"inicio": 1.1, "encolar": 1.35, "extraer": 1.5,
                            "reducir": 1.3, "finalizar": 2.6, "ciclo": 2.6}[tipo]
            escenas.append(Escena("paso", duracion, grafo["titulo"], "", detalle,
                                  grafo, estado, anterior, evento, numero, len(pasos)))

    escenas.extend([
        Escena("complejidad", 7.6),
        Escena("creditos", 5.4),
    ])
    return escenas


class Pintor:
    def __init__(self, ancho, alto, configuracion):
        self.ancho = ancho
        self.alto = alto
        self.escala = ancho / 1920
        self.configuracion = configuracion
        self.fuentes = {}
        fuentes = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        ]
        fuertes = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
        ]
        self.ruta_normal = next((r for r in fuentes if Path(r).is_file()), None)
        self.ruta_gruesa = next((r for r in fuertes if Path(r).is_file()), self.ruta_normal)
        self.base = Image.new("RGB", (ancho, alto), COLORES["fondo"])
        pincel = ImageDraw.Draw(self.base)
        for y in range(alto):
            t = y / max(1, alto - 1)
            color = (int(9 + 5 * t), int(19 + 10 * t), int(36 + 14 * t))
            pincel.line([(0, y), (ancho, y)], fill=color)
        for i in range(13):
            x = self.c(100 + 140 * i)
            pincel.line([(x, 0), (x, alto)], fill="#13253C", width=max(1, self.c(1)))

    def c(self, valor):
        return int(round(valor * self.escala))

    def f(self, tamano, fuerte=False):
        tamano = max(9, self.c(tamano))
        clave = (tamano, fuerte)
        if clave not in self.fuentes:
            ruta = self.ruta_gruesa if fuerte else self.ruta_normal
            self.fuentes[clave] = ImageFont.truetype(ruta, tamano) if ruta else ImageFont.load_default()
        return self.fuentes[clave]

    def texto(self, dibujo, x, y, contenido, tamano=26, color=None, fuerte=False, ancla=None):
        dibujo.text((self.c(x), self.c(y)), str(contenido), fill=color or COLORES["blanco"],
                     font=self.f(tamano, fuerte), anchor=ancla)

    def caja(self, dibujo, x, y, w, h, fill="panel", borde=True, radio=23):
        dibujo.rounded_rectangle([self.c(x), self.c(y), self.c(x+w), self.c(y+h)],
                                radius=self.c(radio), fill=COLORES.get(fill, fill),
                                outline=COLORES["borde"] if borde else None,
                                width=max(1, self.c(2)))

    def lineas(self, dibujo, texto, x, y, ancho, tamano=26, paso=38, color=None, fuerte=False):
        palabras = texto.split()
        linea = ""
        inicio = y
        for palabra in palabras:
            prueba = f"{linea} {palabra}".strip()
            if dibujo.textbbox((0, 0), prueba, font=self.f(tamano, fuerte))[2] > self.c(ancho) and linea:
                self.texto(dibujo, x, y, linea, tamano, color, fuerte)
                y += paso
                linea = palabra
            else:
                linea = prueba
        if linea:
            self.texto(dibujo, x, y, linea, tamano, color, fuerte)
        return y + paso - inicio

    def anillo(self, dibujo, cx, cy, radio, color, grosor=4):
        dibujo.ellipse((self.c(cx-radio), self.c(cy-radio), self.c(cx+radio), self.c(cy+radio)),
                       outline=color, width=max(1, self.c(grosor)))

    def circulo(self, dibujo, cx, cy, radio, fill, borde=None, grosor=3):
        dibujo.ellipse((self.c(cx-radio), self.c(cy-radio), self.c(cx+radio), self.c(cy+radio)),
                       fill=fill, outline=borde, width=max(1, self.c(grosor)))

    def base_escena(self):
        return self.base.copy()

    def etiqueta(self, dibujo, txt, x, y, color="turquesa", ancho=0):
        w = ancho or min(430, max(185, len(txt) * 14))
        self.caja(dibujo, x, y, w, 43, "panel2", False, 13)
        self.texto(dibujo, x+16, y+9, txt, 20, COLORES[color], True)

    def placa(self, escena):
        imagen = self.base_escena()
        d = ImageDraw.Draw(imagen)
        self.caja(d, 78, 70, 440, 54, "panel2", False, 17)
        self.texto(d, 99, 83, "CS2023  ·  PROYECTO FINAL 2", 23, COLORES["turquesa"], True)

        if escena.clase == "portada":
            self.texto(d, 86, 255, self.configuracion["titulo"], 83, COLORES["blanco"], True)
            self.texto(d, 90, 374, self.configuracion["subtitulo"], 73, COLORES["turquesa"], True)
            self.texto(d, 91, 520, "Una cola, grados de entrada y un orden válido.", 31, COLORES["gris"])
            self.caja(d, 92, 685, 1030, 177, "panel", True)
            self.texto(d, 126, 720, "IDEA CENTRAL", 21, COLORES["amarillo"], True)
            self.lineas(d, "Primero van los vértices sin dependencias pendientes.", 126, 765, 900, 32, 45)
            for i, letra in enumerate(["A", "B", "C", "D"]):
                x = 1355 + i * 145
                y = 480 - (i % 2) * 110
                self.circulo(d, x, y, 52, "#1A3D57", COLORES["turquesa"])
                self.texto(d, x, y+2, letra, 36, COLORES["blanco"], True, "mm")
        elif escena.clase == "concepto":
            self.texto(d, 85, 230, escena.titulo, 62, COLORES["blanco"], True)
            self.lineas(d, escena.subtitulo, 90, 355, 1560, 39, 57, COLORES["turquesa"], True)
            self.caja(d, 90, 545, 1650, 220)
            self.texto(d, 140, 586, "¿CÓMO FUNCIONA?", 23, COLORES["amarillo"], True)
            self.lineas(d, escena.detalle, 140, 651, 1500, 33, 46)
            for i, (letra, x) in enumerate([("A", 1215), ("B", 1400), ("C", 1585)]):
                self.circulo(d, x, 860, 45, "#173D54", COLORES["turquesa"])
                self.texto(d, x, 861, letra, 32, COLORES["blanco"], True, "mm")
                if i < 2:
                    d.line([(self.c(x+58), self.c(860)), (self.c(x+125), self.c(860))],
                           fill=COLORES["gris"], width=max(2, self.c(4)))
        elif escena.clase == "seccion":
            self.texto(d, 90, 265, escena.titulo, 78, COLORES["turquesa"], True)
            self.lineas(d, escena.subtitulo, 96, 395, 1660, 42, 65, COLORES["blanco"], True)
            self.caja(d, 96, 610, 1665, 155)
            self.lineas(d, escena.detalle, 136, 653, 1530, 30, 42, COLORES["gris"])
        elif escena.clase == "complejidad":
            self.texto(d, 90, 182, "Complejidad del algoritmo", 72, COLORES["blanco"], True)
            self.caja(d, 90, 345, 810, 360)
            self.caja(d, 940, 345, 810, 360)
            self.texto(d, 140, 400, "TIEMPO", 30, COLORES["gris"], True)
            self.texto(d, 142, 477, "O(|V| + |E|)", 74, COLORES["turquesa"], True)
            self.lineas(d, "Cada vértice y cada arista se procesa una sola vez.", 142, 612, 710, 25, 38)
            self.texto(d, 990, 400, "ESPACIO", 30, COLORES["gris"], True)
            self.texto(d, 992, 477, "O(|V| + |E|)", 74, COLORES["azul"], True)
            self.lineas(d, "Guardamos listas de adyacencia, grados y la cola.", 992, 612, 710, 25, 38)
            self.texto(d, 104, 803, "Kahn sirve para ordenar tareas, cursos y procesos con dependencias.", 29, COLORES["amarillo"])
        elif escena.clase == "creditos":
            self.texto(d, 95, 210, self.configuracion["titulo"], 73, COLORES["blanco"], True)
            self.texto(d, 99, 320, self.configuracion["subtitulo"], 56, COLORES["turquesa"], True)
            self.texto(d, 105, 474, "INTEGRANTES", 27, COLORES["amarillo"], True)
            for i, nombre in enumerate(self.configuracion["integrantes"]):
                self.texto(d, 105, 541 + i * 72, nombre, 40, COLORES["blanco"])
            self.texto(d, 107, 910, self.configuracion["curso"], 27, COLORES["gris"])
        return imagen

    def coordenada_nodo(self, grafo, indice):
        nodo = grafo["nodos"][indice]
        return 120 + nodo["x"] * 1050, 287 + nodo["y"] * 528

    def extremos_arista(self, grafo, u, v, radio=50):
        x1, y1 = self.coordenada_nodo(grafo, u)
        x2, y2 = self.coordenada_nodo(grafo, v)
        dx, dy = x2-x1, y2-y1
        dist = math.hypot(dx, dy)
        if dist == 0:
            return (x1, y1), (x2, y2)
        ux, uy = dx/dist, dy/dist
        return (x1 + ux*radio, y1 + uy*radio), (x2 - ux*(radio+12), y2 - uy*(radio+12))

    def arista(self, dibujo, grafo, u, v, color, grosor=4):
        inicio, fin = self.extremos_arista(grafo, u, v)
        dx, dy = fin[0]-inicio[0], fin[1]-inicio[1]
        modulo = max(1, math.hypot(dx, dy))
        ux, uy = dx/modulo, dy/modulo
        dibujo.line([tuple(self.c(x) for x in inicio), tuple(self.c(x) for x in fin)],
                    fill=color, width=max(1, self.c(grosor)))
        punta = (fin[0]+ux*9, fin[1]+uy*9)
        izquierda = (fin[0]-ux*13-uy*10, fin[1]-uy*13+ux*10)
        derecha = (fin[0]-ux*13+uy*10, fin[1]-uy*13-ux*10)
        dibujo.polygon([tuple(self.c(z) for z in p) for p in (punta, izquierda, derecha)], fill=color)

    def chip(self, dibujo, letra, x, y, color="azul", ancho=55):
        self.caja(dibujo, x, y, ancho, 53, "panel2", True, 12)
        self.texto(dibujo, x+ancho/2, y+26, letra, 26, COLORES[color], True, "mm")

    def grafo_estado(self, escena, estado):
        imagen = self.base_escena()
        d = ImageDraw.Draw(imagen)
        grafo = escena.grafo
        nombres = [n["id"] for n in grafo["nodos"]]
        acento = "rojo" if estado.ciclo else "turquesa"

        self.texto(d, 83, 48, "ORDENAMIENTO TOPOLÓGICO", 48, COLORES["blanco"], True)
        self.etiqueta(d, "KAHN · COLA FIFO", 83, 117, "turquesa", 280)
        self.texto(d, 83, 197, escena.titulo, 32, COLORES["gris"])
        self.caja(d, 72, 260, 1110, 580)
        self.caja(d, 1212, 260, 633, 580)
        self.texto(d, 116, 281, "GRAFO DIRIGIDO", 22, COLORES["gris"], True)

        for indice, (u, v) in enumerate(grafo["aristas_idx"]):
            if indice == estado.arista and estado.tipo == "reducir":
                color, grosor = COLORES["amarillo"], 8
            elif indice in estado.eliminadas:
                color, grosor = "#30435C", 3
            else:
                color, grosor = COLORES["linea"], 4
            self.arista(d, grafo, u, v, color, grosor)

        for i, nombre in enumerate(nombres):
            x, y = self.coordenada_nodo(grafo, i)
            if estado.tipo == "extraer" and estado.actual == i:
                relleno, contorno = "#3B3D7F", COLORES["morado"]
            elif estado.tipo == "encolar" and estado.actual == i:
                relleno, contorno = "#1D585D", COLORES["turquesa"]
            elif i in estado.orden:
                relleno, contorno = "#2C4058", COLORES["morado"]
            elif estado.grados and estado.grados[i] == 0:
                relleno, contorno = "#174C60", COLORES["turquesa"]
            else:
                relleno, contorno = "#21334E", COLORES["azul"]
            self.circulo(d, x, y, 50, relleno, contorno, 4)
            self.texto(d, x, y+2, nombre, 33, COLORES["blanco"], True, "mm")
            if estado.grados:
                self.caja(d, x+29, y-65, 44, 37, "panel2", True, 12)
                self.texto(d, x+51, y-46, str(estado.grados[i]), 21,
                           COLORES["turquesa"] if estado.grados[i] == 0 else COLORES["blanco"],
                           True, "mm")

        self.texto(d, 1252, 297, "COLA (FIFO)", 24, COLORES["gris"], True)
        self.texto(d, 1252, 342, "frente", 18, COLORES["turquesa"])
        if estado.cola:
            for i, indice in enumerate(estado.cola):
                self.chip(d, nombres[indice], 1252 + i % 7 * 77, 379 + i // 7 * 66,
                          "turquesa" if i == 0 else "azul")
        else:
            self.texto(d, 1255, 394, "Vacía", 30, COLORES["suave"])

        self.texto(d, 1252, 483, "ORDEN TOPOLÓGICO", 24, COLORES["gris"], True)
        if estado.orden:
            for i, indice in enumerate(estado.orden):
                self.chip(d, nombres[indice], 1252 + i % 7 * 77, 531 + i // 7 * 60, "morado")
        else:
            self.texto(d, 1255, 550, "Pendiente", 30, COLORES["suave"])

        self.texto(d, 1252, 657, "GRADOS DE ENTRADA", 24, COLORES["gris"], True)
        for i, nombre in enumerate(nombres[:12]):
            columna, fila = i % 6, i // 6
            x = 1254 + 91 * columna
            y = 703 + 52 * fila
            valor = estado.grados[i] if estado.grados else 0
            self.texto(d, x, y, nombre, 22, COLORES["blanco"], True)
            self.texto(d, x+35, y, str(valor), 22,
                       COLORES["turquesa"] if valor == 0 else COLORES["amarillo"], True)

        self.caja(d, 72, 866, 1773, 148)
        self.texto(d, 112, 883, "PASO ACTUAL", 21, COLORES[acento], True)
        self.lineas(d, escena.detalle, 112, 924, 1680, 29, 41, COLORES["blanco"])
        self.texto(d, 1813, 219, f"{escena.numero}/{escena.total}", 22, COLORES["gris"], True, "ra")
        self.caja(d, 72, 1040, 1773, 9, "panel2", False, 4)
        if escena.total:
            self.caja(d, 72, 1040, max(13, 1773*escena.numero/escena.total), 9,
                      COLORES[acento], False, 4)
        return imagen

    def efecto(self, imagen, escena, progreso):
        if escena.clase != "paso" or not escena.estado:
            return imagen
        estado = escena.estado
        if estado.tipo not in ("encolar", "extraer", "reducir"):
            return imagen
        dibujo = ImageDraw.Draw(imagen)
        if estado.tipo == "reducir":
            inicio, fin = self.extremos_arista(escena.grafo, estado.actual, estado.destino)
            t = min(0.95, max(0.05, progreso))
            x = inicio[0] + (fin[0]-inicio[0])*t
            y = inicio[1] + (fin[1]-inicio[1])*t
            self.circulo(dibujo, x, y, 10, COLORES["amarillo"])
            self.anillo(dibujo, x, y, 15 + 4*math.sin(progreso*math.pi), COLORES["amarillo"], 2)
        else:
            x, y = self.coordenada_nodo(escena.grafo, estado.actual)
            radio = 59 + 8*math.sin(progreso*math.pi)
            self.anillo(dibujo, x, y, radio,
                        COLORES["turquesa"] if estado.tipo == "encolar" else COLORES["morado"], 4)
        return imagen


def verificar(ejecutable, grafos):
    for grafo in grafos:
        pasos = construir_pasos(ejecutable, grafo)
        ultimo = pasos[-1][2]
        nombres = [grafo["nodos"][i]["id"] for i in ultimo.orden]
        resultado = "CICLO DETECTADO" if ultimo.ciclo else " → ".join(nombres)
        print(f"{grafo['titulo']}: {resultado}")
        grafo["pasos"] = pasos


def renderizar(escenas, pintor, destino, fps, velocidad):
    if not shutil.which("ffmpeg"):
        raise RuntimeError("No se encontró FFmpeg. Instálalo y agrégalo a PATH.")
    destino.parent.mkdir(exist_ok=True)
    comando = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
               "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{pintor.ancho}x{pintor.alto}", "-r", str(fps),
               "-i", "-", "-an", "-c:v", "libx264", "-preset", "veryfast",
               "-crf", "19", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
               "-threads", "2", str(destino)]
    proceso = subprocess.Popen(comando, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    anterior = None
    total = sum(max(1, int(round(e.duracion * fps / velocidad))) for e in escenas)
    realizados = 0

    try:
        for escena in escenas:
            if escena.clase == "paso":
                actual = pintor.grafo_estado(escena, escena.estado)
                if escena.anterior and escena.anterior.grados:
                    vieja = pintor.grafo_estado(escena, escena.anterior)
                else:
                    vieja = anterior
            else:
                actual = pintor.placa(escena)
                vieja = anterior
            cantidad = max(1, int(round(escena.duracion * fps / velocidad)))
            transicion = max(1, min(cantidad, int(fps * 0.48)))
            for fotograma in range(cantidad):
                avance = (fotograma + 1) / cantidad
                if vieja is not None and fotograma < transicion:
                    t = (fotograma + 1) / transicion
                    t = t*t*(3-2*t)
                    imagen = Image.blend(vieja, actual, t)
                else:
                    imagen = actual.copy()
                pintor.efecto(imagen, escena, avance)
                proceso.stdin.write(imagen.tobytes())
                realizados += 1
                if realizados % 150 == 0 or realizados == total:
                    print(f"Render: {realizados}/{total} fotogramas", flush=True)
            anterior = actual
        proceso.stdin.close()
        error = proceso.stderr.read().decode("utf-8", "replace")
        retorno = proceso.wait()
        if retorno:
            raise RuntimeError(f"FFmpeg falló: {error}")
    except (Exception, KeyboardInterrupt):
        if proceso.poll() is None:
            proceso.kill()
        proceso.wait()
        if destino.exists():
            destino.unlink()
        raise


def main():
    parser = argparse.ArgumentParser(description="Animación del algoritmo de Kahn")
    parser.add_argument("--calidad", choices=("alta", "media", "prueba"), default="alta")
    parser.add_argument("--velocidad", type=float, default=1.0)
    parser.add_argument("--solo-probar", action="store_true")
    parser.add_argument("--salida", type=Path)
    args = parser.parse_args()
    if not 0.1 <= args.velocidad <= 20:
        parser.error("La velocidad debe estar entre 0.1 y 20.")

    with open(RAIZ / "configuracion.json", encoding="utf-8") as archivo:
        configuracion = json.load(archivo)
    principal = cargar_grafo(RAIZ / "grafos" / "principal.json")
    ciclo = cargar_grafo(RAIZ / "grafos" / "con_ciclo.json")
    unico = cargar_grafo(RAIZ / "grafos" / "un_vertice.json")
    ejecutable = compilar()
    verificar(ejecutable, (principal, ciclo, unico))
    if args.solo_probar:
        return

    calidades = {"alta": (1920, 1080, 24), "media": (1280, 720, 24), "prueba": (960, 540, 12)}
    ancho, alto, fps = calidades[args.calidad]
    pintor = Pintor(ancho, alto, configuracion)
    escenas = construir_escenas(principal, ciclo, unico)
    destino = args.salida or RAIZ / "salida" / configuracion["nombre_video"]
    segundos = sum(e.duracion for e in escenas) / args.velocidad
    print(f"Duración: {segundos:.1f} s · Resolución: {ancho}x{alto} · FPS: {fps}", flush=True)
    renderizar(escenas, pintor, destino, fps, args.velocidad)
    print(f"Video generado: {destino}", flush=True)


if __name__ == "__main__":
    main()
