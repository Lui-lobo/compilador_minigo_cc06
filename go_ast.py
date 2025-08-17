# go_ast.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Union

# --------------------------
# Tipos & Identificadores
# --------------------------

@dataclass
class Identifier:
    name: str
    line: int
    column: int

@dataclass
class TypeName:
    name: str
    line: int
    column: int

# --------------------------
# Programa & Declarações
# --------------------------

@dataclass
class Program:
    package: Identifier
    decls: List["Decl"]

class Decl: ...

@dataclass
class VarDecl(Decl):
    name: Identifier
    type_name: Optional[TypeName]  # pode ser None se inferido (se você quiser permitir)
    init: Optional["Expr"]
    line: int
    column: int

@dataclass
class Param:
    name: Identifier
    type_name: TypeName

@dataclass
class FuncDecl(Decl):
    name: Identifier
    params: List[Param]
    result: Optional[TypeName]     # retorno único opcional
    body: "BlockStmt"
    line: int
    column: int

# --------------------------
# Statements
# --------------------------

class Stmt: ...

@dataclass
class BlockStmt(Stmt):
    stmts: List[Stmt]
    line: int
    column: int

@dataclass
class IfStmt(Stmt):
    cond: "Expr"
    then_block: BlockStmt
    else_block: Optional[BlockStmt]
    line: int
    column: int

@dataclass
class ForStmt(Stmt):
    init: Optional[Stmt]   # pode ser ExprStmt/Assign/VarDecl ou None
    cond: Optional["Expr"] # se None, é for infinito
    post: Optional[Stmt]   # pode ser ExprStmt/Assign/IncDec ou None
    body: BlockStmt
    line: int
    column: int

@dataclass
class ReturnStmt(Stmt):
    value: Optional["Expr"]
    line: int
    column: int

@dataclass
class ExprStmt(Stmt):
    expr: "Expr"
    line: int
    column: int

# --------------------------
# Expressões
# --------------------------

class Expr: ...

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

@dataclass
class NameExpr(Expr):
    ident: Identifier
    line: int
    column: int

@dataclass
class UnaryExpr(Expr):
    op: str
    right: Expr
    line: int
    column: int

@dataclass
class BinaryExpr(Expr):
    left: Expr
    op: str
    right: Expr
    line: int
    column: int

@dataclass
class AssignStmt(Stmt):
    lhs: "Expr"
    rhs: "Expr"
    op: str   # "=" ou ":="
    line: int
    column: int

@dataclass
class AssignExpr(Expr):
    target: NameExpr
    value: Expr
    line: int
    column: int

@dataclass
class IncDecExpr(Expr):
    target: NameExpr
    op: str  # '++' | '--'
    line: int
    column: int

@dataclass
class CallExpr(Expr):
    callee: Expr            # NameExpr ou SelectorExpr
    args: List[Expr]
    line: int
    column: int

@dataclass
class SelectorExpr(Expr):
    recv: Expr              # ex: fmt.Println  => recv: NameExpr('fmt')
    attr: Identifier        # attr: 'Println'
    line: int
    column: int
