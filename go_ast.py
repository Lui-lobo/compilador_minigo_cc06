# go_ast.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Union

# ============================================================
# Definições de AST (Árvore Sintática Abstrata) do Mini-Go
# ------------------------------------------------------------
# Cada classe representa um nó na árvore sintática. 
# A árvore é produzida pelo parser e usada nas próximas fases:
# análise semântica, interpretação ou geração de código.
# ============================================================

# --------------------------
# Tipos & Identificadores
# --------------------------

@dataclass
class Identifier:
    """Um identificador com posição no código (nome de variável, função, pacote, etc.)."""
    name: str
    line: int
    column: int

@dataclass
class TypeName:
    """Nome de tipo simples (int, float64, bool, string)."""
    name: str
    line: int
    column: int

# --------------------------
# Programa & Declarações
# --------------------------

@dataclass
class Program:
    """Raiz da AST: programa Mini-Go completo."""
    package: Identifier
    decls: List["Decl"]   # lista de declarações (variáveis/funções)

class Decl: ...
"""Classe base para declarações (não instanciada diretamente)."""

@dataclass
class VarDecl(Decl):
    """Declaração de variável."""
    name: Identifier
    type_name: Optional[TypeName]  # pode ser None se inferido (ex.: via :=)
    init: Optional["Expr"]         # expressão inicializadora opcional
    line: int
    column: int

@dataclass
class Param:
    """Parâmetro de função: identificador + tipo obrigatório."""
    name: Identifier
    type_name: TypeName

@dataclass
class FuncDecl(Decl):
    """Declaração de função: nome, parâmetros, tipo de retorno opcional e corpo."""
    name: Identifier
    params: List[Param]
    result: Optional[TypeName]     # retorno único opcional
    body: "BlockStmt"
    line: int
    column: int

# --------------------------
# Statements (instruções)
# --------------------------

class Stmt: ...
"""Classe base para statements."""

@dataclass
class BlockStmt(Stmt):
    """Bloco de instruções delimitado por chaves { ... }."""
    stmts: List[Stmt]
    line: int
    column: int

@dataclass
class IfStmt(Stmt):
    """Comando if (com else opcional)."""
    cond: "Expr"
    then_block: BlockStmt
    else_block: Optional[BlockStmt]
    line: int
    column: int

@dataclass
class ForStmt(Stmt):
    """Laço for em estilo Go (3 formas suportadas)."""
    init: Optional[Stmt]    # inicialização (VarDecl, Assign, ExprStmt ou None)
    cond: Optional["Expr"]  # condição (ou None para for infinito)
    post: Optional[Stmt]    # pós-expressão (ExprStmt, IncDec, Assign ou None)
    body: BlockStmt
    line: int
    column: int

@dataclass
class ReturnStmt(Stmt):
    """Comando return (expr opcional)."""
    value: Optional["Expr"]
    line: int
    column: int

@dataclass
class ExprStmt(Stmt):
    """Statement que é apenas uma expressão (ex.: chamada de função)."""
    expr: "Expr"
    line: int
    column: int

# --------------------------
# Expressões
# --------------------------

class Expr: ...
"""Classe base para expressões."""

# Literais
@dataclass
class IntegerLit(Expr):
    value: int
    line: int
    column: int

@dataclass
class FloatLit(Expr):
    value: float
    line: int
    column: int

@dataclass
class StringLit(Expr):
    value: str
    line: int
    column: int

@dataclass
class BoolLit(Expr):
    value: bool
    line: int
    column: int

# Expressões de nomes e operadores
@dataclass
class NameExpr(Expr):
    """Referência a uma variável/função pelo nome (Identifier)."""
    ident: Identifier
    line: int
    column: int

@dataclass
class UnaryExpr(Expr):
    """Operador unário prefixado (!, -)."""
    op: str
    right: Expr
    line: int
    column: int

@dataclass
class BinaryExpr(Expr):
    """Operador binário infix (+, -, *, /, <, ==, etc.)."""
    left: Expr
    op: str
    right: Expr
    line: int
    column: int

# Atribuições
@dataclass
class AssignStmt(Stmt):
    """Statement de atribuição (não muito usado, preferimos AssignExpr+ExprStmt)."""
    lhs: "Expr"
    rhs: "Expr"
    op: str   # "=" ou ":="
    line: int
    column: int

@dataclass
class AssignExpr(Expr):
    """Atribuição como expressão (tratada como ExprStmt no parser)."""
    target: NameExpr
    value: Expr
    line: int
    column: int

@dataclass
class IncDecExpr(Expr):
    """Incremento/decremento pós-fixado (++ ou --)."""
    target: NameExpr
    op: str  # '++' | '--'
    line: int
    column: int

# Chamadas e seletores
@dataclass
class CallExpr(Expr):
    """Chamada de função (ex.: soma(a, b), fmt.Println(...))."""
    callee: Expr            # pode ser NameExpr ou SelectorExpr
    args: List[Expr]
    line: int
    column: int

@dataclass
class SelectorExpr(Expr):
    """Seletor (expr.ident), ex.: fmt.Println."""
    recv: Expr              # ex: 'fmt'
    attr: Identifier        # ex: 'Println'
    line: int
    column: int
