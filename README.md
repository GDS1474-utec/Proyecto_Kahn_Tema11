# Ordenamiento topológico — Kahn

**CS2023 · Algoritmos y Estructuras de Datos · Proyecto Final 2 · Tema 11**

Implementación del algoritmo de Kahn en C++ y visualización en Python. La animación muestra el grado de entrada de cada vértice, la cola FIFO, las aristas procesadas y el orden topológico resultante. Los cambios de estado se obtienen ejecutando el programa C++; no hay una secuencia de pasos predeterminada en el código de animación.

## Archivos

- `src/kahn.cpp`: implementación de Kahn y emisión de eventos JSON por consola.
- `animacion.py`: ejecuta el programa C++, valida los eventos y genera el video MP4.
- `grafos/principal.json`: ejemplo de un grafo dirigido acíclico.
- `grafos/con_ciclo.json`: caso borde con ciclo.
- `grafos/un_vertice.json`: caso borde con un vértice.
- `configuracion.json`: título, curso e integrantes del equipo.
- `tests/test_kahn.py`: pruebas de ordenamiento y detección de ciclos.

## Software necesario

- Python 3.10 o superior.
- Un compilador C++ compatible con C++17: `g++` en PATH.
- FFmpeg instalado y disponible en PATH.
- Pillow para dibujar los fotogramas.

En Windows, `g++` puede instalarse con MSYS2/MinGW-w64 y FFmpeg desde sus distribuciones oficiales. Conviene comprobar en la terminal `g++ --version`, `ffmpeg -version` y `python --version`.

## Generar el video

Abrir una terminal en la carpeta del proyecto:

```bash
python -m pip install -r requirements.txt
python animacion.py --calidad alta
```

Salida: `salida/Kahn_Ordenamiento_Topologico.mp4` en 1920 × 1080, 24 fotogramas por segundo.

Para una versión de revisión más rápida:

```bash
python animacion.py --calidad prueba --velocidad 3
```

La calidad `prueba` usa 960 × 540 a 12 fotogramas por segundo. La velocidad predeterminada es 1; valores mayores aceleran el video.

Para comprobar que la ejecución del algoritmo produce un orden válido sin renderizar:

```bash
python animacion.py --solo-probar
```

También pueden ejecutar `ejecutar.bat` en Windows o `./ejecutar.sh` en Linux/macOS (con las herramientas indicadas ya instaladas).

## Ejecutar solo el algoritmo C++

```bash
g++ -std=c++17 -O2 -Wall -Wextra src/kahn.cpp -o kahn
```

El programa recibe por entrada estándar una primera línea con `n m`, seguida de `m` líneas con `u v`. Los vértices se numeran desde 0 hasta n − 1. Cada línea de salida es un evento JSON con una modificación del algoritmo. Por ejemplo:

```text
3 2
0 1
1 2
```

Los tipos de eventos son `inicio`, `encolar`, `extraer`, `reducir`, `finalizar` y `ciclo`. El archivo Python utiliza estos eventos para mostrar el avance.

## Pruebas

```bash
python -m unittest discover -s tests -v
```

## Funcionamiento

1. Calcular el grado de entrada de cada vértice.
2. Agregar a una cola todos los vértices con grado de entrada cero.
3. Extraer el primer vértice de la cola y agregarlo al orden.
4. Reducir el grado de entrada de sus vecinos y encolar los que lleguen a cero.
5. Repetir hasta vaciar la cola. Si faltan vértices, el grafo tiene un ciclo.

Para un grafo dirigido acíclico, el tiempo es **O(|V| + |E|)**, ya que cada vértice entra y sale de la cola una vez y cada arista se recorre una vez. El espacio del algoritmo es **O(|V| + |E|)** por las listas de adyacencia, los grados y la cola. La generación de un MP4 requiere trabajo adicional por cada fotograma, independiente de la complejidad del algoritmo.

## Antes de entregar

Editar `configuracion.json` con los nombres de los integrantes, generar el MP4 en alta calidad y subir el código al repositorio de GitHub. El video y el informe se entregan por separado según las indicaciones del curso.
