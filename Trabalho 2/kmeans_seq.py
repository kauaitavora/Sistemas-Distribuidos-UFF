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
    """Para cada linha de X, o índice do centróide mais próximo e a distância² até ele."""
    cc = np.einsum("ij,ij->i", C, C) # ||c||² de cada centróide (vetor de tamanho k)
    D = cc - 2.0 * (X @ C.T) # N x k: ||x-c||² SEM o termo ||x||² (não muda o argmin)
    rotulos = np.argmin(D, axis=1) # centróide mais próximo de cada documento
    dmin = D.min(axis=1) + xx # recoloca ||x||² para obter a distância² verdadeira
    return rotulos, dmin

def atualiza(X, rotulos, C, k):
    """Novos centróides = soma dos documentos de cada cluster ÷ quantidade."""
    somas = np.zeros((k, X.shape[1])) # k x d
    np.add.at(somas, rotulos, X) # soma cada linha de X na linha do seu cluster
    contagens = np.bincount(rotulos, minlength=k).astype(np.float64) # k
    C_novo = C.copy()
    ok = contagens > 0 # regra do cluster vazio: mantém o centróide antigo
    C_novo[ok] = somas[ok] / contagens[ok, None]
    return C_novo

def kmeans(X, C0, iters):
    xx = np.einsum("ij,ij->i", X, X) # ||x||² de cada documento: calculado uma vez, reaproveitado
    C = C0.copy() # nunca alteramos o C0 original
    inercias = []
    for _ in range(iters):
        rotulos, dmin = atribui(X, C, xx)
        inercias.append(dmin.sum()) # inércia = soma das distâncias² (com os centróides ANTES de atualizar)
        C = atualiza(X, rotulos, C, C.shape[0])
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

    # Qualidade do agrupamento vs. tema verdadeiro (só validação, fora do tempo)
    from sklearn.metrics import adjusted_rand_score
    y = np.load(f"{a.pasta}/y_{a.nome}.npy")
    print(f"ARI vs. tema verdadeiro: {adjusted_rand_score(y, rotulos):.3f}  (0 = aleatório, 1 = perfeito)")

if __name__ == "__main__":
    main()
