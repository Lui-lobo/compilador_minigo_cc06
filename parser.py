# parser.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

from lexer import Lexer, Token, TokenType
import go_ast as A  # seu módulo de AST (não é o stdlib "ast")

# ------------------------------------------------------------
# Representação de erro sintático
# ------------------------------------------------------------

@dataclass
class ParseError:
    line: int
    column: int
    message: str

# ------------------------------------------------------------
# Parser (descida recursiva + Pratt para expressões)
# ------------------------------------------------------------

class Parser:
    """
    Parser do Mini-Go.
    - Constrói a AST a partir da lista de tokens emitida pelo Lexer.
    - Usa descida recursiva para declarações/estatements e Pratt para expressões.
    - Acumula erros sintáticos em self.errors e tenta seguir parsing (recover).
    """
    def __init__(self, lexer: Lexer):
        self.lexer = lexer
        self.tokens: List[Token] = lexer.tokenize()  # tokeniza tudo de uma vez
        self.pos: int = 0                            # cursor na lista de tokens
        self.errors: List[ParseError] = []           # erros sintáticos acumulados

    # ------------- helpers básicos -------------

    def _pos_of_expr(self, e):
        """
        Extrai (line, column) de uma expressão para mensagens de erro/posicionamento.
        - Muitas Exprs têm .line/.column.
        - NameExpr pode não ter: buscamos no Identifier interno.
        - Se nada disponível, usamos o token atual.
        """
        if hasattr(e, "line") and hasattr(e, "column"):
            return e.line, e.column
        if isinstance(e, A.NameExpr) and hasattr(e, "ident"):
            return e.ident.line, e.ident.column
        tok = self._current()
        return tok.line, tok.column

    def _current(self) -> Token:
        """Retorna o token na posição atual (sem consumir)."""
        return self.tokens[self.pos]

    def _peek(self, k: int = 0) -> Token:
        """Lookahead: retorna o token pos+k (ou o último se passar do fim)."""
        i = self.pos + k
        if i >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[i]

    def _at(self, tt: TokenType) -> bool:
        """True se o token atual é do tipo tt."""
        return self._current().type == tt

    def _match(self, *types: TokenType) -> bool:
        """
        Se o token atual estiver entre 'types', consome e retorna True.
        Do contrário, não consome e retorna False.
        """
        if self._current().type in types:
            self.pos += 1
            return True
        return False

    def _expect(self, tt: TokenType, msg: str) -> Token:
        """
        Exige que o próximo token seja do tipo 'tt'.
        - Se for, consome e retorna.
        - Se não for, registra erro e retorna o token atual (sem consumir).
        Obs.: quem chama decide como se recuperar.
        """
        tok = self._current()
        if tok.type == tt:
            self.pos += 1
            return tok
        self._error(tok, msg + f" (esperado {tt.name}, encontrado {tok.type.name})")
        # não consome; deixa o chamador decidir como se recuperar
        return tok

    def _error(self, tok: Token, message: str):
        """Adiciona um erro sintático com posição do token fornecido."""
        self.errors.append(ParseError(tok.line, tok.column, message))

    def _synchronize(self, stop_types: List[TokenType]):
        """
        Recuperação simples: avança até encontrar um 'marcador seguro'
        (por exemplo, início de nova declaração) ou EOF.
        """
        while self._current().type not in stop_types and self._current().type != TokenType.EOF:
            self.pos += 1

    # ------------- parsing de alto nível -------------

    def parse_program(self) -> Optional[A.Program]:
        """
        program := 'package' IDENT ';'? decl*
        - Aceita ';' opcional depois de 'package main'.
        - Reúne declarações de nível superior (func/var).
        """
        if not self._match(TokenType.PACKAGE):
            self._error(self._current(), "programa deve iniciar com 'package'")
            return None

        name_tok = self._expect(TokenType.IDENT, "nome do pacote após 'package'")
        package = A.Identifier(name_tok.lexeme, name_tok.line, name_tok.column)

        # ';' opcional após 'package main'
        self._match(TokenType.SEMICOLON)

        decls: List[A.Decl] = []
        while not self._at(TokenType.EOF):
            if self._match(TokenType.FUNC):
                d = self._func_decl()
                if d:
                    decls.append(d)
            elif self._match(TokenType.VAR):
                d = self._var_decl(expect_semicolon=True)
                if d:
                    decls.append(d)
            elif self._at(TokenType.EOF):
                break
            else:
                # token inesperado em nível superior → tenta sincronizar
                self._error(self._current(), "declaração esperada ('func' ou 'var')")
                self._synchronize([TokenType.FUNC, TokenType.VAR, TokenType.EOF])

        return A.Program(package, decls)

    # ------------- declarações -------------

    def _var_decl(self, expect_semicolon: bool) -> Optional[A.VarDecl]:
        """
        varDecl := IDENT type? ('=' expr)? ';'?
        - type ∈ {int, float64, bool, string}
        - init opcional com '='
        - 'expect_semicolon' controla se exige ';' ao final (topo/bloco)
        """
        name_tok = self._expect(TokenType.IDENT, "identificador da variável")
        type_name: Optional[A.TypeName] = None
        init_expr: Optional[A.Expr] = None

        # tipo opcional
        if self._current().type in (
            TokenType.INT_TYPE,
            TokenType.FLOAT64_TYPE,
            TokenType.BOOL_TYPE,
            TokenType.STRING_TYPE,
        ):
            t = self._current()
            self.pos += 1
            type_name = A.TypeName(t.lexeme, t.line, t.column)

        # inicialização opcional com '='
        if self._match(TokenType.ASSIGN):
            init_expr = self._expression()

        if expect_semicolon:
            self._expect(TokenType.SEMICOLON, "ponto-e-vírgula após declaração de variável")

        return A.VarDecl(
            name=A.Identifier(name_tok.lexeme, name_tok.line, name_tok.column),
            type_name=type_name,
            init=init_expr,
            line=name_tok.line,
            column=name_tok.column,
        )

    def _func_decl(self) -> Optional[A.FuncDecl]:
        """
        funcDecl := 'func' IDENT '(' paramList? ')' resultType? block
        - Retorno único opcional após ')'
        """
        name_tok = self._expect(TokenType.IDENT, "nome da função")
        self._expect(TokenType.LPAREN, "abrir parênteses da lista de parâmetros")

        params: List[A.Param] = []
        if not self._at(TokenType.RPAREN):
            params = self._param_list()
        self._expect(TokenType.RPAREN, "fechar parênteses da lista de parâmetros")

        result: Optional[A.TypeName] = None
        if self._current().type in (
            TokenType.INT_TYPE,
            TokenType.FLOAT64_TYPE,
            TokenType.BOOL_TYPE,
            TokenType.STRING_TYPE,
        ):
            t = self._current()
            self.pos += 1
            result = A.TypeName(t.lexeme, t.line, t.column)

        body = self._block_stmt()
        return A.FuncDecl(
            name=A.Identifier(name_tok.lexeme, name_tok.line, name_tok.column),
            params=params,
            result=result,
            body=body,
            line=name_tok.line,
            column=name_tok.column,
        )

    def _param_list(self) -> List[A.Param]:
        """
        paramList := (IDENT type) (',' IDENT type)*
        - Cada parâmetro deve ter tipo explícito (subset simplificado).
        """
        params: List[A.Param] = []
        while True:
            name_tok = self._expect(TokenType.IDENT, "nome do parâmetro")
            type_tok = self._current()
            if type_tok.type not in (
                TokenType.INT_TYPE,
                TokenType.FLOAT64_TYPE,
                TokenType.BOOL_TYPE,
                TokenType.STRING_TYPE,
            ):
                self._error(type_tok, "tipo do parâmetro esperado (int/float64/bool/string)")
            else:
                self.pos += 1

            params.append(
                A.Param(
                    name=A.Identifier(name_tok.lexeme, name_tok.line, name_tok.column),
                    type_name=A.TypeName(type_tok.lexeme, type_tok.line, type_tok.column),
                )
            )
            if not self._match(TokenType.COMMA):
                break
        return params

    # ------------- statements -------------

    def _block_stmt(self) -> A.BlockStmt:
        """
        block := '{' stmt* '}'
        - Consome '{', parseia statements até '}'/EOF e consome '}'.
        """
        lbrace = self._expect(TokenType.LBRACE, "abrir bloco '{'")
        stmts: List[A.Stmt] = []

        while not self._at(TokenType.RBRACE) and not self._at(TokenType.EOF):
            stmts.append(self._statement())

        self._expect(TokenType.RBRACE, "fechar bloco '}'")
        return A.BlockStmt(stmts, lbrace.line, lbrace.column)

    def _statement(self) -> A.Stmt:
        """
        stmt := varDecl
              | ifStmt
              | forStmt
              | 'return' expr? ';'
              | simpleStmt ';'
        A ordem de checagem importa (palavras-chave primeiro).
        """
        if self._match(TokenType.VAR):
            # var dentro de bloco (mesma gramática do topo)
            decl = self._var_decl(expect_semicolon=True)
            return decl  # VarDecl também tratado como Stmt no subset

        if self._match(TokenType.IF):
            return self._if_stmt()

        if self._match(TokenType.FOR):
            return self._for_stmt()

        if self._match(TokenType.RETURN):
            stmt = self._return_stmt()
            # Consome o ';' do return, mantendo consistência com os demais
            self._expect(TokenType.SEMICOLON, "ponto-e-vírgula após 'return'")
            return stmt

        # Caso geral: simpleStmt + ';'
        stmt = self._simple_stmt()
        self._expect(TokenType.SEMICOLON, "ponto-e-vírgula após statement")
        return stmt

    def _if_stmt(self) -> A.IfStmt:
        """ifStmt := 'if' expr block ('else' block)?"""
        cond = self._expression()
        then_block = self._block_stmt()
        else_block = None
        if self._match(TokenType.ELSE):
            else_block = self._block_stmt()
        tok = self._peek(-1) if self.pos > 0 else self._current()
        return A.IfStmt(cond, then_block, else_block, tok.line, tok.column)
    
    def _maybe_for_init_stmt(self) -> Optional[A.Stmt]:
        """
        Reconhece o 'init' do for (sem consumir ';'):
          - IDENT ':=' expr  → VarDecl implícito (short var)
          - IDENT '='  expr  → Assign (como ExprStmt)
          - expr             → ExprStmt (ex.: chamada)
        Retorna None se não reconhecer nada (permitindo 'for ; cond ; post').
        """
        # IDENT := expr
        if (self._current().type == TokenType.IDENT and
            self._peek(1).type == TokenType.DEFINE):
            name_tok = self._current()
            self.pos += 2
            init = self._expression()
            return A.VarDecl(
                name=A.Identifier(name_tok.lexeme, name_tok.line, name_tok.column),
                type_name=None,     # tipo será inferido pelo semântico
                init=init,
                line=name_tok.line,
                column=name_tok.column,
            )

        # IDENT = expr
        if (self._current().type == TokenType.IDENT and
            self._peek(1).type == TokenType.ASSIGN):
            name_tok = self._current()
            self.pos += 2
            value = self._expression()
            expr = A.AssignExpr(
                target=A.NameExpr(A.Identifier(name_tok.lexeme, name_tok.line, name_tok.column),
                                  name_tok.line, name_tok.column),
                value=value,
                line=name_tok.line,
                column=name_tok.column,
            )
            return A.ExprStmt(expr, name_tok.line, name_tok.column)

        # expressão genérica como init (ex.: chamada)
        save = self.pos
        expr = self._expression()
        if expr:
            line, col = self._pos_of_expr(expr)
            return A.ExprStmt(expr, line, col)

        # nada reconhecido
        self.pos = save
        return None

    def _for_stmt(self) -> A.ForStmt:
        """
        forStmt:
          - 'for' block
          - 'for' expr block
          - 'for' init ';' cond? ';' post? block
        """
        init = None
        cond = None
        post = None

        # for { ... } → bloco infinito
        if self._at(TokenType.LBRACE):
            body = self._block_stmt()
            tok = self._peek(-1) if self.pos > 0 else self._current()
            return A.ForStmt(init, cond, post, body, tok.line, tok.column)

        # Tenta reconhecer 'init ; cond ; post'
        save_pos = self.pos
        maybe_init = self._maybe_for_init_stmt()

        if self._match(TokenType.SEMICOLON):
            init = maybe_init  # pode ser None (for ; cond ; post)

            # cond opcional
            if not self._at(TokenType.SEMICOLON):
                cond = self._expression()
            self._expect(TokenType.SEMICOLON, "ponto-e-vírgula após condição do for")

            # post opcional (ExprStmt)
            if not self._at(TokenType.LBRACE):
                post = self._post_stmt()

            body = self._block_stmt()
            tok = self._peek(-1) if self.pos > 0 else self._current()
            return A.ForStmt(init, cond, post, body, tok.line, tok.column)
        else:
            # Não havia dois ';' → trata como 'for cond { ... }'
            self.pos = save_pos
            if not self._at(TokenType.LBRACE):
                cond = self._expression()
            body = self._block_stmt()
            tok = self._peek(-1) if self.pos > 0 else self._current()
            return A.ForStmt(init, cond, post, body, tok.line, tok.column)


    def _post_stmt(self) -> A.Stmt:
        """
        Pós do for: qualquer expressão simples que valha como statement.
        Ex.: i++, i--, i = i + 1, chamada.
        """
        expr = self._expression()
        return A.ExprStmt(expr, expr.line, expr.column)

    def _return_stmt(self) -> A.ReturnStmt:
        """
        returnStmt := 'return' expr?
        (o ';' é consumido por _statement())
        """
        tok = self._peek(-1) if self.pos > 0 else self._current()

        if self._at(TokenType.SEMICOLON) or self._at(TokenType.RBRACE):
            return A.ReturnStmt(None, tok.line, tok.column)

        expr = self._expression()
        return A.ReturnStmt(expr, tok.line, tok.column)

    def _simple_stmt(self) -> A.Stmt:
        """
        simpleStmt :=
            IDENT ':=' expr      → VarDecl (short var)
          | IDENT '='  expr      → Assign (como ExprStmt)
          | IDENT '++' | '--'    → IncDec (como ExprStmt)
          | expr                 → ExprStmt
        """
        # short var: IDENT := expr
        if (self._current().type == TokenType.IDENT and
            self._peek(1).type == TokenType.DEFINE):
            name_tok = self._current()
            self.pos += 2  # consome IDENT e :=
            init = self._expression()
            # Representamos como VarDecl com type=None (inferência no semântico)
            return A.VarDecl(
                name=A.Identifier(name_tok.lexeme, name_tok.line, name_tok.column),
                type_name=None,
                init=init,
                line=name_tok.line,
                column=name_tok.column,
            )
    
        # assign: IDENT = expr
        if (self._current().type == TokenType.IDENT and
            self._peek(1).type == TokenType.ASSIGN):
            name_tok = self._current()
            self.pos += 2  # IDENT '='
            value = self._expression()
            expr = A.AssignExpr(
                target=A.NameExpr(A.Identifier(name_tok.lexeme, name_tok.line, name_tok.column),
                                  name_tok.line, name_tok.column),
                value=value,
                line=name_tok.line,
                column=name_tok.column,
            )
            line, col = name_tok.line, name_tok.column
            return A.ExprStmt(expr, line, col)
    
        # inc/dec: IDENT ++/--
        if (self._current().type == TokenType.IDENT and
            self._peek(1).type in (TokenType.INC, TokenType.DEC)):
            name_tok = self._current(); op_tok = self._peek(1)
            self.pos += 2
            expr = A.IncDecExpr(
                target=A.NameExpr(A.Identifier(name_tok.lexeme, name_tok.line, name_tok.column),
                                  name_tok.line, name_tok.column),
                op="++" if op_tok.type == TokenType.INC else "--",
                line=name_tok.line,
                column=name_tok.column,
            )
            return A.ExprStmt(expr, name_tok.line, name_tok.column)
    
        # fallback: expressão genérica como statement
        expr = self._expression()
        line, col = self._pos_of_expr(expr)
        return A.ExprStmt(expr, line, col)

    # ------------- expressões (Pratt) -------------

    # precedências (menor -> maior)
    # 1: ||   2: &&   3: == !=   4: < <= > >=
    # 5: + -   6: * / %
    PRECEDENCE = {
        "OR": 1,
        "AND": 2,
        "EQ": 3, "NOT_EQ": 3,
        "LT": 4, "LTE": 4, "GT": 4, "GTE": 4,
        "PLUS": 5, "MINUS": 5,
        "ASTERISK": 6, "SLASH": 6, "MOD": 6,
    }

    def _precedence_of(self, tok: Token) -> int:
        """Retorna a precedência do operador atual (0 se não é operador infixo)."""
        return self.PRECEDENCE.get(tok.type.name, 0)

    def _expression(self, min_prec: int = 1) -> A.Expr:
        """
        Expressão com climbing de precedência.
        - Primeiro, lê um prefixo (_prefix).
        - Em seguida, aplica pós-fixos de maior precedência (call e seletor).
        - Depois, consome operadores infix respeitando precedência crescente.
        """
        expr = self._prefix()

        # pós-fixos de maior precedência: chamada () e seletor .
        while True:
            # chamada: expr '(' arglist? ')'
            if self._match(TokenType.LPAREN):
                args = []
                if not self._at(TokenType.RPAREN):
                    while True:
                        args.append(self._expression())
                        if not self._match(TokenType.COMMA):
                            break
                rp = self._expect(TokenType.RPAREN, "fechar chamada ')'")
                expr = A.CallExpr(expr, args, rp.line, rp.column)
                continue

            # seletor: expr '.' IDENT  (ex.: fmt.Println)
            if self._match(TokenType.DOT):
                attr = self._expect(TokenType.IDENT, "nome após '.'")
                expr = A.SelectorExpr(
                    expr,
                    A.Identifier(attr.lexeme, attr.line, attr.column),
                    attr.line,
                    attr.column,
                )
                continue

            break

        # operadores binários infix, respeitando precedência
        while True:
            tok = self._current()
            prec = self._precedence_of(tok)
            if prec < min_prec or prec == 0:
                break
            self.pos += 1  # consome o operador
            right = self._expression(prec + 1)
            expr = A.BinaryExpr(expr, tok.lexeme or tok.type.name, right, tok.line, tok.column)

        return expr

    def _prefix(self) -> A.Expr:
        """
        Reconhece os átomos e operadores prefixados:
        - literais (int, float, string, true, false)
        - identificadores
        - unários '!' e '-'
        - parênteses para agrupar
        """
        tok = self._current()

        # literais
        if self._match(TokenType.INT):
            return A.IntegerLit(int(tok.lexeme), tok.line, tok.column)
        if self._match(TokenType.FLOAT):
            return A.FloatLit(float(tok.lexeme), tok.line, tok.column)
        if self._match(TokenType.STRING):
            return A.StringLit(tok.lexeme, tok.line, tok.column)
        if self._match(TokenType.TRUE):
            return A.BoolLit(True, tok.line, tok.column)
        if self._match(TokenType.FALSE):
            return A.BoolLit(False, tok.line, tok.column)

        # identificador
        if self._match(TokenType.IDENT):
            ident = A.Identifier(tok.lexeme, tok.line, tok.column)
            return A.NameExpr(ident, tok.line, tok.column)  # se NameExpr carrega posição

        # unários: !  -
        if self._match(TokenType.BANG):
            right = self._expression(7)  # maior que qualquer binário
            return A.UnaryExpr("!", right, tok.line, tok.column)
        if self._match(TokenType.MINUS):
            right = self._expression(7)
            return A.UnaryExpr("-", right, tok.line, tok.column)

        # parênteses
        if self._match(TokenType.LPAREN):
            expr = self._expression()
            self._expect(TokenType.RPAREN, "fechar ')'")
            return expr

        # erro: nada que forme expressão
        self._error(tok, f"expressão inesperada: {tok.type.name}")
        self.pos += 1  # evita loop
        return A.IntegerLit(0, tok.line, tok.column)
