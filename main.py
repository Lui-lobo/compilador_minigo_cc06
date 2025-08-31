# main.py
from __future__ import annotations
import argparse
import json
import os
import sys
from typing import Iterable, Dict, Any
# Imports e libs referentes ao parser (Analisador Sintatico)
from parser import Parser
# certo: importa o seu módulo renomeado
import go_ast as A
import json


# Garante import local (executando de dentro do projeto)
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from lexer import Lexer, TokenType, Token  # noqa: E402

# --------- utilidades de exibição ---------

def escape_lexeme(s: str, max_len: int = 60) -> str:
    """Mostra \n, \t, \r e aspas, e corta lexemas muito longos."""
    repl = (
        ("\\", "\\\\"),
        ("\n", "\\n"),
        ("\t", "\\t"),
        ("\r", "\\r"),
        ("\"", "\\\""),
    )
    for a, b in repl:
        s = s.replace(a, b)
    if len(s) > max_len:
        s = s[:max_len - 3] + "..."
    return f"\"{s}\""

def color(text: str, code: str, use_color: bool) -> str:
    return f"\x1b[{code}m{text}\x1b[0m" if use_color else text

def token_to_dict(t: Token) -> Dict[str, Any]:
    return {
        "type": t.type.name,
        "lexeme": t.lexeme,
        "line": t.line,
        "column": t.column,
    }

def print_table(tokens: Iterable[Token], use_color: bool):
    # cabeçalho
    idx_hdr = color("#", "2", use_color)
    pos_hdr = color("pos", "2", use_color)
    typ_hdr = color("type", "2", use_color)
    lex_hdr = color("lexeme", "2", use_color)
    print(f"{idx_hdr:>4}  {pos_hdr:>8}  {typ_hdr:>15}  {lex_hdr}")

    count = 0
    errors = 0
    for i, t in enumerate(tokens):
        count += 1
        pos = f"{t.line}:{t.column}"
        tname = t.type.name
        lex = escape_lexeme(t.lexeme)

        # destaca erros
        if t.type == TokenType.ILLEGAL:
            tname = color(tname, "31;1", use_color)  # vermelho
            lex = color(lex, "31", use_color)
            errors += 1
        elif t.type == TokenType.EOF:
            tname = color(tname, "36", use_color)    # ciano

        print(f"{i:>4}  {pos:>8}  {tname:>15}  {lex}")

    # resumo
    print()
    summary = f"{count} tokens, {errors} erro(s)"
    if errors:
        summary = color(summary, "31;1", use_color)
    else:
        summary = color(summary, "32;1", use_color)
    print(summary)

def print_json(tokens: Iterable[Token]):
    data = [token_to_dict(t) for t in tokens]
    print(json.dumps(data, ensure_ascii=False, indent=2))

def ast_to_dict(node):
    if node is None:
        return None
    if isinstance(node, (str, int, float, bool)):
        return node
    if isinstance(node, list):
        return [ast_to_dict(x) for x in node]
    if hasattr(node, "__dict__"):
        d = {}
        for k, v in node.__dict__.items():
            d[k] = ast_to_dict(v)
        d["__class__"] = node.__class__.__name__
        return d
    return str(node)

# --------- CLI ---------

def main():
    ap = argparse.ArgumentParser(
        description="Mini-Go: lexer, parser e verificações."
    )
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("-f", "--file", help="Caminho para arquivo .go a ser lido.")
    src.add_argument("-c", "--code", help="Código-fonte inline (string).")

    # Modo AST (parser completo → imprime AST)
    ap.add_argument(
        "--parse",
        action="store_true",
        help="Faz parsing e imprime a AST (JSON)."
    )
    # Modo tokens (atual)
    ap.add_argument(
        "--json",
        action="store_true",
        help="(modo lexer) Saída em JSON em vez de tabela."
    )
    ap.add_argument(
        "--no-ansi",
        action="store_true",
        help="(modo lexer) Desativa cores ANSI."
    )
    # 👉 Novo modo: imprime tokens e, em seguida, checa erros sintáticos
    ap.add_argument(
        "--check",
        action="store_true",
        help="Imprime os tokens e, em seguida, executa o parser reportando erros sintáticos."
    )

    args = ap.parse_args()

    # 1) Obter o source primeiro (independente do modo)
    if args.file:
        with open(args.file, "r", encoding="utf-8") as fh:
            source = fh.read()
    else:
        source = args.code or ""

    # 2) Modo AST (continua igual)
    if args.parse:
        p = Parser(Lexer(source))
        prog = p.parse_program()

        # Erros léxicos
        if p.lexer.errors:
            print("Erros léxicos:")
            for e in p.lexer.errors:
                print("  -", e)

        # Erros sintáticos
        if p.errors:
            print("Erros sintáticos:")
            for e in p.errors:
                print(f"  - [{e.line}:{e.column}] {e.message}")
        else:
            print("Não há erros sintáticos.")

        # AST em JSON (se existir)
        if prog:
            print(json.dumps(ast_to_dict(prog), ensure_ascii=False, indent=2))
        return

    # 3) Novo modo: --check  (lexer + relatório sintático)
    if args.check:
        # 3.1) Primeiro: imprimir tokens como no modo lexer
        lx = Lexer(source)
        tokens = lx.tokenize()
        if args.json:
            print_json(tokens)
        else:
            print_table(tokens, use_color=not args.no_ansi)

        # 3.2) Reportar erros léxicos, se houver
        if lx.errors:
            print("\nErros léxicos encontrados:")
            for e in lx.errors:
                print("  -", e)

        # 3.3) Em seguida: rodar o parser e relatar erros sintáticos
        p = Parser(Lexer(source))
        _ = p.parse_program()

        if p.errors:
            print("\nErros sintáticos:")
            for e in p.errors:
                print(f"  - [{e.line}:{e.column}] {e.message}")
        else:
            print("\nNão há erros sintáticos.")
        return

    # 4) Modo lexer “puro” (comportamento atual)
    lx = Lexer(source)
    tokens = lx.tokenize()

    if args.json:
        print_json(tokens)
    else:
        print_table(tokens, use_color=not args.no_ansi)

    if lx.errors:
        print("\nErros léxicos encontrados:")
        for e in lx.errors:
            print("  -", e)

if __name__ == "__main__":
    main()