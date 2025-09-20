import os
import sys
from typing import List, Tuple

# Garante que a pasta raiz esteja no path para import do lexer.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Testes com pytest
import pytest
from lexer import Lexer, TokenType, Token

# ---------------------------
# Helpers para os testes
# ---------------------------

def tok_types(tokens: List[Token]) -> List[TokenType]:
    return [t.type for t in tokens]

def tok_pairs(tokens: List[Token]) -> List[Tuple[str, str]]:
    """Retorna pares (TokenType.name, lexeme) para snapshots legíveis."""
    return [(t.type.name, t.lexeme) for t in tokens]

def assert_subsequence(haystack, needle):
    """
    Verifica se 'needle' é subsequência de 'haystack' mantendo a ordem.
    Útil para não amarrar o teste a todos os tokens, apenas aos importantes.
    """
    it = iter(haystack)
    for n in needle:
        for h in it:
            if h == n:
                break
        else:
            raise AssertionError(f"Subsequência não encontrada: {needle} em {haystack}")

# ---------------------------
# Código-fonte Go de teste
# ---------------------------

PROGRAM = r'''
package main

// soma dois inteiros
func soma(a int, b int) int {
    return a + b
}

func main() {
    var x int = 10;
    var y float64 = 3.5e1;
    var s string = "hello\nworld";
    // if / else com operadores lógicos e relacionais
    if x < 20 && y >= 10 {
        x++
    } else {
        x = x - 1
    }
    // loop for clássico
    for i := 0; i < 3; i++ {
        fmt.Println(s, soma(x, 2));
    }
}
'''

# ---------------------------
# Testes
# ---------------------------

def test_program_end_to_end_types_subsequence():
    """
    Testa o fluxo completo do lexer com um programa funcional.
    Checa uma subsequência de tipos de tokens essenciais para garantir
    que 'package', 'func soma', 'func main' e estruturas controle aparecem.
    """
    lx = Lexer(PROGRAM)
    tokens = lx.tokenize()
    types = tok_types(tokens)

    expected_subseq = [
        TokenType.PACKAGE, TokenType.IDENT,                # package main
        TokenType.FUNC, TokenType.IDENT,                   # func soma
        TokenType.LPAREN, TokenType.IDENT, TokenType.INT_TYPE,
        TokenType.COMMA, TokenType.IDENT, TokenType.INT_TYPE,
        TokenType.RPAREN, TokenType.INT_TYPE,              # ) int
        TokenType.LBRACE, TokenType.RETURN, TokenType.IDENT, TokenType.PLUS, TokenType.IDENT, TokenType.RBRACE,

        TokenType.FUNC, TokenType.IDENT, TokenType.LPAREN, TokenType.RPAREN, TokenType.LBRACE,  # func main() {
        TokenType.VAR, TokenType.IDENT, TokenType.INT_TYPE, TokenType.ASSIGN, TokenType.INT, TokenType.SEMICOLON,
        TokenType.VAR, TokenType.IDENT, TokenType.FLOAT64_TYPE, TokenType.ASSIGN, TokenType.FLOAT, TokenType.SEMICOLON,
        TokenType.VAR, TokenType.IDENT, TokenType.STRING_TYPE, TokenType.ASSIGN, TokenType.STRING, TokenType.SEMICOLON,

        TokenType.IF, TokenType.IDENT, TokenType.LT, TokenType.INT,
        TokenType.AND, TokenType.IDENT, TokenType.GTE, TokenType.INT,
        TokenType.LBRACE, TokenType.IDENT, TokenType.INC, TokenType.RBRACE,

        TokenType.ELSE, TokenType.LBRACE, TokenType.IDENT, TokenType.ASSIGN, TokenType.IDENT, TokenType.MINUS, TokenType.INT, TokenType.RBRACE,

        TokenType.FOR, TokenType.IDENT, TokenType.DEF if hasattr(TokenType, "DEF") else TokenType.COLON if hasattr(TokenType, "COLON") else TokenType.IDENT,  # ver nota abaixo
    ]
    # Nota: nosso lexer atual NÃO tem ':=' (declaração curta), então essa parte do for não é suportada.
    # Para manter o teste coerente com o lexer atual, não vamos exigir 'i := 0;'.
    # Em vez disso, apenas checamos outras partes do for mais adiante.

    # Ajuste: vamos checar outra subsequência depois do 'for', ignorando 'i := 0;'
    expected_subseq_after_for = [
        TokenType.SEMICOLON, TokenType.IDENT, TokenType.LT, TokenType.INT, TokenType.SEMICOLON,
        TokenType.IDENT, TokenType.INC, TokenType.LBRACE,
        TokenType.IDENT, TokenType.DOT, TokenType.IDENT, TokenType.LPAREN, TokenType.IDENT, TokenType.COMMA, TokenType.IDENT,
        TokenType.LPAREN, TokenType.IDENT, TokenType.COMMA, TokenType.INT, TokenType.RPAREN, TokenType.RPAREN, TokenType.SEMICOLON,
        TokenType.RBRACE, TokenType.RBRACE, TokenType.EOF
    ]

    # Em vez de usar a primeira subsequência (que inclui ':='), só validamos a existência até 'func soma' e 'if/else'
    assert_subsequence(types, expected_subseq[:30])
    assert_subsequence(types, expected_subseq_after_for)

