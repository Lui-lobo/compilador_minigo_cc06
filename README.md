# 📝 Mini-Go Compiler

## 👨‍💻 Membros Do Projeto
- Luiz Henrique Carvalhas Lobo de Oliveira - RA: 2301293 - CC06
- Johnathan Silva Francisco - RA: 2301490 - CC06
- Enzo Tavares Lula Silva - RA: 2301843 - CC06
- Abner Israel Sanches de Oliveira - RA: 2300152 - CC06
- Lucas Araújo Andrade Morais - RA: 2300734 - CC06

## 📌 Sobre o projeto
Este projeto implementa um **compilador educacional** em **Python** para um **subconjunto da linguagem Go (Mini-Go)**.  
O objetivo é demonstrar de forma prática como funcionam as etapas clássicas de um compilador:

1. **Análise Léxica** → converte o código-fonte em **tokens**.  
2. **Análise Sintática (Parser)** → valida a estrutura do programa e gera uma **AST (Árvore Sintática Abstrata)**.  
3. **Relato de erros** → exibe tanto **erros léxicos** (tokens inválidos) quanto **erros sintáticos** (estrutura incorreta).  

---

## ⚡ Features implementadas até o momento
- ✅ **Lexer**
  - Reconhecimento de identificadores e literais (`int`, `float`, `string`, `bool`).
  - Palavras-chave: `package`, `func`, `var`, `return`, `if`, `else`, `for`, `true`, `false`, tipos primitivos.
  - Operadores: `+`, `-`, `*`, `/`, `:=`, `==`, `!=`, `<=`, `>=`, `++`, `--`, `&&`, `||` e outros.
  - Registro de **erros léxicos** (caracteres inesperados, strings mal formadas, números inválidos).

- ✅ **Parser**
  - Estrutura de programas iniciando com `package main`.
  - Declarações de funções e variáveis.
  - Statements suportados: `if/else`, `for` (3 formas), `return`, `var`, expressões.
  - Declarações curtas (`:=`) com inferência de tipo (posterior no semântico).
  - Construção da **AST**.
  - Relato de **erros sintáticos** com linha e coluna.

- ✅ **AST**
  - Nós para literais, operadores, atribuições, chamadas de função, seletores (`fmt.Println`), blocos, funções e controle de fluxo.

- ✅ **CLI**
  - `--parse` → executa parser e imprime AST em JSON.  
  - `--check` → imprime tokens e, em seguida, erros sintáticos (ou “Não há erros sintáticos”).  
  - `--json` → saída de tokens em JSON.  
  - `--no-ansi` → desativa cores ANSI.  
  - Suporte a entrada via arquivo (`--file`) ou código inline (`--code`).  

---

## 📂 Estrutura do projeto
compilador_impacta/
│
├── lexer.py # Analisador léxico
├── parser.py # Analisador sintático
├── go_ast.py # Definições da AST
├── main.py # CLI principal
├── tests/ # Testes automatizados
│ └── test_lexer.py, test_parser.py ...
└── examples/ # Exemplos de códigos Mini-Go

## ▶️ Como executar

### 1. Instalar dependências (Etapa opcional, não é necessário baixar a biblioteca de testes para rodar o projeto)
O projeto usa apenas bibliotecas padrão do Python (≥ 3.9).  
Para rodar os testes:
```bash
pip install pytest
```

### 2. Rodar lexer + verificação sintática
```bash
python main.py  -f examples/example_ap01_teste01.go --check
```

### 3. Rodar somente o lexer (somente tokens)
```bash
python main.py -f examples/example_ap01_teste01.go
```

### 4. Rodar o parser (AST em JSON)
```bash
python main.py -f examples/ex01.go --parse
```
