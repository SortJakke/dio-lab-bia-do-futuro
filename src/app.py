import json
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

# =========================
# Configuração
# =========================
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma4:31b-cloud" 
REQUEST_TIMEOUT = 60  # segundos
MAX_TRANSACOES = 20  # evita estourar o contexto conforme o histórico cresce

DATA_DIR = Path("data")

SYSTEM_PROMPT = """Você é o Edu, um educador financeiro amigável e didático.

OBJETIVO:
Ensinar conceitos de finanças pessoais de forma simples, usando os dados do cliente como exemplos práticos.

REGRAS:
1. Limite o escopo da conversa a conhecimentos financeiros.
2. NUNCA recomende investimentos específicos - apenas explique como funcionam.
3. Use os dados fornecidos para dar exemplos personalizados.
4. Linguagem simples, como se explicasse para um amigo.
5. Se não souber algo, admita: "Não tenho essa informação, mas posso explicar..."
6. Sempre pergunte se o cliente entendeu.
"""


# =========================
# Carregamento de dados (cacheado — só roda uma vez por sessão)
# =========================
@st.cache_data(show_spinner=False)
def carregar_dados():
    """Carrega CSVs e JSONs do disco. Levanta erro claro se algo faltar."""
    try:
        history = pd.read_csv(DATA_DIR / "historico_atendimento.csv")
        transactions = pd.read_csv(DATA_DIR / "transacoes.csv")
        with open(DATA_DIR / "perfil_investidor.json", encoding="utf-8") as f:
            profile = json.load(f)
        with open(DATA_DIR / "produtos_financeiros.json", encoding="utf-8") as f:
            products = json.load(f)
    except FileNotFoundError as e:
        st.error(f"Arquivo de dados não encontrado: {e.filename}")
        st.stop()
    except json.JSONDecodeError as e:
        st.error(f"JSON inválido em um dos arquivos de dados: {e}")
        st.stop()

    return history, transactions, profile, products


@st.cache_data(show_spinner=False)
def montar_contexto(_history, _transactions, profile, products):
    """Monta o bloco de contexto textual. Cacheado para não remontar a cada mensagem."""
    transacoes_recentes = _transactions.tail(MAX_TRANSACOES)

    return f"""CLIENTE: {profile["nome"]}, {profile["idade"]} anos, perfil {profile["perfil_investidor"]}
OBJETIVO: {profile["objetivo_principal"]}
PATRIMONIO: R$ {profile["patrimonio_total"]} | RESERVA: R$ {profile["reserva_emergencia_atual"]}

TRANSAÇÕES RECENTES (últimas {len(transacoes_recentes)}):
{transacoes_recentes.to_string(index=False)}

ATENDIMENTOS ANTERIORES:
{_history.to_string(index=False)}

PRODUTOS DISPONÍVEIS:
{json.dumps(products, indent=2, ensure_ascii=False)}
"""


# =========================
# Chamada ao Ollama via /api/chat
# =========================
def montar_mensagens(contexto: str, historico_conversa: list, pergunta: str) -> list:
    """
    Monta a lista de mensagens no formato que /api/chat espera:
    [{"role": "system"|"user"|"assistant", "content": "..."}, ...]

    O contexto do cliente entra dentro do system prompt (é instrução de
    comportamento, não fala do usuário) — diferente da string manual que
    misturava tudo num único bloco de texto.
    """
    mensagens = [
        {
            "role": "system",
            "content": f"{SYSTEM_PROMPT}\n\nCONTEXTO DO CLIENTE:\n{contexto}",
        }
    ]

    # histórico real da conversa, cada turno com seu role original
    for m in historico_conversa:
        mensagens.append({"role": m["role"], "content": m["content"]})

    mensagens.append({"role": "user", "content": pergunta})
    return mensagens


def perguntar_ao_edu(pergunta: str, contexto: str, historico_conversa: list) -> str:
    """Envia a pergunta ao modelo via /api/chat, com o histórico como mensagens estruturadas."""
    mensagens = montar_mensagens(contexto, historico_conversa, pergunta)

    try:
        r = requests.post(
            OLLAMA_URL,
            json={"model": MODEL, "messages": mensagens, "stream": False},
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
    except requests.exceptions.ConnectionError:
        return "⚠️ Não consegui me conectar ao Ollama. Ele está rodando em `localhost:11434`?"
    except requests.exceptions.Timeout:
        return "⚠️ O modelo demorou demais para responder. Tente novamente."
    except requests.exceptions.HTTPError as e:
        return f"⚠️ Erro na API do Ollama: {e}"

    data = r.json()
    # /api/chat devolve {"message": {"role": "assistant", "content": "..."}, ...}
    # em vez de {"response": "..."} do /api/generate
    if "message" not in data or "content" not in data["message"]:
        return f"⚠️ Resposta inesperada da API: {data}"

    return data["message"]["content"]


# =========================
# Interface
# =========================
st.set_page_config(page_title="Edu | Educador Financeiro")
st.title("Edu - Educador Financeiro")

history, transactions, profile, products = carregar_dados()
contexto = montar_contexto(history, transactions, profile, products)

if "messages" not in st.session_state:
    st.session_state.messages = []

# Reexibe o histórico a cada rerun (senão ele "some" visualmente)
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

if pergunta := st.chat_input("Sua dúvida sobre finanças..."):
    st.session_state.messages.append({"role": "user", "content": pergunta})
    st.chat_message("user").write(pergunta)

    with st.spinner("Pensando..."):
        resposta = perguntar_ao_edu(pergunta, contexto, st.session_state.messages[:-1])

    st.session_state.messages.append({"role": "assistant", "content": resposta})
    st.chat_message("assistant").write(resposta)