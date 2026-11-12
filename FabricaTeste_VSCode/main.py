"""Data Discovery MVP: identifica/classifica metadados de colunas SQLite.

Os valores de amostra são processados localmente. Somente metadados e
estatísticas agregadas são enviados ao Gemini, quando a API estiver configurada.
"""

from __future__ import annotations

import json
import random
import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent
DB = BASE_DIR / "empresa_teste.db"
RELATORIO = BASE_DIR / "relatorio_data_discovery.csv"

load_dotenv(BASE_DIR / ".env")


def criar_banco(db_path: Path = DB) -> None:
    """Cria o banco fictício usado na demonstração."""
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("PRAGMA foreign_keys = ON")
    cur.executescript("""
    DROP TABLE IF EXISTS pedidos;
    DROP TABLE IF EXISTS funcionarios;
    DROP TABLE IF EXISTS produtos;
    DROP TABLE IF EXISTS clientes;

    CREATE TABLE clientes (
        id INTEGER PRIMARY KEY,
        nome TEXT,
        cpf TEXT,
        email TEXT,
        telefone TEXT,
        data_nascimento TEXT,
        cidade TEXT
    );

    CREATE TABLE funcionarios (
        id INTEGER PRIMARY KEY,
        nome TEXT,
        cargo TEXT,
        salario REAL,
        email_corporativo TEXT,
        cpf TEXT
    );

    CREATE TABLE produtos (
        id INTEGER PRIMARY KEY,
        nome_produto TEXT,
        preco REAL,
        estoque INTEGER,
        categoria TEXT
    );

    CREATE TABLE pedidos (
        id INTEGER PRIMARY KEY,
        cliente_id INTEGER,
        produto_id INTEGER,
        valor REAL,
        data_pedido TEXT,
        FOREIGN KEY(cliente_id) REFERENCES clientes(id),
        FOREIGN KEY(produto_id) REFERENCES produtos(id)
    );
    """)

    nomes = [
        "Pessoa Alfa", "Pessoa Beta", "Pessoa Gama", "Pessoa Delta",
        "Pessoa Épsilon", "Pessoa Zeta", "Pessoa Eta", "Pessoa Teta",
        "Pessoa Iota", "Pessoa Kappa"
    ]
    cidades = ["Marília", "Bauru", "Campinas", "Londrina", "Curitiba"]
    cargos = ["Analista", "Desenvolvedor", "Gerente", "Designer", "Suporte"]

    def cpf_ficticio(i: int) -> str:
        # Formato semelhante a CPF, mas os valores são sintéticos.
        return f"{100+i:03d}.{200+i:03d}.{300+i:03d}-{10+i:02d}"

    for i, nome in enumerate(nomes, 1):
        cur.execute("INSERT INTO clientes VALUES (?,?,?,?,?,?,?)", (
            i, nome, cpf_ficticio(i), f"pessoa{i}@exemplo.test",
            f"(11) 90000-{1000+i:04d}",
            str(date(1985, 1, 1) + timedelta(days=i * 503)),
            random.choice(cidades)
        ))

    for i in range(1, 7):
        cur.execute("INSERT INTO funcionarios VALUES (?,?,?,?,?,?)", (
            i, f"Funcionario {i}", random.choice(cargos),
            round(random.uniform(2500, 11000), 2),
            f"func{i}@empresa.test", cpf_ficticio(20+i)
        ))

    produtos = [
        ("Notebook", 4200, 12, "Tecnologia"),
        ("Mouse", 120, 55, "Tecnologia"),
        ("Cadeira", 900, 8, "Escritório"),
        ("Monitor", 1350, 18, "Tecnologia")
    ]
    for i, produto in enumerate(produtos, 1):
        cur.execute("INSERT INTO produtos VALUES (?,?,?,?,?)", (i, *produto))

    for i in range(1, 21):
        pid = random.randint(1, 4)
        preco = produtos[pid - 1][1]
        cur.execute("INSERT INTO pedidos VALUES (?,?,?,?,?)", (
            i, random.randint(1, 10), pid, preco,
            str(date.today() - timedelta(days=random.randint(1, 180)))
        ))

    con.commit()
    con.close()
    print(f"Banco fictício criado: {db_path}")


def descobrir_schema(db_path: Path = DB) -> dict[str, dict[str, Any]]:
    con = sqlite3.connect(db_path)
    tabelas = pd.read_sql_query(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%'", con
    )["name"].tolist()
    schema: dict[str, dict[str, Any]] = {}
    for tabela in tabelas:
        info = pd.read_sql_query(f'PRAGMA table_info("{tabela}")', con)
        fks = pd.read_sql_query(f'PRAGMA foreign_key_list("{tabela}")', con)
        schema[tabela] = {
            "colunas": info[["name", "type", "pk"]].to_dict("records"),
            "foreign_keys": fks.to_dict("records")
        }
    con.close()
    return schema


