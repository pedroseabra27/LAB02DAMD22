# com_concorrencia.py
import multiprocessing
import time
import os
from contextlib import contextmanager
from dotenv import load_dotenv
import redis

load_dotenv()

def get_redis() -> redis.Redis:
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        password=os.getenv("REDIS_PASSWORD"),
        ssl=False,
        decode_responses=True
    )

@contextmanager
def distributed_lock(r: redis.Redis, resource: str, ttl: int = 5):
    """
    Lock distribuido via Redis SET NX EX.
    NX = somente define se a chave NAO existir — operacao atomica no Redis.
    EX = TTL em segundos — previne deadlock se o processo travar antes de liberar.
    Documentacao: https://redis.io/docs/latest/commands/set/
    """
    key = f"lock:{resource}"
    acquired = r.set(key, "1", nx=True, ex=ttl)
    if not acquired:
        raise RuntimeError(f"Recurso '{resource}' em uso — tente novamente")
    try:
        yield
    finally:
        r.delete(key)  # sempre libera, mesmo em caso de excecao

def inicializar_saldo(valor: int = 1000):
    r = get_redis()
    r.set("conta:saldo", valor)
    print(f"Saldo inicial: R${valor}")

def transferir_com_lock(valor: int, nome: str):
    """Transferencia COM lock distribuido — segura entre processos distintos."""
    r = get_redis()
    with distributed_lock(r, "conta:saldo"):
        saldo_atual = int(r.get("conta:saldo"))
        time.sleep(0.05)                       # mesmo delay — agora serializado pelo lock
        novo_saldo = saldo_atual - valor
        r.set("conta:saldo", novo_saldo)
        print(f"  [{nome}] transferiu R${valor}. Saldo atual: R${novo_saldo}")

if __name__ == "__main__":
    inicializar_saldo(1000)

    p1 = multiprocessing.Process(target=transferir_com_lock, args=(200, "Processo-A"))
    p2 = multiprocessing.Process(target=transferir_com_lock, args=(300, "Processo-B"))

    p1.start(); p2.start()
    p1.join();  p2.join()

    r = get_redis()
    saldo_final = int(r.get("conta:saldo"))
    print(f"\nSaldo final no Redis: R${saldo_final}")
    print(f"Resultado: {'R$500 correto' if saldo_final == 500 else 'race condition detectada'}")