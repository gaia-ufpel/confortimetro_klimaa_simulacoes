from graphviz import Digraph


def generate_flowchart():
    dot = Digraph(comment='Diagrama de Fluxo - room_conditioner')

    # Nós principais
    dot.node('S', 'Início')
    dot.node('A', 'Obter variáveis necessárias')
    dot.node('B', 'Pessoas na sala?')
    dot.node('C', 'Obter variáveis adicionais')
    dot.node('D', 'AC ultrapassou tempo limite?')
    dot.node('E', 'Desligar AC')
    dot.node('F', 'Temperatura externa adequada?')
    dot.node('G', 'Ajustar janela e velocidade')
    dot.node('H', 'Fechar janela')
    dot.node('I', 'Janela fechada?')
    dot.node('J', 'Ajustar velocidade e ligar AC')
    dot.node('K', 'Ajustar temperatura do AC')
    dot.node('L', 'CO2 acima do limite?')
    dot.node('M', 'Ligar DOAS')
    dot.node('N', 'Calcular PMV e atualizar atuadores')
    dot.node('O', 'Verificar conforto térmico')
    dot.node('P', 'Pessoas ausentes - Ajustar janelas')
    dot.node('Q', 'Desligar sistemas')
    dot.node('R', 'Atualizar valores adaptativos')
    dot.node('T', 'Fim')

    # Ligações
    dot.edge('S', 'A')
    dot.edge('A', 'B')
    dot.edge('B', 'C', label='Sim')
    dot.edge('B', 'P', label='Não')
    dot.edge('C', 'D')
    dot.edge('D', 'E', label='Sim')
    dot.edge('D', 'F', label='Não')
    dot.edge('E', 'F')
    dot.edge('F', 'G', label='Sim')
    dot.edge('F', 'H', label='Não')
    dot.edge('G', 'I')
    dot.edge('H', 'I')
    dot.edge('I', 'J', label='Sim')
    dot.edge('I', 'K', label='Não')
    dot.edge('J', 'K')
    dot.edge('K', 'L')
    dot.edge('L', 'M', label='Sim')
    dot.edge('L', 'N', label='Não')
    dot.edge('M', 'N')
    dot.edge('N', 'O')
    dot.edge('O', 'R')
    dot.edge('P', 'Q')
    dot.edge('Q', 'R')
    dot.edge('R', 'T')

    # Renderiza e salva o arquivo
    dot.render('room_conditioner_flowchart', format='png', cleanup=True)


# Executa a geração do diagrama
generate_flowchart()
