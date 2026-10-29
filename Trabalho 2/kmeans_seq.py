# K-Means de Lloyd sequencial em numpy (Tserial e gabarito da validação)
import os
# Força a BLAS a usar 1 thread. TEM que vir ANTES do "import numpy":
# a biblioteca lê essas variáveis só no momento em que é carregada.
# Sem isso, o "sequencial" usaria vários núcleos às escondidas e o speedup ficaria errado.
for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(var, "1")

import argparse, time
import numpy as np

def parse_args():
    p = argparse.ArgumentParser(description="K-Means sequencial (numpy).")
    p.add_argument("--nome", required=True, help="sufixo dos dados: real, sint_20000, ...")
    p.add_argument("--pasta", default="dados")
    p.add_argument("--iter", type=int, default=20, help="nº FIXO de iterações (igual em todas as versões)")
    return p.parse_args()

def atribui(X, C, xx):
    """
        Retorna, para cada ponto de dados, o índice do centroide mais próximo e as
        respectivas distâncias euclidianas ao quadrado.
        O cálculo de distância euclidiana entre um ponto de dados e um centroide
        pode ser escrito como: √[ Σ(xi - ci)² ] = √[ Σ(xi²) - 2 * Σ(xi * ci) + Σ(ci²) ].
        O termo Σ(xi²) é constante para todas as distâncias entre um mesmo ponto de dados
        e cada centroide: logo, na verificação de qual é o centroide mais próximo de um
        ponto de dados, podemos ignorar o termo Σ(xi²).
    """
    cc = np.sum(C * C, axis=1) # Σ(ci²) de cada centroide (vetor de tamanho k)
    D = cc - 2.0 * (X @ C.T) # N x k: Σ(xi - ci)² SEM o termo Σ(xi²)

    rotulos = np.argmin(D, axis=1) # centroide mais próximo de cada ponto
    dmin = D.min(axis=1) + xx # recoloca Σ(xi²) para obter a distância² verdadeira

    return rotulos, dmin

def atualiza(X, rotulos, C):
    """Novos centroides = soma dos pontos de cada cluster ÷ quantidade."""
    d = X.shape[1]; k = C.shape[0]
    
    somas = np.zeros((k, d)) # k x d
    np.add.at(somas, rotulos, X) # soma cada linha de X na linha do seu cluster

    contagens = np.bincount(rotulos, minlength=k) # k
    ok = contagens > 0 # regra do cluster vazio: mantém o centroide antigo
    C[ok] = somas[ok] / contagens[ok, None]

def kmeans(X, C0, iters):
    xx = np.sum(X * X, axis=1) # ||x||² de cada ponto: calculado uma vez, reaproveitado.
    C = C0.copy() # nunca alteramos o C0 original
    inercias = []

    for _ in range(iters):
        rotulos, dmin = atribui(X, C, xx)
        inercias.append(dmin.sum()) # inércia = soma das distâncias² (com os centroides ANTES de atualizar)
        atualiza(X, rotulos, C)
    
    return C, rotulos, inercias

def main():
    a = parse_args()
    X  = np.load(f"{a.pasta}/X_{a.nome}.npy")
    C0 = np.load(f"{a.pasta}/C0_{a.nome}.npy")
    N, d = X.shape; k = C0.shape[0]

    t0 = time.perf_counter() # cronômetro SÓ em volta do laço (leitura fica fora)
    C, rotulos, inercias = kmeans(X, C0, a.iter)
    t = time.perf_counter() - t0

    # Lloyd garante inércia não crescente (tolerância para arredondamento)
    monotona = all(b <= a_ * (1 + 1e-12) for a_, b in zip(inercias, inercias[1:]))

    np.save(f"{a.pasta}/C_seq_{a.nome}.npy", C) # gabarito

    print(f"N={N} d={d} k={k} iter={a.iter} | tempo={t:.3f}s ({t/a.iter*1000:.1f} ms/iter)")
    print(f"inércia: inicial={inercias[0]:.6f} final={inercias[-1]:.6f} | não crescente: {monotona}")

    print(f"tamanhos dos clusters: min={np.bincount(rotulos, minlength=k).min()} "
          f"max={np.bincount(rotulos, minlength=k).max()}")

    # Qualidade do agrupamento vs. cluster verdadeiro (y)
    from sklearn.metrics import adjusted_rand_score
    
    y = np.load(f"{a.pasta}/y_{a.nome}.npy")
    print(f"ARI vs. cluster verdadeiro: {adjusted_rand_score(y, rotulos):.3f}  (0 = aleatório, 1 = perfeito)")

    # mesma linha das versões MPI e Spark (p=1; sem t_dist, t_comp e t_comm), lida pelo rodar_bateria.sh
    print(f"RESULTADO,seq,1,{N},{d},{k},{a.iter},,{t:.6f},,,{inercias[-1]:.6f}")

if __name__ == "__main__":
    main()