def features_coluna(
    con: sqlite3.Connection, tabela: str, coluna: str, limite: int = 30
) -> dict[str, Any]:
    nome_seguro = tabela.replace('"', '""')
    col_segura = coluna.replace('"', '""')
    rows = con.execute(
        f'SELECT "{col_segura}" FROM "{nome_seguro}" '
        f'WHERE "{col_segura}" IS NOT NULL LIMIT ?', (limite,)
    ).fetchall()
    vals = [r[0] for r in rows]
    textos = [str(v) for v in vals]

    def taxa(pred) -> float:
        return round(sum(bool(pred(v)) for v in textos) / max(len(textos), 1), 2)

    return {
        "quantidade_amostrada": len(vals),
        "taxa_email": taxa(lambda x: re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", x) is not None),
        "taxa_formato_cpf": taxa(lambda x: re.fullmatch(r"\d{3}\.\d{3}\.\d{3}-\d{2}", x) is not None),
        "taxa_telefone": taxa(lambda x: re.fullmatch(r"[(]?\d{2}[)]?\s?\d{4,5}-?\d{4}", x) is not None),
        "taxa_data_iso": taxa(lambda x: re.fullmatch(r"\d{4}-\d{2}-\d{2}", x) is not None),
        "taxa_numerico": round(sum(isinstance(v, (int, float)) for v in vals) / max(len(vals), 1), 2),
        "media_tamanho_texto": round(sum(map(len, textos)) / max(len(textos), 1), 1)
    }


def calcular_features(schema: dict[str, dict[str, Any]], db_path: Path = DB):
    con = sqlite3.connect(db_path)
    features = {}
    for tabela, dados in schema.items():
        features[tabela] = {}
        for coluna in dados["colunas"]:
            nome = coluna["name"]
            features[tabela][nome] = features_coluna(con, tabela, nome)
    con.close()
    return features


def classificar_local(nome: str, tipo_sql: str, f: dict[str, Any]):
    n = nome.lower()
    if f["taxa_formato_cpf"] >= .7 or "cpf" in n:
        return "PESSOAL", "CPF", .99
    if f["taxa_email"] >= .7 or "email" in n:
        return "PESSOAL", "E-MAIL", .98
    if f["taxa_telefone"] >= .7 or any(x in n for x in ["telefone", "celular"]):
        return "PESSOAL", "TELEFONE", .97
    if "salario" in n or "renda" in n:
        return "FINANCEIRO", "RENDA/SALÁRIO", .96
    if n == "nome" or n.endswith("_nome"):
        return "PESSOAL", "NOME", .90
    if "nascimento" in n:
        return "PESSOAL", "DATA DE NASCIMENTO", .94
    if "cidade" in n or "endereco" in n or "cep" in n:
        return "PESSOAL", "LOCALIZAÇÃO/ENDEREÇO", .82
    if n.endswith("_id") or n == "id":
        return "COMUM", "IDENTIFICADOR TÉCNICO", .86
    if any(x in n for x in ["valor", "preco"]):
        return "FINANCEIRO", "VALOR MONETÁRIO", .85
    return "COMUM", "OUTRO", .70


def classificar_gemini(tabela: str, coluna: str, tipo_sql: str, feat: dict[str, Any]):
    """Usa o SDK atual google-genai; se falhar, retorna o detector local."""
    local = classificar_local(coluna, tipo_sql, feat)
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return local

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        payload = {
            "tabela": tabela,
            "coluna": coluna,
            "tipo_sql": tipo_sql,
            "caracteristicas_anonimizadas": feat,
            "sugestao_detector_local": {
                "categoria": local[0], "tipo": local[1], "confianca": local[2]
            }
        }
        prompt = (
            "Você classifica metadados de banco para data discovery. "
            "Não há valores reais no conteúdo recebido. Retorne somente JSON com "
            "categoria (COMUM|PESSOAL|SENSÍVEL|FINANCEIRO|COMPORTAMENTAL), "
            "tipo (descrição curta em maiúsculas) e confianca (número de 0 a 1). "
            "Use tabela, coluna, tipo SQL, características e detector local.\n\n"
            + json.dumps(payload, ensure_ascii=False)
        )
        resposta = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        obj = json.loads(resposta.text)
        categoria = str(obj["categoria"]).upper()
        tipo = str(obj["tipo"]).upper()
        confianca = max(0.0, min(1.0, float(obj["confianca"])))
        categorias_validas = {"COMUM", "PESSOAL", "SENSÍVEL", "FINANCEIRO", "COMPORTAMENTAL"}
        if categoria not in categorias_validas:
            return local
        return categoria, tipo, confianca
    except Exception as erro:
        print(f"Aviso: Gemini indisponível para {tabela}.{coluna}; usando classificador local. ({erro})")
        return local


def executar_data_discovery() -> pd.DataFrame:
    if not DB.exists():
        criar_banco()

    schema = descobrir_schema()
    features = calcular_features(schema)
    total = sum(len(x["colunas"]) for x in schema.values())
    print("\nDATA DISCOVERY")
    print(f"{len(schema)} tabelas e {total} colunas encontradas.")
    print("Classificando colunas...\n")

    resultados = []
    for tabela, dados in schema.items():
        for coluna in dados["colunas"]:
            nome = coluna["name"]
            categoria, tipo, confianca = classificar_gemini(
                tabela, nome, coluna["type"], features[tabela][nome]
            )
            resultados.append({
                "Tabela": tabela,
                "Coluna": nome,
                "Tipo SQL": coluna["type"],
                "Categoria": categoria,
                "Dado identificado": tipo,
                "Confiança": round(confianca * 100, 1)
            })

    df = pd.DataFrame(resultados)
    print(df.to_string(index=False))
    df.to_csv(RELATORIO, index=False, encoding="utf-8-sig")
    print(f"\nRelatório salvo em: {RELATORIO}")
    print("Nenhum valor amostrado foi incluído no relatório.")
    return df


def mostrar_contagem_registros() -> None:
    with sqlite3.connect(DB) as con:
        for tabela in ["clientes", "funcionarios", "produtos", "pedidos"]:
            quantidade = pd.read_sql_query(
                f"SELECT COUNT(*) AS total FROM {tabela}", con
            )["total"].iloc[0]
            print(f"{tabela}: {quantidade} registros")


if __name__ == "__main__":
    executar_data_discovery()
    print("\nContagem de registros:")
    mostrar_contagem_registros()
