#include <iostream>
#include <vector>
#include <utility>
#include <stdexcept>

using namespace std;

struct Arista {
    int destino;
    int indice;
};

void evento_inicio(const vector<int>& grado) {
    cout << "{\"tipo\":\"inicio\",\"grados\":[";
    for (size_t i = 0; i < grado.size(); ++i) {
        if (i) cout << ',';
        cout << grado[i];
    }
    cout << "]}\n";
}

void evento(const char* tipo, int u = -1, int v = -1, int grado = -1, int arista = -1) {
    cout << "{\"tipo\":\"" << tipo << '"';
    if (u >= 0) cout << ",\"u\":" << u;
    if (v >= 0) cout << ",\"v\":" << v;
    if (grado >= 0) cout << ",\"grado\":" << grado;
    if (arista >= 0) cout << ",\"arista\":" << arista;
    cout << "}\n";
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, m;
    if (!(cin >> n >> m) || n < 1 || m < 0 || n > 100000 || m > 1000000) {
        cerr << "Entrada invalida. Formato: n m, seguido de m aristas u v.\n";
        return 1;
    }

    vector<vector<Arista>> adyacencia(n);
    vector<int> grado(n, 0);

    for (int i = 0; i < m; ++i) {
        int u, v;
        if (!(cin >> u >> v) || u < 0 || u >= n || v < 0 || v >= n) {
            cerr << "Arista invalida en la posicion " << i << ".\n";
            return 1;
        }
        adyacencia[u].push_back({v, i});
        ++grado[v];
    }

    evento_inicio(grado);

    vector<int> cola;
    cola.reserve(n);
    size_t frente = 0;
    int procesados = 0;

    for (int u = 0; u < n; ++u) {
        if (grado[u] == 0) {
            cola.push_back(u);
            evento("encolar", u);
        }
    }

    while (frente < cola.size()) {
        int u = cola[frente++];
        ++procesados;
        evento("extraer", u);

        for (const Arista& e : adyacencia[u]) {
            --grado[e.destino];
            evento("reducir", u, e.destino, grado[e.destino], e.indice);

            if (grado[e.destino] == 0) {
                cola.push_back(e.destino);
                evento("encolar", e.destino);
            }
        }
    }

    if (procesados == n) {
        evento("finalizar");
    } else {
        evento("ciclo");
    }

    return 0;
}
