from concurrent import futures
from datetime import datetime, timezone
import grpc
import exp_grpc_pb2
import exp_grpc_pb2_grpc

class EnvioMensagensServicer(exp_grpc_pb2_grpc.EnvioMensagensServicer):
    def enviar(self, request, context):
        tamanho = len(request.mensagem)
        timestamp = datetime.now(timezone.utc).isoformat()

        print(f"[servidor] Recebido payload de {tamanho} bytes em {timestamp}")
        return exp_grpc_pb2.Confirmacao(tamanho = tamanho, timestamp = timestamp)

servidor = grpc.server(futures.ThreadPoolExecutor(max_workers = 10))
exp_grpc_pb2_grpc.add_EnvioMensagensServicer_to_server(EnvioMensagensServicer(), servidor)

servidor.add_insecure_port('[::]:12000')
servidor.start()
servidor.wait_for_termination()
