from solve import main

horarios="./dados/exemplos/horarios_teste.xlsx"
salas="./dados/2024_1/salas_2024_1.csv"
salas_preferenciais="./dados/2024_1/salas_preferenciais_2024.1.xlsx"

main(arquivo_horarios=horarios,arquivo_salas=salas,arquivo_salas_preferenciais=salas_preferenciais)

# Atenção, como estamos usando o solve.py para resolver o problema
# as planilhas geradas são salvas na no caminho /web/static/dados
