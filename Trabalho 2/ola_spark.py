# ola_spark.py — teste do ambiente Spark (passo 0.4)
# Testa as 4 peças do K-Means em Spark: partições, broadcast, mapPartitions, treeAggregate.
from pyspark import SparkContext
import numpy as np

sc = SparkContext(appName="ola_spark") # o --master vem do spark-submit, não do código
sc.setLogLevel("WARN") # esconde o log INFO, que é muito verboso

print("master:", sc.master, "| paralelismo padrão:", sc.defaultParallelism)

# 10 números divididos em 4 partições (equivalente às "fatias" do Scatterv)
rdd = sc.parallelize(range(10), numSlices=4)
print("conteúdo de cada partição:", rdd.glom().collect()) # glom: junta cada partição numa lista

# Broadcast: envia o vetor uma vez para cada executor (equivalente ao Bcast)
bc = sc.broadcast(np.array([1.0, 2.0, 3.0]))

def resumo_particao(iterador):
    # Roda UMA vez por partição, dentro do executor.
    # Mesma ideia do K-Means: converter a partição em numpy e calcular de forma vetorizada.
    vals = np.fromiter(iterador, dtype=np.float64)
    yield np.array([vals.sum(), len(vals), bc.value.sum()]) # [soma, contagem, soma do broadcast]

# treeAggregate: soma os vetores parciais em árvore até chegar ao driver (equivalente ao Allreduce)
total = rdd.mapPartitions(resumo_particao).treeAggregate(
    np.zeros(3), # valor inicial
    lambda acc, v: acc + v, # combina dentro de uma partição
    lambda a, b: a + b) # combina resultados de partições diferentes

print(f"soma={total[0]:.0f} (esperado 45) | contagem={total[1]:.0f} (esperado 10) | "
      f"broadcast somado em 4 partições={total[2]:.0f} (esperado 24)")
sc.stop()