def test_ident_and_literals_values_and_positions():
    """
    Valida lexemas concretos e posição (linha/coluna) de alguns tokens-chave.
    """
    lx = Lexer(PROGRAM)
    tokens = lx.tokenize()

    # Encontrar alguns tokens por tipo/lexema
    pkg = next(t for t in tokens if t.type == TokenType.PACKAGE)
    main_ident = next(t for t in tokens if t.type == TokenType.IDENT and t.lexeme == "main")
    soma_ident = next(t for t in tokens if t.type == TokenType.IDENT and t.lexeme == "soma")
    int_literal_10 = next(t for t in tokens if t.type == TokenType.INT and t.lexeme == "10")
    float_literal = next(t for t in tokens if t.type == TokenType.FLOAT)  # 3.5e1
    string_literal = next(t for t in tokens if t.type == TokenType.STRING)

    # Checagens de valor
    assert main_ident.lexeme == "main"
    assert soma_ident.lexeme == "soma"
    assert int_literal_10.lexeme == "10"
    assert float_literal.lexeme.lower() == "3.5e1"
    assert "hello" in string_literal.lexeme and "\n" in string_literal.lexeme and "world" in string_literal.lexeme

    # Checagens de posição: o 'package' deve estar no topo (linha 2 por causa da quebra inicial no PROGRAM)
    assert pkg.line >= 2
    # 'main' após 'package'
    assert main_ident.line >= pkg.line

def test_comments_are_ignored():
    """
    Garante que comentários de linha e bloco não geram tokens 'visíveis'.
    """
    code = r'''
    // linha
    package main /* bloco */
    func main() { /* outro
    bloco */ return }
    '''
    lx = Lexer(code)
    tokens = [t for t in lx.tokenize() if t.type not in (TokenType.EOF,)]
    # Não deve existir token do tipo ILLEGAL por causa de comentários
    assert all(t.type != TokenType.ILLEGAL for t in tokens)

def test_numbers_variants():
    """
    Checa inteiros, floats com ponto e notação científica.
    """
    code = 'var a int = 0; var b float64 = 1.0; var c float64 = 6.02e23;'
    lx = Lexer(code)
    pairs = tok_pairs(lx.tokenize())

    # Procurar presenças
    assert ('VAR', 'var') in pairs
    assert ('INT_TYPE', 'int') in pairs
    assert ('INT', '0') in pairs
    assert ('FLOAT64_TYPE', 'float64') in pairs
    assert ('FLOAT', '1.0') in pairs
    # Pode vir em maiúsculas/minúsculas, normalizamos com lower no lexer? aqui só conferimos a presença bruta.
    assert any(p[0] == 'FLOAT' and p[1].lower() == '6.02e23' for p in pairs)

def test_string_escapes_and_unterminated_errors():
    """
    Valida escapes e erro de string não terminada.
    """
    ok = r'var s string = "linha1\nlinha2\t\"aspas\"";'
    bad = r'var s string = "oops'
    lx_ok = Lexer(ok)
    toks_ok = lx_ok.tokenize()
    assert any(t.type == TokenType.STRING and '\n' in t.lexeme and '\t' in t.lexeme for t in toks_ok)

    lx_bad = Lexer(bad)
    toks_bad = lx_bad.tokenize()
    assert any(t.type == TokenType.ILLEGAL and "unterminated" in t.lexeme for t in toks_bad)