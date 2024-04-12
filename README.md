# Simulações Personalizadas com EnergyPlus e Python

Aplicação sendo desenvolvida para gestão do conforto térmico do usuário e otimização energética por meio de simulações no EnergyPlus utilizando Python no âmbito do projeto do confortímetro Klimaa na Universidade Federal de Pelotas

![User Interface](/resources/images/UI.png)

## Como executar

- Instale o pacote `poetry` do Python: `pip install poetry`

### Automaticamente

- Caso esteja no Windows execute o `SimulacoesPersonalizas.bat`
- Caso esteja no Linux ou MacOS execute o `SimulacoesPersonalizadas.sh`

### Manualmente

- Instale as dependências da aplicação: `poetry install`

- Execute a aplicação: `poetry run python src/app.py`

## Tecnologias utilizadas

- EnergyPlus
- Python
- Pandas
- Eppy
- Tkinter