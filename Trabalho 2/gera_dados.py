# Gera a matriz de documentos X (N x d) e os centróides iniciais C0 (k x d).
# Sequencial, MPI e Spark leem os mesmos arquivos.
import argparse, json, os, time
import numpy as np

def parse_args():
    p = argparse.ArgumentParser(description="Gera X (N x d), C0 (k x d) e rótulos y.")
    p.add_argument("--modo", choices=["real", "sintetico"], required=True)
    p.add_argument("--N", type=int, default=400_000, help="nº de documentos (só no modo sintético)")
    p.add_argument("--d", type=int, default=256, help="dimensão de cada vetor-documento")
    p.add_argument("--k", type=int, default=64, help="nº de clusters")
    p.add_argument("--seed", type=int, default=42, help="semente: mesmos dados e mesmos C0 sempre")
    p.add_argument("--nome", default=None, help="sufixo dos arquivos (padrão: real ou sint_<N>)")
    p.add_argument("--saida", default="dados", help="pasta de saída")
    p.add_argument("--arquivo-20ng", default="dados/20news-bydate.tar.gz",
                   help="arquivo do 20 Newsgroups baixado manualmente (modo real)")
    return p.parse_args()

def carrega_20newsgroups_local(arquivo):
    import tarfile
    from sklearn.datasets import load_files
    # Mesmas funções de limpeza que o fetch_20newsgroups usa internamente
    from sklearn.datasets._twenty_newsgroups import (
        strip_newsgroup_header, strip_newsgroup_footer, strip_newsgroup_quoting)

    pasta = os.path.dirname(arquivo)
    if not os.path.isdir(os.path.join(pasta, "20news-bydate-train")): # extrai só na 1ª vez
        with tarfile.open(arquivo, "r:gz") as tar:
            tar.extractall(pasta, filter="data") # filter="data": não deixa o .tar escrever fora da pasta

    textos, rotulos = [], []
    for parte in ("20news-bydate-train", "20news-bydate-test"):
        # shuffle=False é ESSENCIAL: o padrão embaralha sem semente,
        # e a ordem das linhas de X mudaria a cada execução
        b = load_files(os.path.join(pasta, parte), encoding="latin1", shuffle=False)
        textos += [strip_newsgroup_quoting(strip_newsgroup_footer(strip_newsgroup_header(t)))
                   for t in b.data]
        rotulos.append(b.target)
    return textos, np.concatenate(rotulos)

def vetoriza_20newsgroups(arquivo, d, seed):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.decomposition import TruncatedSVD
    from sklearn.preprocessing import normalize

    textos, alvo = carrega_20newsgroups_local(arquivo) # ~18.800 mensagens, 20 temas

    # TF-IDF: cada documento vira um vetor esparso de 20.000 palavras
    tfidf = TfidfVectorizer(max_features=20_000, stop_words="english", sublinear_tf=True, min_df=2)
    T = tfidf.fit_transform(textos)

    # Remove documentos vazios (viraram vetor zero após a limpeza)
    nao_vazios = T.getnnz(axis=1) > 0
    T, y = T[nao_vazios], alvo[nao_vazios]

    # TruncatedSVD: 20.000 palavras -> d "temas latentes" (matriz densa N x d)
    X = TruncatedSVD(n_components=d, random_state=seed).fit_transform(T)
    return normalize(X), y.astype(np.int32)   # norma 1: distância euclidiana ~ cosseno

def gera_sintetico(N, d, k, seed, bloco=50_000):
    rng = np.random.default_rng(seed) # gerador com semente: reprodutível
    temas = rng.random((k, d)) ** 4 # k "temas": poucos termos com peso alto (^4 concentra)
    y = rng.integers(0, k, size=N).astype(np.int32) # tema verdadeiro de cada documento
    X = np.empty((N, d), dtype=np.float64) # aloca a matriz final UMA vez

    # Gera em blocos: evita ter cópias temporárias de N x d inteiras na memória
    for ini in range(0, N, bloco):
        fim = min(ini + bloco, N)
        ruido = 0.5 * rng.random((fim - ini, d)) ** 4 # ruído não negativo, mais fraco que o tema
        X[ini:fim] = temas[y[ini:fim]] + ruido # documento = tema + ruído
        X[ini:fim] /= np.linalg.norm(X[ini:fim], axis=1, keepdims=True) # norma 1, igual ao real
    return X, y

def centroides_iniciais(X, k, seed):
    # Escolhe k documentos distintos ao acaso como centróides iniciais.
    # seed+1: fluxo aleatório independente do usado para gerar os dados.
    rng = np.random.default_rng(seed + 1)
    idx = np.sort(rng.choice(X.shape[0], size=k, replace=False))
    return X[idx] # indexação por lista já devolve uma cópia contígua k x d

def main():
    a = parse_args()
    os.makedirs(a.saida, exist_ok=True)
    t0 = time.perf_counter()

    if a.modo == "real":
        X, y = vetoriza_20newsgroups(a.arquivo_20ng, a.d, a.seed)
        nome = a.nome or "real"
    else:
        X, y = gera_sintetico(a.N, a.d, a.k, a.seed)
        nome = a.nome or f"sint_{a.N}"

    # Garantias para o MPI: float64 e memória contígua (C-order)
    X = np.ascontiguousarray(X, dtype=np.float64)
    C0 = centroides_iniciais(X, a.k, a.seed)

    base = os.path.join(a.saida, f"{{}}_{nome}.npy")
    np.save(base.format("X"), X)
    np.save(base.format("C0"), C0)
    np.save(base.format("y"), y)

    # Metadados: registram como os dados foram gerados 
    meta = dict(modo=a.modo, N=X.shape[0], d=X.shape[1], k=a.k, seed=a.seed,
                dtype=str(X.dtype), numpy=np.__version__)
    with open(os.path.join(a.saida, f"meta_{nome}.json"), "w") as f:
        json.dump(meta, f, indent=2)

    print(f"X: {X.shape} {X.dtype} contígua={X.flags['C_CONTIGUOUS']} "
          f"{X.nbytes/1e6:.1f} MB | C0: {C0.shape} | soma(X)={X.sum():.6f} "
          f"| soma(C0)={C0.sum():.6f} | {time.perf_counter()-t0:.1f}s")

if __name__ == "__main__":
    main()
