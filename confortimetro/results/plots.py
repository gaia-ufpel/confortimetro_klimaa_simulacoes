"""Gráficos exploratórios das planilhas de resultado."""

import matplotlib.pyplot as plt
import pandas

def plot_graphics(excel_path, sheet_name):
    """
    Cria gráficos para temperatura externa, temperaturas do adaptativo, pmv, temperatura operativa a partir de um arquivo .excel com várias tabelas com os períodos de verão, inverno, dias de verão e dias de inverno.
    """

    df = pandas.read_excel(excel_path, sheet_name=sheet_name)

    # Cria uma figura
    fig = plt.figure(figsize=(30, 10))
    fig.suptitle("Gráficos de Temperatura", fontsize=16)
    
    # Cria um gráfico geral
    ax = fig.add_subplot(111)

    # Plota a linha da temperatura externa
    ax.plot(df["Date/Time"], df["Site Outdoor Air Drybulb Temperature"], label="Temperatura Externa", color="red")

    # Plota a linha da temperatura do adaptativo
    ax.plot(df["Date/Time"], df["ADAP_MIN_ATELIE1:Schedule Value"], label="Temperatura Mínima do Adaptativo", color="blue")
    ax.plot(df["Date/Time"], df["ADAP_MAX_ATELIE1:Schedule Value"], label="Temperatura Máxima do Adaptativo", color="blue")

    # Plota a linha da temperatura operativa
    ax.plot(df["Date/Time"], df["ATELIE1:Zone Operative Temperature"], label="Temperatura Operativa", color="green")

    # Mostra os labels
    plt.legend()
    plt.grid()

    plt.show()
