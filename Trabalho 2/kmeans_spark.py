# K-Means de Lloyd em PySpark (RDD): cache (opcional) + broadcast + mapPartitions + treeAggregate
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
    
    # Alteração Spark (b): sem cache, cada iteração refaz a leitura dos blocos e o cálculo de Σ(xi²)
    p.add_argument("--sem-cache", action="store_true", help="não chama cache() no RDD dos dados")

    # Alterações de desempenho: o padrão é a MELHOR versão (a usada no teste principal);
    # a outra opção é o "antes", usado só para medir o impacto de cada alteração
    p.add_argument("--somas", choices=["onehot", "add_at"], default="onehot",
                   help="produto de matrizes com a matriz one-hot (padrão) x np.add.at")
    
    return p.parse_args()

def divisao(N, p):
    """Linhas por processo e início de cada pedaço.
    Ex.: N = 10, p = 4 -> linhas = [3, 3, 2, 2], inicios = [0, 3, 6, 8]."""
    linhas = np.full(p, N // p) # todos recebem a parte inteira da divisão...
    linhas[: N % p] += 1 # ...e os primeiros (N % p) processos recebem uma linha a mais
    inicios = np.cumsum(linhas) - linhas # início de cada pedaço = soma dos pedaços anteriores
    return linhas, inicios

def atribui(X, C, xx):
    """
        Idêntica ao kmeans_seq.py, mas aplicada só à fatia local de cada processo.
        Retorna, para cada ponto de dados, o índice do centroide mais próximo e as
        respectivas distâncias euclidianas ao quadrado.
        O cálculo de distância euclidiana entre um ponto de dados e um centroide
        pode ser escrito como: √[ Σ(xi - ci)² ] = √[ Σ(xi²) - 2 * Σ(xi * ci) + Σ(ci²) ].
        O termo Σ(xi²) é constante para todas as distâncias entre um mesmo ponto de dados
        e cada centroide: logo, na verificação de qual é o centroide mais próximo de um
        ponto de dados, podemos ignorar o termo Σ(xi²).
    """
    cc = np.sum(C * C, axis=1) # Σ(ci²) de cada centroide (vetor de tamanho k)
    D = cc - 2.0 * (X @ C.T) # n_local x k: Σ(xi - ci)² SEM o termo Σ(xi²)

    rotulos = np.argmin(D, axis=1) # centroide mais próximo de cada ponto
    dmin = D[np.arange(D.shape[0]), rotulos] + xx # recoloca Σ(xi²) para obter a distância² verdadeira

    return rotulos, dmin

def somas_locais(X_local, rotulos, k, modo="add_at"):
    """Metade do 'atualiza' do sequencial: só soma e conta."""
    if modo == "onehot":
        # M[i, j] = 1 se o ponto i está no cluster j. Então (M.T @ X)[j] = soma dos pontos do cluster j.
        # Soma feita como produto de matrizes (BLAS), que é muito mais rápido.
        M = np.zeros((X_local.shape[0], k))
        M[np.arange(X_local.shape[0]), rotulos] = 1.0
        somas = M.T @ X_local
    else:
        # "Antes" da alteração: mesma conta, mas linha a linha (laço interno do numpy, sem BLAS)
        somas = np.zeros((k, X_local.shape[1]))
        np.add.at(somas, rotulos, X_local)
    
    contagens = np.bincount(rotulos, minlength=k).astype(np.float64) # float64: mesmo tipo usado na versão com MPI
    return somas, contagens

def distribui(sc, caminho, P, usa_cache=False):
    N, d = np.load(caminho, mmap_mode="r").shape # lê só o cabeçalho do .npy (N e d)
    linhas, inicios = divisao(N, P) # mesma divisão por linhas da versão com MPI

    def carrega_bloco(i):
        # Roda NO EXECUTOR: mapeia o arquivo e copia para a memória só as linhas do bloco i
        Xm = np.load(caminho, mmap_mode="r")
        Xb = np.array(Xm[inicios[i]:inicios[i] + linhas[i]], dtype=np.float64)
        return Xb, np.sum(Xb * Xb, axis=1) # guarda também Σ(xi²), que não muda entre iterações

    t0 = time.perf_counter()

    # P elementos (0..P-1) em P partições: cada partição recebe exatamente 1 índice -> 1 bloco
    rdd = sc.parallelize(range(P), P).map(carrega_bloco)

    if usa_cache:
        rdd = rdd.cache() # guarda os blocos na memória: as 20 iterações reaproveitam

    rdd.count() # AÇÃO: força a carga (e, com cache, preenche o cache)

    t_dist = time.perf_counter() - t0

    return rdd, N, d, t_dist

def kmeans_spark(sc, rdd, C0, iters, modo_somas="add_at"):
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
                rotulos, dmin = atribui(Xb, Cb, xxb)
                somas, contagens = somas_locais(Xb, rotulos, k, modo_somas)
                yield somas, contagens, dmin.sum()

        # treeAggregate: combina os resultados parciais em árvore até o driver
        somas, contagens, iner = rdd.mapPartitions(parcial).treeAggregate(zero, soma3, soma3)

        inercias.append(iner)

        bc.unpersist() # descarta a cópia antiga de C nos executores

        C = C.copy() # novo array para os novos centroides
        ok = contagens > 0 # mesma regra do cluster vazio
        C[ok] = somas[ok] / contagens[ok, None]
    
    t_total = time.perf_counter() - t0

    return C, inercias, t_total

def main():
    a = parse_args()

    conf = SparkConf().setAppName(f"kmeans_spark_{a.nome}")

    # Threads da BLAS nos EXECUTORES: o os.environ do driver não chega até eles
    for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        conf.setExecutorEnv(var, "1")

    sc = SparkContext(conf=conf)

    # Diminui drasticamente a quantidade de informações no log de terminal do Spark.
    sc.setLogLevel("WARN")

    caminho = os.path.abspath(f"{a.pasta}/X_{a.nome}.npy") # caminho ABSOLUTO: o executor roda em outra pasta
    
    P = a.particoes or sc.defaultParallelism # partições = núcleos
    C0 = np.load(f"{a.pasta}/C0_{a.nome}.npy")

    rdd, N, d, t_dist = distribui(sc, caminho, P, usa_cache=not a.sem_cache)
    C, inercias, t_total = kmeans_spark(sc, rdd, C0, a.iter, a.somas)
    
    np.save(f"{a.pasta}/C_spark_{a.nome}_P{P}.npy", C)

    # ---- validação ----
    C_seq = np.load(f"{a.pasta}/C_seq_{a.nome}.npy")

    monotona = all(b <= x * (1 + 1e-12) for x, b in zip(inercias, inercias[1:]))
    k = C0.shape[0]

    print(f"master={sc.master} partições={P} cache={not a.sem_cache} somas={a.somas}")

    print(f"N={N} d={d} k={k} iter={a.iter} | dist={t_dist:.3f}s total={t_total:.3f}s | "
          f"inércia final={inercias[-1]:.6f} | não crescente: {monotona}")
    
    print(f"max |C_spark - C_seq| = {np.abs(C - C_seq).max():.2e}")

    # mesmas colunas da versão com MPI; comp/comm ficam vazios (o Spark não expõe essa separação no driver)
    print(f"RESULTADO,spark,{P},{N},{d},{k},{a.iter},{t_dist:.6f},{t_total:.6f},,,{inercias[-1]:.6f}")

    sc.stop()

if __name__ == "__main__":
    main()
