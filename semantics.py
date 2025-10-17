# semantics.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, List

import go_ast as A  # módulo contendo a definição da AST (árvore sintática abstrata)

# -------------------------
# Tipos
# -------------------------

# Classe que representa um tipo da linguagem
@dataclass(frozen=True)
class Type:
    name: str  # Nome do tipo: "int", "float64", "bool", "string", "void", "invalid"

# Instâncias imutáveis representando tipos primitivos e especiais
INT = Type("int")
FLOAT = Type("float64")
BOOL = Type("bool")
STRING = Type("string")
VOID = Type("void")
INVALID = Type("invalid")

# Função que converte um TypeName da AST em um Type do analisador
def type_from_typename(tn: Optional[A.TypeName]) -> Type:
    if tn is None: return VOID  # se não há tipo declarado, assume void
    n = tn.name
    if n == "int": return INT
    if n == "float64": return FLOAT
    if n == "bool": return BOOL
    if n == "string": return STRING
    return INVALID  # tipo não reconhecido

# Retorna True se o tipo for numérico (int ou float)
def is_numeric(t: Type) -> bool:
    return t in (INT, FLOAT)

# Retorna o tipo resultante de uma operação entre dois tipos numéricos
def common_numeric(l: Type, r: Type) -> Type:
    if l == FLOAT or r == FLOAT: return FLOAT  # float domina
    if l == INT and r == INT: return INT
    return INVALID  # combinação inválida

# -------------------------
# Símbolos / Escopos
# -------------------------

# Representa uma variável declarada
@dataclass
class VarSymbol:
    name: str
    type: Type
    decl: A.VarDecl  # referência à declaração na AST

# Representa uma função declarada
@dataclass
class FuncSymbol:
    name: str
    params: List[Type]
    result: Type
    decl: A.FuncDecl  # referência à declaração na AST

# Classe que gerencia os escopos léxicos
class Scope:
    """Escopo léxico com encadeamento pai → filho"""
    def __init__(self, parent: Optional["Scope"]=None):
        self.parent = parent         # escopo pai
        self.syms: Dict[str, object] = {}  # tabela de símbolos locais

    def define(self, name: str, sym: object) -> bool:
        """Define um novo símbolo no escopo atual.
           Retorna False se o símbolo já existir (erro de redeclaração)."""
        if name in self.syms:
            return False
        self.syms[name] = sym
        return True

    def lookup(self, name: str) -> Optional[object]:
        """Procura um símbolo no escopo atual e em todos os escopos pais."""
        s: Optional[Scope] = self
        while s:
            if name in s.syms:
                return s.syms[name]
            s = s.parent
        return None  # não encontrado

# -------------------------
# Erros
# -------------------------

# Representa um erro semântico com posição e mensagem
@dataclass
class SemaError:
    line: int
    column: int
    message: str

# -------------------------
# Analisador Semântico
# -------------------------

