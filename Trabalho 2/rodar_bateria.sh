#!/bin/bash
# Bateria de execuções do K-Means (baseado no script_cluster do curso).
# Roda cada configuração REPS vezes e grava a linha RESULTADO de cada execução num CSV.
#
# Uso:  ./rodar_bateria.sh <seq|mpi|spark> <nome dos dados> ["lista de p"]
# Ex.:  ./rodar_bateria.sh mpi   sint_600000
#       ./rodar_bateria.sh spark sint_600000 "1 2 4 8 16"
#       SMOKE=1 ./rodar_bateria.sh mpi sint_20000      (teste rápido: p = 1 e 2, 1 repetição)
# Opções por variável de ambiente:
#   REPS=3            nº de repetições
#   VARIANTE=base     rótulo da versão do código (usado nas 3 alterações)
#   EXTRA="..."       argumentos extras repassados ao programa Python
#   MEM_SPARK=8g      memória da JVM no Spark local (o cache do RDD fica nela)

set -u                                   # erro se usar variável não definida (pega erro de digitação)

IMPL=$1
NOME=$2
LISTA_P=${3:-"1 2 4 8 16 32 64 128"}
REPS=${REPS:-3}
VARIANTE=${VARIANTE:-base}
EXTRA=${EXTRA:-}
MEM_SPARK=${MEM_SPARK:-8g}

# Recursos do n-11 (levantados com lscpu em 19/10): 2 sockets x 8 núcleos, 2 threads por núcleo
NUCLEOS=16
THREADS_HW=32

if [ "${SMOKE:-0}" = 1 ]; then LISTA_P="1 2"; REPS=1; fi
if [ "$IMPL" = seq ]; then LISTA_P="1"; fi        # o sequencial só existe com 1 processo

# 1 processo = 1 núcleo: BLAS sem threads extras (vale para MPI, seq e o driver do Spark)
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYSPARK_PYTHON=$(which python)            # executores do Spark usam o Python do venv

mkdir -p resultados
CSV=resultados/${IMPL}_${NOME}_${VARIANTE}.csv
LOG=resultados/${IMPL}_${NOME}_${VARIANTE}.log
# cabeçalho só se o CSV ainda não existe (rodar de novo ACRESCENTA linhas, não apaga)
[ -f "$CSV" ] || echo "impl,p,N,d,k,iter,t_dist,t_total,t_comp,t_comm,inercia,rep,oversub,variante" > "$CSV"

# Repetição por fora e p por dentro: se a máquina ficar carregada por um tempo,
# o efeito se espalha entre os p em vez de cair todo em um p só
for rep in $(seq 1 "$REPS"); do
  for p in $LISTA_P; do

    # oversub: 0 = até 1 processo por núcleo físico; 1 = usando hyperthreading; 2 = mais processos que threads
    if   [ "$p" -le $NUCLEOS ];    then OVERSUB=0; FLAG=""
    elif [ "$p" -le $THREADS_HW ]; then OVERSUB=1; FLAG="--use-hwthread-cpus"
    else                                OVERSUB=2; FLAG="--oversubscribe"
    fi

    # Monta o comando como um array (cada palavra um elemento; $FLAG vazio some)
    case $IMPL in
      seq)   CMD=(python kmeans_seq.py --nome "$NOME" $EXTRA) ;;
      mpi)   CMD=(mpiexec -n "$p" $FLAG python kmeans_mpi.py --nome "$NOME" $EXTRA) ;;
      spark) CMD=(spark-submit --master "local[$p]" --driver-memory "$MEM_SPARK"
                  --conf spark.default.parallelism="$p"
                  kmeans_spark.py --nome "$NOME" --particoes "$p" $EXTRA) ;;
      *)     echo "impl deve ser seq, mpi ou spark"; exit 1 ;;
    esac

    # No log: data, configuração, carga da máquina (outros grupos usam o mesmo nó) e o comando
    { echo "=== $(date '+%F %T') rep=$rep p=$p oversub=$OVERSUB | carga: $(cut -d' ' -f1-3 /proc/loadavg)"
      echo "${CMD[*]}"; } >> "$LOG"

    SAIDA=$("${CMD[@]}" 2>&1)            # roda e guarda toda a saída (inclusive erros)
    STATUS=$?
    echo "$SAIDA" >> "$LOG"

    LINHA=$(echo "$SAIDA" | grep '^RESULTADO,' | tail -1)
    if [ $STATUS -ne 0 ] || [ -z "$LINHA" ]; then
      echo "FALHOU rep=$rep p=$p (status $STATUS): veja $LOG"
      continue                           # segue para a próxima configuração
    fi

    # Tira o prefixo "RESULTADO," e acrescenta rep, oversub e variante
    echo "${LINHA#RESULTADO,},$rep,$OVERSUB,$VARIANTE" >> "$CSV"
    echo "ok $IMPL rep=$rep p=$p: t_total=$(echo "$LINHA" | cut -d, -f9) s"
  done
done

echo "Concluído. CSV: $CSV | log: $LOG"
