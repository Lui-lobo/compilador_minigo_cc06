from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
import re
from typing import Optional, List, Tuple

# ----------------------------
# Definições de Tokens
# ----------------------------

class TokenType(Enum):
    # especiais
    EOF = auto()
    ILLEGAL = auto()

    # identificadores e literais
    IDENT = auto()
    INT = auto()
    FLOAT = auto()
    STRING = auto()

    # palavras-chave
    PACKAGE = auto()
    FUNC = auto()
    VAR = auto()
    RETURN = auto()
    IF = auto()
    ELSE = auto()
    FOR = auto()
    TRUE = auto()
    FALSE = auto()
    INT_TYPE = auto()
    FLOAT64_TYPE = auto()
    BOOL_TYPE = auto()
    STRING_TYPE = auto()

    # operadores
    DEFINE = auto()   # para :=
    ASSIGN = auto()       # =
    PLUS = auto()         # +
    MINUS = auto()        # -
    ASTERISK = auto()     # *
    SLASH = auto()        # /
    MOD = auto()          # %
    BANG = auto()         # !
    LT = auto()           # <
    GT = auto()           # >
    EQ = auto()           # ==
    NOT_EQ = auto()       # !=
    LTE = auto()          # <=
    GTE = auto()          # >=
    AND = auto()          # &&
    OR = auto()           # ||
    INC = auto()          # ++
    DEC = auto()          # --

    # pontuação
    COMMA = auto()        # ,
    SEMICOLON = auto()    # ;
    DOT = auto()          # .
    LPAREN = auto()       # (
    RPAREN = auto()       # )
    LBRACE = auto()       # {
    RBRACE = auto()       # }
    LBRACKET = auto()     # [
    RBRACKET = auto()     # ]

KEYWORDS = {
    "package": TokenType.PACKAGE,
    "func": TokenType.FUNC,
    "var": TokenType.VAR,
    "return": TokenType.RETURN,
    "if": TokenType.IF,
    "else": TokenType.ELSE,
    "for": TokenType.FOR,
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
    "int": TokenType.INT_TYPE,
    "float64": TokenType.FLOAT64_TYPE,
    "bool": TokenType.BOOL_TYPE,
    "string": TokenType.STRING_TYPE,
}

@dataclass
class Token:
    type: TokenType
    lexeme: str
    line: int
    column: int

# ----------------------------
# Lexer
# ----------------------------

_ESCAPE_SEQUENCES = {
    '"': '"',
    "\\": "\\",
    "n": "\n",
    "t": "\t",
    "r": "\r",
}

_FLOAT_RE = re.compile(
    r"""
    (?:
        (?:\d+\.\d*|\.\d+|\d+\.)   # parte fracionária com ponto
        (?:[eE][+\-]?\d+)?         # expoente opcional
      |
        \d+(?:[eE][+\-]?\d+)       # inteiro com expoente
    )
    """,
    re.VERBOSE,
)

_INT_RE = re.compile(r"\d+")

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

