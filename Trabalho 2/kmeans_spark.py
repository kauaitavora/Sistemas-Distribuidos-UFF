# K-Means de Lloyd em PySpark (RDD): cache + broadcast + mapPartitions + treeAggregate
import os
for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(var, "1") # vale só para o DRIVER; para os executores, ver SparkConf no main

import argparse, time
import numpy as np
from pyspark import SparkConf, SparkContext

def parse_args():
    p = argparse.ArgumentParser(description="K-Means Spark (RDD).")
    p.add_argument("--nome", required=True)
    p.add_argument("--pasta", default="dados")
    p.add_argument("--iter", type=int, default=20)
    p.add_argument("--particoes", type=int, default=0,
                   help="nº de partições (0 = nº de núcleos do Spark, defaultParallelism)")
    return p.parse_args()

def divisao(N, p):
    """Linhas por processo e início de cada pedaço."""
    base, resto = divmod(N, p)
    linhas = np.array([base + (1 if r < resto else 0) for r in range(p)])
    inicios = np.concatenate(([0], np.cumsum(linhas)[:-1]))
    return linhas, inicios

def atribui(X, C, xx):
    """Idêntica ao kmeans_seq.py, mas aplicada só à fatia local."""
    cc = np.einsum("ij,ij->i", C, C)
    D = cc - 2.0 * (X @ C.T)
    rotulos = np.argmin(D, axis=1)
    return rotulos, D.min(axis=1) + xx

def somas_locais(X_local, rotulos, k):
    """Metade do 'atualiza' do sequencial: só soma e conta. A divisão fica para DEPOIS do Allreduce."""
    somas = np.zeros((k, X_local.shape[1]))
    np.add.at(somas, rotulos, X_local)
    contagens = np.bincount(rotulos, minlength=k).astype(np.float64) # float64: mesmo tipo do buffer MPI.DOUBLE
    return somas, contagens

def distribui(sc, caminho, P):
    N, d = np.load(caminho, mmap_mode="r").shape # lê só o cabeçalho do .npy (N e d)
    linhas, inicios = divisao(N, P) # mesma divisão por linhas do MPI

    def carrega_bloco(i):
        # Roda NO EXECUTOR: mapeia o arquivo e copia para a memória só as linhas do bloco i
        Xm = np.load(caminho, mmap_mode="r")
        Xb = np.array(Xm[inicios[i]:inicios[i] + linhas[i]], dtype=np.float64)
        return Xb, np.einsum("ij,ij->i", Xb, Xb) # guarda também ||x||², que não muda entre iterações

    t0 = time.perf_counter()
    # P elementos (0..P-1) em P partições: cada partição recebe exatamente 1 índice -> 1 bloco
    rdd = sc.parallelize(range(P), P).map(carrega_bloco).cache()
    rdd.count() # AÇÃO: força a carga e preenche o cache
    t_dist = time.perf_counter() - t0
    return rdd, N, d, t_dist

def kmeans_spark(sc, rdd, C0, iters):
    k, d = C0.shape
    C = C0.copy()
    zero = (np.zeros((k, d)), np.zeros(k), 0.0) # (somas, contagens, inércia)
    soma3 = lambda a, b: (a[0] + b[0], a[1] + b[1], a[2] + b[2]) # cria arrays NOVOS, não altera a/b
    inercias = []

    t0 = time.perf_counter()
    for _ in range(iters):
        bc = sc.broadcast(C) # C (k x d) enviado UMA vez a cada executor

        def parcial(blocos): # roda no executor, uma vez por partição
            Cb = bc.value
            for Xb, xxb in blocos: # há exatamente 1 bloco por partição
                rot, dmin = atribui(Xb, Cb, xxb)
                somas, cont = somas_locais(Xb, rot, k)
                yield somas, cont, dmin.sum()

        # treeAggregate: combina os resultados parciais em árvore até o driver
        somas, cont, ine = rdd.mapPartitions(parcial).treeAggregate(zero, soma3, soma3)
        bc.unpersist() # descarta a cópia antiga de C nos executores
        inercias.append(ine)

        C = C.copy() # novo array para os novos centróides
        ok = cont > 0 # mesma regra do cluster vazio
        C[ok] = somas[ok] / cont[ok, None]
    t_total = time.perf_counter() - t0
    return C, inercias, t_total

def main():
    a = parse_args()
    # Threads da BLAS nos EXECUTORES: o os.environ do driver não chega até eles
    conf = SparkConf().setAppName(f"kmeans_spark_{a.nome}")
    for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        conf.setExecutorEnv(var, "1")
    sc = SparkContext(conf=conf)
    sc.setLogLevel("WARN")

    P = a.particoes or sc.defaultParallelism # partições = núcleos
    caminho = os.path.abspath(f"{a.pasta}/X_{a.nome}.npy") # caminho ABSOLUTO: o executor roda em outra pasta
    C0 = np.load(f"{a.pasta}/C0_{a.nome}.npy")

    # Sanidade: o que os executores enxergam (fora do tempo)
    threads = sc.parallelize(range(P), P).map(
        lambda _: os.environ.get("OPENBLAS_NUM_THREADS")).distinct().collect()

    rdd, N, d, t_dist = distribui(sc, caminho, P)
    C, inercias, t_total = kmeans_spark(sc, rdd, C0, a.iter)

    # ---- fora do tempo: validação ----
    k = C0.shape[0]
    monotona = all(b <= x * (1 + 1e-12) for x, b in zip(inercias, inercias[1:]))
    np.save(f"{a.pasta}/C_spark_{a.nome}_P{P}.npy", C)
    C_seq = np.load(f"{a.pasta}/C_seq_{a.nome}.npy")
    print(f"master={sc.master} partições={P} | OPENBLAS_NUM_THREADS nos executores={threads}")
    print(f"N={N} d={d} k={k} iter={a.iter} | dist={t_dist:.3f}s total={t_total:.3f}s | "
          f"inércia final={inercias[-1]:.6f} | não crescente: {monotona}")
    print(f"max |C_spark - C_seq| = {np.abs(C - C_seq).max():.2e}")
    # mesmas colunas do MPI; comp/comm ficam vazios (o Spark não expõe essa separação no driver)
    print(f"RESULTADO,spark,{P},{N},{d},{k},{a.iter},{t_dist:.6f},{t_total:.6f},,,{inercias[-1]:.6f}")
    sc.stop()

if __name__ == "__main__":
    main()
