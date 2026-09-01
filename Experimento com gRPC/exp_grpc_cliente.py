#from concurrent import futures
import time
import grpc
import csv
import exp_grpc_pb2
import exp_grpc_pb2_grpc

S = [1, 10000, 100000, 1000000] # Lista de tamanhos de mensagem.
N = 20 # Número de mensagens a serem enviadas para cada tamanho.
header = ["timestamp", "tamanho_bytes", "indice_chamada", "rtt_ms"] # headers do arquivo benchmark

def run():
    resultados = []

    with grpc.insecure_channel('localhost:12000') as channel:
        EnvioMensagem_stub = exp_grpc_pb2_grpc.EnvioMensagensStub(channel)

        for tamanho in S:
            texto_mensagem = "Z" * tamanho

            for i in range(N):
                mensagem = exp_grpc_pb2.Mensagem(mensagem = texto_mensagem)

                hora_ida = time.perf_counter()
                confirmacao = EnvioMensagem_stub.enviar(mensagem)
                hora_volta = time.perf_counter()

                rtt_ms = (hora_volta - hora_ida) * 1000

                resultados.append([
                    confirmacao.timestamp,
                    confirmacao.tamanho,
                    i,
                    rtt_ms
                ])
                
                print("RESPOSTA")
                print(f"Timestamp: {confirmacao.timestamp}")
                print(f"Tamanho (bytes): {confirmacao.tamanho}")
                print(f"Índice da chamada: {i}")
                print(f"RTT (ms): {rtt_ms}\n")

    with open('benchmark.log', 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(resultados)

if __name__ == "__main__":
    run()