class Lexer:
    def __init__(self, source: str):
        self.src = source
        self.len = len(source)
        self.i = 0
        self.line = 1
        self.col = 1
        self.errors: List[str] = []   # << lista de erros léxicos

    def add_error(self, msg: str):
        """Registra um erro com linha e coluna atuais."""
        self.errors.append(f"[{self.line}:{self.col}] {msg}")

    # utilidades básicas
    def _eof(self) -> bool:
        return self.i >= self.len

    def _peek(self, k: int = 0) -> str:
        j = self.i + k
        if j < self.len:
            return self.src[j]
        return "\0"

    def _advance(self) -> str:
        ch = self._peek()
        self.i += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def _match(self, expected: str) -> bool:
        if self._peek() == expected:
            self._advance()
            return True
        return False

    def _skip_ws_and_comments(self):
        while not self._eof():
            ch = self._peek()
            # espaços e quebras
            if ch in " \t\r\n":
                self._advance()
                continue
            # comentários
            if ch == "/":
                if self._peek(1) == "/":
                    # linha
                    self._advance(); self._advance()
                    while not self._eof() and self._peek() != "\n":
                        self._advance()
                    continue
                if self._peek(1) == "*":
                    # bloco
                    self._advance(); self._advance()
                    while not self._eof():
                        if self._peek() == "*" and self._peek(1) == "/":
                            self._advance(); self._advance()
                            break
                        else:
                            self._advance()
                    continue
            break

    def _token(self, t: TokenType, lex: str, line: int, col: int) -> Token:
        return Token(t, lex, line, col)

    def _string(self) -> Token:
        start_line, start_col = self.line, self.col
        self._advance()  # consumir "
        buf = []
        while not self._eof():
            ch = self._advance()
            if ch == '"':
                return self._token(TokenType.STRING, "".join(buf), start_line, start_col)
            if ch == "\\":  # escape
                nxt = self._advance()
                if nxt in _ESCAPE_SEQUENCES:
                    buf.append(_ESCAPE_SEQUENCES[nxt])
                else:
                    self.add_error(f"escape inválido: \\{nxt}")
                    return self._token(TokenType.ILLEGAL, f"\\{nxt}", start_line, start_col)
            elif ch == "\n":
                self.add_error("string literal não terminada")
                return self._token(TokenType.ILLEGAL, "unterminated string", start_line, start_col)
            else:
                buf.append(ch)
        self.add_error("string literal não terminada no EOF")
        return self._token(TokenType.ILLEGAL, "unterminated string", start_line, start_col)

    def _number(self) -> Token:
        start_line, start_col = self.line, self.col
        m = _FLOAT_RE.match(self.src, self.i)
        if m:
            lex = m.group(0)
            self._consume_match(lex)
            return self._token(TokenType.FLOAT, lex, start_line, start_col)
        m = _INT_RE.match(self.src, self.i)
        if m:
            lex = m.group(0)
            self._consume_match(lex)
            return self._token(TokenType.INT, lex, start_line, start_col)
        self.add_error("número malformado")
        return self._token(TokenType.ILLEGAL, "bad number", start_line, start_col)


    def _identifier_or_keyword(self) -> Token:
        start_line, start_col = self.line, self.col
        m = _IDENT_RE.match(self.src, self.i)
        lex = m.group(0)
        self._consume_match(lex)
        t = KEYWORDS.get(lex, TokenType.IDENT)
        return self._token(t, lex, start_line, start_col)

    def _consume_match(self, lexeme: str):
        # avança i/linha/col de acordo com um match já calculado
        for ch in lexeme:
            self._advance()

    def next_token(self) -> Token:
        self._skip_ws_and_comments()
        if self._eof():
            return self._token(TokenType.EOF, "", self.line, self.col)

        ch = self._peek()
        start_line, start_col = self.line, self.col

        # strings
        if ch == '"':
            return self._string()

        # números (começa com dígito ou ponto seguido de dígito)
        if ch.isdigit() or (ch == "." and self._peek(1).isdigit()):
            return self._number()

        # identificadores / palavras-chave
        if ch.isalpha() or ch == "_":
            return self._identifier_or_keyword()

        # operadores compostos / simples
        two = ch + self._peek(1)
        if two == "==":
            self._advance(); self._advance()
            return self._token(TokenType.EQ, "==", start_line, start_col)
        if two == "!=":
            self._advance(); self._advance()
            return self._token(TokenType.NOT_EQ, "!=", start_line, start_col)
        if two == "<=":
            self._advance(); self._advance()
            return self._token(TokenType.LTE, "<=", start_line, start_col)
        if two == ">=":
            self._advance(); self._advance()
            return self._token(TokenType.GTE, ">=", start_line, start_col)
        if two == "&&":
            self._advance(); self._advance()
            return self._token(TokenType.AND, "&&", start_line, start_col)
        if two == "||":
            self._advance(); self._advance()
            return self._token(TokenType.OR, "||", start_line, start_col)
        if two == "++":
            self._advance(); self._advance()
            return self._token(TokenType.INC, "++", start_line, start_col)
        if two == "--":
            self._advance(); self._advance()
            return self._token(TokenType.DEC, "--", start_line, start_col)
        # novo caso para :=
        if two == ":=":
            self._advance(); self._advance()
            return self._token(TokenType.DEFINE, ":=", start_line, start_col)

        # operadores de um char e pontuação
        single_map = {
            "=": TokenType.ASSIGN,
            "+": TokenType.PLUS,
            "-": TokenType.MINUS,
            "*": TokenType.ASTERISK,
            "/": TokenType.SLASH,
            "%": TokenType.MOD,
            "!": TokenType.BANG,
            "<": TokenType.LT,
            ">": TokenType.GT,
            ",": TokenType.COMMA,
            ";": TokenType.SEMICOLON,
            ".": TokenType.DOT,
            "(": TokenType.LPAREN,
            ")": TokenType.RPAREN,
            "{": TokenType.LBRACE,
            "}": TokenType.RBRACE,
            "[": TokenType.LBRACKET,
            "]": TokenType.RBRACKET,
        }
        if ch in single_map:
            self._advance()
            return self._token(single_map[ch], ch, start_line, start_col)

        # desconhecido
        self.add_error(f"caractere inesperado '{ch}'")
        self._advance()
        return self._token(TokenType.ILLEGAL, ch, start_line, start_col)

    def tokenize(self) -> List[Token]:
        tokens = []
        while True:
            tok = self.next_token()
            tokens.append(tok)
            if tok.type == TokenType.EOF:
                break
        return tokens