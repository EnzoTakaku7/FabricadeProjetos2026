# FabricaTeste — Data Discovery + Vanna/Gemini

Migração do notebook Google Colab para um projeto Python executável no VS Code.

## O que foi mantido

- Criação do banco SQLite fictício `empresa_teste.db`.
- Descoberta automática de tabelas, colunas e chaves estrangeiras.
- Amostragem local e cálculo de características sem enviar valores individuais ao modelo.
- Classificador local como fallback.
- Relatório CSV sem valores pessoais de amostra.

## O que foi atualizado

- Removidos os caminhos `/content` do Colab; os arquivos ficam na pasta do projeto.
- A classificação por LLM usa o SDK atual `google-genai` e Gemini.
- A integração Vanna foi atualizada para a arquitetura Vanna 2.x (`Agent`, `GeminiLlmService`, `SqliteRunner` e `RunSqlTool`).
- A memória vetorial do Vanna usa Chroma local em `chroma_memory/`.
- A chave fica em `.env`, fora do código e ignorada pelo Git.

## Requisitos

- Python 3.10 ou superior (recomendado: Python 3.11 ou 3.12).
- Uma chave da Gemini API criada no Google AI Studio: https://aistudio.google.com/apikey

## Configuração no VS Code (Windows)

Abra esta pasta no VS Code e, no terminal integrado, execute:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Se o PowerShell bloquear a ativação do ambiente virtual, você pode executar os comandos com o Python do ambiente diretamente ou ajustar a política de execução do seu usuário.

Copie `.env.example` para `.env` e substitua `sua_chave_gemini_aqui` pela chave obtida no Google AI Studio.

## Executar o Data Discovery

```powershell
python main.py
```

Na primeira execução, o programa cria o banco fictício, classifica as colunas e salva `relatorio_data_discovery.csv`.

Sem chave Gemini válida, o programa continua com o classificador local. Com a chave configurada, envia ao Gemini somente nomes de tabela/coluna, tipo SQL e estatísticas agregadas; não envia os valores lidos na amostra.

## Executar a interface Vanna

Primeiro execute `python main.py` para criar o banco. Depois:

```powershell
python vanna_app.py
```

O Vanna 2.x inicia uma interface/servidor local e informa no terminal o endereço para abrir no navegador.

## Observações de segurança

- Não compartilhe o arquivo `.env` nem publique sua chave.
- O banco gerado é fictício e serve apenas para demonstração.
- O Vanna recebe permissão para executar SQL no banco configurado. Use somente com este banco de teste e não exponha o servidor publicamente sem implementar autenticação, autorização e restrições de consultas.
- O CSV contém nomes de tabelas/colunas e classificações, não os valores das linhas.