class SemanticAnalyzer:
    def __init__(self):
        # Lista de erros encontrados
        self.errors: List[SemaError] = []
        # Mapa node_id → tipo inferido
        self.types: Dict[int, Type] = {}
        # Escopo global (sem pai)
        self.scope = Scope(None)
        # Função atual sendo analisada
        self.current_func: Optional[FuncSymbol] = None

        # Define função builtin "print" como disponível globalmente
        self.scope.define("print", FuncSymbol("print", params=[], result=VOID, decl=None))

    # ---------- utils ----------

    # Associa um tipo a um nó da AST (para futuras consultas)
    def _note_type(self, node, t: Type):
        if node is not None:
            self.types[id(node)] = t

    # Registra um erro com posição aproximada do nó
    def _err(self, node, msg: str):
        line = getattr(node, "line", 0)
        col = getattr(node, "column", 0)
        self.errors.append(SemaError(line, col, msg))

    # Verifica se o tipo fonte pode ser atribuído ao destino
    def _assert_assignable(self, dst: Type, src: Type, node):
        if dst == src: return  # tipos idênticos → ok
        if dst == FLOAT and src == INT: return  # int pode ser convertido em float
        self._err(node, f"tipo incompatível: não é possível atribuir {src.name} em {dst.name}")

    # ---------- entrada ----------

    # Função principal do analisador semântico
    def analyze(self, program: A.Program) -> bool:
        # Primeira passagem: declara variáveis e funções globais
        for d in program.decls:
            if isinstance(d, A.VarDecl):
                self._declare_global_var(d)
            elif isinstance(d, A.FuncDecl):
                self._declare_func(d)

        # Segunda passagem: verifica tipos e corpos das declarações
        for d in program.decls:
            if isinstance(d, A.VarDecl):
                self._check_vardecl(d, in_block=False)
            elif isinstance(d, A.FuncDecl):
                self._check_func(d)
        return not self.errors  # retorna True se não houver erros

    # ---------- declarações topo ----------

    # Declara uma variável global
    def _declare_global_var(self, d: A.VarDecl):
        t = type_from_typename(d.type_name) if d.type_name else VOID
        sym = VarSymbol(d.name.name, t, d)
        if not self.scope.define(sym.name, sym):
            self._err(d, f"variável global '{sym.name}' redeclarada")

    # Declara uma função no escopo global
    def _declare_func(self, f: A.FuncDecl):
        params: List[Type] = []
        # Lê tipos dos parâmetros
        for p in f.params:
            pt = type_from_typename(p.type_name)
            if pt == INVALID:
                self._err(p, f"tipo de parâmetro inválido: {p.type_name.name}")
            params.append(pt)
        # Tipo de retorno
        res = type_from_typename(f.result) if f.result else VOID
        sym = FuncSymbol(f.name.name, params, res, f)
        if not self.scope.define(sym.name, sym):
            self._err(f, f"função '{sym.name}' redeclarada")

    # ---------- checagem de declarações ----------

    # Verifica o corpo de uma função
    def _check_func(self, f: A.FuncDecl):
        func_sym = self.scope.lookup(f.name.name)
        assert isinstance(func_sym, FuncSymbol)
        prev_func = self.current_func
        self.current_func = func_sym

        # Cria um novo escopo para parâmetros da função
        fn_scope = Scope(self.scope)
        for (p, t) in zip(f.params, func_sym.params):
            if not fn_scope.define(p.name.name, VarSymbol(p.name.name, t, None)):
                self._err(p, f"parâmetro '{p.name.name}' duplicado")

        # Salva escopo atual e troca para o escopo da função
        saved = self.scope
        self.scope = fn_scope
        # Verifica o corpo da função
        self._check_block(f.body)
        # Restaura escopo e função anterior
        self.scope = saved
        self.current_func = prev_func

    # Verifica um bloco de código (cria escopo local)
    def _check_block(self, b: A.BlockStmt):
        blk = Scope(self.scope)  # novo escopo léxico filho
        saved = self.scope
        self.scope = blk
        for s in b.stmts:  # verifica cada statement
            self._check_stmt(s)
        self.scope = saved  # restaura escopo pai

    # Verifica cada tipo de statement individualmente
    def _check_stmt(self, s: A.Stmt):
        if isinstance(s, A.VarDecl):  # declaração de variável local
            self._check_vardecl(s, in_block=True)
            return
        if isinstance(s, A.ExprStmt):  # expressão usada como statement
            self._type_of_expr(s.expr)
            return
        if isinstance(s, A.ReturnStmt):  # retorno de função
            self._check_return(s)
            return
        if isinstance(s, A.IfStmt):  # estrutura condicional
            tcond = self._type_of_expr(s.cond)
            if tcond != BOOL:
                self._err(s.cond, f"condição do if deve ser bool, obtido {tcond.name}")
            self._check_block(s.then_block)
            if s.else_block:
                self._check_block(s.else_block)
            return
        if isinstance(s, A.ForStmt):  # laço for
            if s.init: self._check_stmt(s.init)
            if s.cond:
                tcond = self._type_of_expr(s.cond)
                if tcond != BOOL:
                    self._err(s.cond, f"condição do for deve ser bool, obtido {tcond.name}")
            if s.post: self._check_stmt(s.post)
            self._check_block(s.body)
            return
        if isinstance(s, A.AssignStmt):  # atribuição simples
            lt = self._type_of_expr(s.lhs)
            rt = self._type_of_expr(s.rhs)
            self._assert_assignable(lt, rt, s)
            return

    # Verifica uma declaração de variável (global ou local)
    def _check_vardecl(self, d: A.VarDecl, in_block: bool):
        # Garante que não há redeclaração no mesmo escopo
        if not self.scope.define(d.name.name, VarSymbol(d.name.name, VOID, d)):
            self._err(d, f"variável '{d.name.name}' redeclarada no mesmo escopo")

        declared_type = type_from_typename(d.type_name) if d.type_name else None
        # Caso sem tipo e sem inicializador → erro
        if d.init is None and declared_type is None:
            self._err(d, f"não é possível inferir tipo de '{d.name.name}' sem inicializador")
            vtype = INVALID
        else:
            # Infere tipo do inicializador, se houver
            init_type = self._type_of_expr(d.init) if d.init is not None else None
            # Se ambos existem, valida compatibilidade
            if declared_type is not None and init_type is not None:
                self._assert_assignable(declared_type, init_type, d)
                vtype = declared_type
            elif declared_type is not None:
                vtype = declared_type
            else:
                vtype = init_type

        # Atualiza símbolo com o tipo final
        sym_here = VarSymbol(d.name.name, vtype or INVALID, d)
        self.scope.syms[d.name.name] = sym_here

    # Verifica instruções de retorno
    def _check_return(self, r: A.ReturnStmt):
        expected = self.current_func.result if self.current_func else VOID
        if r.value is None:  # retorno vazio
            if expected != VOID:
                self._err(r, f"função espera retorno {expected.name}, mas 'return' vazio encontrado")
            return
        got = self._type_of_expr(r.value)  # tipo do valor retornado
        self._assert_assignable(expected, got, r)

    # ---------- Expressões ----------

    # Determina o tipo de uma expressão (e valida compatibilidades)
    def _type_of_expr(self, e: A.Expr) -> Type:
        # Literais primitivos
        if isinstance(e, A.IntegerLit):
            self._note_type(e, INT); return INT
        if isinstance(e, A.FloatLit):
            self._note_type(e, FLOAT); return FLOAT
        if isinstance(e, A.StringLit):
            self._note_type(e, STRING); return STRING
        if isinstance(e, A.BoolLit):
            self._note_type(e, BOOL); return BOOL

        # Identificador (variável ou função)
        if isinstance(e, A.NameExpr):
            sym = self.scope.lookup(e.ident.name)
            if isinstance(sym, VarSymbol):
                self._note_type(e, sym.type); return sym.type
            if isinstance(sym, FuncSymbol):
                self._err(e, f"uso de nome de função '{sym.name}' como valor não suportado")
                self._note_type(e, INVALID); return INVALID
            self._err(e, f"identificador não declarado: {e.ident.name}")
            self._note_type(e, INVALID); return INVALID

        # Expressão unária (! ou -)
        if isinstance(e, A.UnaryExpr):
            rt = self._type_of_expr(e.right)
            if e.op == "!":  # negação lógica
                if rt != BOOL: self._err(e, f"'!' requer bool, obtido {rt.name}")
                self._note_type(e, BOOL); return BOOL
            if e.op == "-":  # inversão numérica
                if not is_numeric(rt): self._err(e, f"unário '-' requer numérico, obtido {rt.name}")
                self._note_type(e, rt if is_numeric(rt) else INVALID); return rt if is_numeric(rt) else INVALID

        # Expressão binária (+, -, *, /, comparações, lógicas)
        if isinstance(e, A.BinaryExpr):
            lt = self._type_of_expr(e.left)
            rt = self._type_of_expr(e.right)
            op = e.op
            if op in {"+", "-", "*", "/", "%"}:  # operações aritméticas
                if not (is_numeric(lt) and is_numeric(rt)):
                    self._err(e, f"operador '{op}' requer numéricos, obtidos {lt.name} e {rt.name}")
                    self._note_type(e, INVALID); return INVALID
                t = common_numeric(lt, rt)
                self._note_type(e, t); return t
            if op in {"<", "<=", ">", ">="}:  # comparações numéricas
                if not (is_numeric(lt) and is_numeric(rt)):
                    self._err(e, f"comparação '{op}' requer numéricos, obtidos {lt.name} e {rt.name}")
                self._note_type(e, BOOL); return BOOL
            if op in {"==", "!="}:  # igualdade e diferença
                if lt != rt and not (lt == FLOAT and rt == INT) and not (lt == INT and rt == FLOAT):
                    self._err(e, f"igualdade entre tipos incompatíveis: {lt.name} vs {rt.name}")
                self._note_type(e, BOOL); return BOOL
            if op in {"&&", "||"}:  # operadores lógicos
                if lt != BOOL or rt != BOOL:
                    self._err(e, f"operador lógico '{op}' requer bool, obtidos {lt.name} e {rt.name}")
                self._note_type(e, BOOL); return BOOL

        # Expressão de atribuição dentro de uma expressão
        if isinstance(e, A.AssignExpr):
            vt = self._type_of_expr(e.value)
            if not isinstance(e.target, A.NameExpr):
                self._err(e, "atribuição requer alvo nomeado")
                self._note_type(e, INVALID); return INVALID
            sym = self.scope.lookup(e.target.ident.name)
            if not isinstance(sym, VarSymbol):
                self._err(e, f"identificador não declarado: {e.target.ident.name}")
                self._note_type(e, INVALID); return INVALID
            self._assert_assignable(sym.type, vt, e)
            self._note_type(e, sym.type); return sym.type

        # Incremento / Decremento (++ ou --)
        if isinstance(e, A.IncDecExpr):
            t = self._type_of_expr(e.target)
            if not is_numeric(t):
                self._err(e, f"{e.op} requer alvo numérico, obtido {t.name}")
            self._note_type(e, t if is_numeric(t) else INVALID); return t if is_numeric(t) else INVALID

        # Chamada de função
        if isinstance(e, A.CallExpr):
            if isinstance(e.callee, A.NameExpr):  # chamada direta ex: f(x)
                fname = e.callee.ident.name
                sym = self.scope.lookup(fname)
                if isinstance(sym, FuncSymbol):
                    # Verifica quantidade de argumentos
                    if len(e.args) != len(sym.params) and sym.name != "print":
                        self._err(e, f"função '{sym.name}' espera {len(sym.params)} arg(s), recebeu {len(e.args)}")
                    # Verifica compatibilidade de cada argumento
                    for i, arg in enumerate(e.args[:len(sym.params)]):
                        at = self._type_of_expr(arg)
                        self._assert_assignable(sym.params[i], at, arg)
                    # Avalia argumentos excedentes (para funções builtins como print)
                    for arg in e.args[len(sym.params):]:
                        self._type_of_expr(arg)
                    self._note_type(e, sym.result); return sym.result
                else:
                    self._err(e, f"função não declarada: {fname}")
                    self._note_type(e, INVALID); return INVALID
            elif isinstance(e.callee, A.SelectorExpr):  # ex: fmt.Println()
                for arg in e.args:
                    self._type_of_expr(arg)
                self._note_type(e, VOID); return VOID

        # Expressão seletora (não implementada aqui)
        if isinstance(e, A.SelectorExpr):
            self._note_type(e, INVALID); return INVALID

        # Caso não identificado
        self._note_type(e, INVALID)
        return INVALID
