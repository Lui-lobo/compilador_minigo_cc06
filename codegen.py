# codegen.py
from __future__ import annotations
from typing import List
import go_ast as A
from semantics import VarSymbol, SemanticAnalyzer


class CodeGenerator:
    """
    Gera código para a máquina MEPA a partir de uma AST no 'dialeto Go' do projeto.

    Visão geral do funcionamento
    ----------------------------
    - O gerador opera com um *buffer* de instruções (self.code), emitindo mnemonics MEPA.
    - Mantém uma pilha de escopos (self.scopes) para mapear nomes de variáveis a endereços
      de memória locais (endereçamento relativo do frame atual).
    - Concilia variáveis **globais** (vindas do escopo do analisador semântico) com variáveis
      **locais** (alocadas por bloco/declaração).
    - Usa rótulos (L1, L2, ...) para estruturas de controle (if/for) com DSVF/DSVS.
    - Converte expressões para a disciplina de pilha do MEPA (avalia esquerda→direita, empilha
      operandos, aplica operador).

    Convenções MEPA adotadas
    ------------------------
    - CRCT k  : empilha constante k
    - CRVL a  : empilha o conteúdo do endereço 'a'
    - ARMZ a  : armazena topo da pilha no endereço 'a'
    - AMEM k  : reserva 'k' posições de memória
    - DMEM k  : libera 'k' posições de memória
    - SOMA, SUBT, MULT, DIVI : aritmética
    - CMxx    : comparações (CMMA, CMME, CMAG, CMEG, CMIG, CMDG)
    - CONJ, DISJ : lógicos
    - NEGA, INVR : negação lógica / troca de sinal
    - DSVF L  : desvia se falso para rótulo L
    - DSVS L  : desvia incondicional para rótulo L
    - ESCRV   : (aqui) usado para simular 'fmt.Println' impressa 1 valor
    - RETU    : retorno de função/procedimento
    - NADA    : no-op (também usado como marcador de rótulo)

    Observações sobre memória
    -------------------------
    - Na inicialização do programa, se houver 'globals_count', emitimos AMEM globals_count.
      Essas posições 0..globals_count-1 modelam as variáveis globais.
    - Para variáveis locais, cada declaração faz 'AMEM 1' e associamos um endereço sequencial
      (self.next_addr). A desalocação é feita por bloco (DMEM <qtd-local>), exceto no bloco
      raiz de função (corpo da função), que é tratado como frame-base.
    """

    def __init__(self, analyzer: SemanticAnalyzer):
        self.analyzer = analyzer
        self.code: List[str] = []
        self._label_count = 0

        # Pilha de escopos locais (cada item é {nome: endereço_local})
        self.scopes: list[dict[str, int]] = [{}]
        # Contador global de endereços locais no frame atual (cresce a cada VarDecl)
        self.next_addr = 0

    # -------------------------------
    # Utilitários básicos
    # -------------------------------
    def next_label(self) -> str:
        """
        Cria um novo rótulo MEPA único (L1, L2, ...).

        Usado para ancorar desvios de estruturas de controle.
        """
        self._label_count += 1
        return f"L{self._label_count}"

    def emit(self, instr: str):
        """
        Acrescenta uma instrução MEPA ao buffer de saída.
        """
        self.code.append(instr)

    # -------------------------------
    # Controle de escopo
    # -------------------------------
    def push_scope(self):
        """
        Entra em um novo escopo léxico (bloco). Variáveis declaradas após isso
        serão mapeadas neste dicionário topo da pilha.
        """
        self.scopes.append({})

    def pop_scope(self):
        """
        Sai do escopo atual. A desalocação de memória (DMEM) é decidida em 'block',
        pois lá sabemos quantas locais foram criadas neste escopo.
        """
        self.scopes.pop()

    def declare_var(self, name: str) -> int:
        """
        Declara variável local no escopo atual:
        - Atribui o próximo endereço livre (self.next_addr).
        - Emite AMEM 1 (reserva 1 célula no frame).
        - Retorna o endereço atribuído para futuras CRVL/ARMZ.

        Obs.: Endereços locais são modelados aqui como índices simples (0..N) do frame.
        """
        addr = self.next_addr
        self.next_addr += 1
        self.scopes[-1][name] = addr
        self.emit("\tAMEM 1")
        return addr

    def lookup_addr(self, name: str) -> int:
        """
        Resolve o endereço de uma variável, preferindo o escopo mais interno.

        Ordem de busca:
        1) Escopos locais (self.scopes, do topo para a base).
        2) Escopo global vindo do analisador semântico (self.analyzer.scope).
           - Se for VarSymbol global, mapeamos o endereço pelo índice de inserção
             em analyzer.scope.syms (0-based), compatível com 'AMEM globals' no início.
        3) Nomes especiais 'fmt' / 'Println' são ignorados (retornam 0 por convenção).
        """
        # busca em escopos locais, do mais interno ao mais externo
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]

        # busca em globais (tabela do analisador semântico)
        sym = self.analyzer.scope.lookup(name)
        if isinstance(sym, VarSymbol):
            # Endereço global = índice de inserção na tabela de símbolos global
            return list(self.analyzer.scope.syms.keys()).index(name)

        # Pseudo-nomes da simulação de I/O (não ocupam memória real)
        if name in ("fmt", "Println"):
            return 0

        raise RuntimeError(f"Variável {name} não declarada")

    # -------------------------------
    # Geração principal
    # -------------------------------
    def generate(self, program: A.Program) -> List[str]:
        """
        Ponto de entrada da geração:
        - Reserva memória para globais (AMEM) conforme tabela semântica.
        - Percorre declarações do programa emitindo código de cada função (FuncDecl).

        Retorna a lista final de instruções MEPA.
        """
        globals_count = sum(
            1 for sym in self.analyzer.scope.syms.values() if isinstance(sym, VarSymbol)
        )
        if globals_count:
            # Reserva as células das variáveis globais no início do programa
            self.emit(f"\tAMEM {globals_count}")

        # Gera o corpo de cada função declarada
        for d in program.decls:
            if isinstance(d, A.FuncDecl):
                self.func_decl(d)

        return self.code

    # -------------------------------
    # Declarações e blocos
    # -------------------------------
    def func_decl(self, f: A.FuncDecl):
        """
        Emite ponto de entrada da função:
        - Reseta pilha de escopos locais para uma base vazia.
        - Reseta contador de endereços locais (novo frame).
        - Emite rótulo 'nome: NADA' como entrada da função.
        - Gera o bloco do corpo marcando-o como 'raiz' (is_root=True) para
          NÃO desalocar com DMEM ao final (o RETU fecha o frame).
        """
        self.scopes = [{}]
        self.next_addr = 0
        self.emit(f"{f.name.name}: NADA")
        self.block(f.body, is_root=True)
        self.emit("\tRETU")

    def block(self, b: A.BlockStmt, is_root: bool = False):
        """
        Gera um novo bloco:
        - Abre escopo (push_scope).
        - Emite cada statement na ordem.
        - Calcula quantas variáveis locais foram declaradas neste escopo e,
          se não for o bloco raiz da função, emite 'DMEM <qtd>' para liberar.
        - Fecha o escopo (pop_scope).

        Por que não desalocar no escopo raiz?
        - O frame da função (variáveis locais "do corpo") é desalocado pelo protocolo
          de chamada/retorno (RETU). Emitir DMEM aqui causaria desalocação dupla.
        """
        self.push_scope()
        for s in b.stmts:
            self.stmt(s)

        local_count = len(self.scopes[-1])
        if local_count > 0 and not is_root:
            self.emit(f"\tDMEM {local_count}")
        self.pop_scope()

    # -------------------------------
    # Statements
    # -------------------------------
    def stmt(self, s: A.Stmt):
        """
        Dispatcher de statements. Para cada nó, emite a sequência MEPA correspondente.
        """
        # Declaração de variável: aloca e, se houver inicializador, avalia e armazena.
        if isinstance(s, A.VarDecl):
            addr = self.declare_var(s.name.name)
            if s.init:
                self.expr(s.init)
                self.emit(f"\tARMZ {addr}")
            return

        # Atribuição simples: avalia RHS -> ARMZ endereço do LHS
        if isinstance(s, A.AssignExpr):
            addr = self.lookup_addr(s.target.ident.name)
            self.expr(s.value)
            self.emit(f"\tARMZ {addr}")
            return

        # Expressão usada como statement (ex.: chamada de função/biblioteca)
        if isinstance(s, A.ExprStmt):
            # Caso especial: simulação 'fmt.Println(x)' -> avalia x e ESCRV
            if isinstance(s.expr, A.CallExpr) and isinstance(s.expr.callee, A.SelectorExpr):
                if s.expr.args:
                    self.expr(s.expr.args[0])
                    self.emit("\tESCRV")
            else:
                self.expr(s.expr)
            return

        # Return: se tem valor, avalia e deixa no topo; em seguida RETU
        if isinstance(s, A.ReturnStmt):
            if s.value:
                self.expr(s.value)
            self.emit("\tRETU")
            return

        # If/Else
        if isinstance(s, A.IfStmt):
            self.if_stmt(s)
            return

        # For (estilo 'for cond { ... }' ou 'for { ... }' com pós)
        if isinstance(s, A.ForStmt):
            self.for_stmt(s)
            return

    def if_stmt(self, s: A.IfStmt):
        """
        Compila:
            if cond { then_block } else { else_block }
        como:
            <cond>
            DSVF L_else
            <then_block>
            DSVS L_end
        L_else: NADA
            <else_block?>
        L_end : NADA
        """
        label_else = self.next_label()
        label_end = self.next_label()

        self.expr(s.cond)
        self.emit(f"\tDSVF {label_else}")

        self.block(s.then_block)
        self.emit(f"\tDSVS {label_end}")

        self.emit(f"{label_else}: NADA")
        if s.else_block:
            self.block(s.else_block)
        self.emit(f"{label_end}: NADA")

    def for_stmt(self, s: A.ForStmt):
        """
        Compila:
            for cond { body; post? }
        como:
        L_start: NADA
            <cond?>           ; se houver
            DSVF L_end        ; sai se falso
            <body>
            <post?>           ; ex.: i = i + 1
            DSVS L_start      ; volta ao teste/loop
        L_end: NADA
        """
        label_start = self.next_label()
        label_end = self.next_label()
        self.emit(f"{label_start}: NADA")

        if s.cond:
            self.expr(s.cond)
            self.emit(f"\tDSVF {label_end}")

        self.block(s.body)
        if s.post:
            self.stmt(s.post)
        self.emit(f"\tDSVS {label_start}")
        self.emit(f"{label_end}: NADA")

    # -------------------------------
    # Expressões
    # -------------------------------
    def expr(self, e: A.Expr):
        """
        Emite código para avaliar e deixar o resultado da expressão no topo da pilha.

        Estratégia:
        - Literais: CRCT k
        - Nome: resolve endereço (local/global) e CRVL addr
        - Binário: avalia esquerda, avalia direita, aplica operador (mnemônico em 'opmap')
        - Unário: avalia operando e aplica INVR/NEGA
        - Atribuição usada como expressão: avalia RHS e ARMZ addr
        """
        if isinstance(e, A.IntegerLit):
            self.emit(f"\tCRCT {e.value}")

        elif isinstance(e, A.BoolLit):
            val = 1 if e.value else 0
            self.emit(f"\tCRCT {val}")

        elif isinstance(e, A.NameExpr):
            addr = self.lookup_addr(e.ident.name)
            self.emit(f"\tCRVL {addr}")

        elif isinstance(e, A.BinaryExpr):
            # Avalia left -> empilha, avalia right -> empilha, aplica operador
            self.expr(e.left)
            self.expr(e.right)
            opmap = {
                "+": "SOMA",
                "-": "SUBT",
                "*": "MULT",
                "/": "DIVI",
                ">": "CMMA",
                "<": "CMME",
                ">=": "CMAG",
                "<=": "CMEG",
                "==": "CMIG",
                "!=": "CMDG",
                "&&": "CONJ",
                "||": "DISJ",
            }
            instr = opmap.get(e.op, "NADA")  # 'NADA' como fallback defensivo
            self.emit(f"\t{instr}")

        elif isinstance(e, A.UnaryExpr):
            self.expr(e.right)
            if e.op == "-":
                self.emit("\tINVR")
            elif e.op == "!":
                self.emit("\tNEGA")

        elif isinstance(e, A.AssignExpr):
            # Atribuição em contexto de expressão (ex.: x = y + 1)
            addr = self.lookup_addr(e.target.ident.name)
            self.expr(e.value)
            self.emit(f"\tARMZ {addr}")

        else:
            # Nó não suportado explicitamente → no-op para não quebrar a geração
            self.emit("\tNADA")
