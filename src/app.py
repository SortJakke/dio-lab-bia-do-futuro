import pandas as pd
import json

import streamlit as st
import requests

# # Configuração
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma4:31b-cloud"

# # Carregar Dados
history = pd.read_csv('data/historico_atendimento.csv')
transactions = pd.read_csv('data/transacoes.csv')

profile = json.load(open('./data/perfil_investidor.json'))
products = json.load(open('./data/produtos_financeiros.json'))

# # Montar Contexto
context = f"""
CLIENTE: {profile["nome"]}, {profile["idade"]} anos, perfil {profile["perfil_investidor"]}
OBJETIVO: {profile["objetivo_principal"]}
PATRIMONIO: R$ {profile["patrimonio_total"]} | RESERVA: R$ {profile["reserva_emergencia_atual"]}

TRANSAÇÕES RECENTES:
{transactions.to_string(index=False)}

ATENDIMENTOS ANTERIORES:
{history.to_string(index=False)}

PRODUTOS DISPONÍVEIS:
{json.dumps(products, indent=2, ensure_ascii=False)}
"""

# # SYSTEM PROMPT
SYSTEM_PROMPT = """Você é o Edu, um educador financeiro amigavel e didático.

OBJETIVO:
Ensinar conceitos de finanças pessoais de forma simples, usando os dados do cliente como exemplos práticos.

REGRAS:
1. Limite o escopo da conversa à conhecimentos financeiros
2. NUNCA recomende investimentos específicos - apenas explique como funcionam
3. Use os dados fornecidos para dar exemplos personalizados
4. Linguagem simples, como se explicasse para um amigo
5. Se não souber algo, admita: "Não tenho essa informação, mas posso explicar..."
6. Sempre pergunte se o cliente entendeu

"""

# # Chamar OLLAMA
def toAsk(msg):
  prompt = f"""
  {SYSTEM_PROMPT}

  CONTEXTO DO CLIENTE:
  {context}

  PERGUNTA: {msg} 
  """

  r = requests.post(OLLAMA_URL, json={"model": MODEL, "prompt": prompt, "stream": False})
  return r.json()['response']

# # Interface
st.title("Edu, Seu Educador Financeiro")

if ask := st.chat_input("Sua dúvida sobre finanças..."):
  st.chat_message("user").write(ask)
  with st.spinner("..."):
    st.chat_message("assistant").write(toAsk(ask))