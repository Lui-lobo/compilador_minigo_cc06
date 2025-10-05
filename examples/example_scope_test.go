package main

/* Teste de escopos e sombreamento */
func main() {
    var x int = 10;    // variável no escopo externo

    if true {
        var x int = 20;    // nova variável no escopo interno (sombra a externa)
        fmt.Println(x);    // deve imprimir 20
    }

    fmt.Println(x);        // deve imprimir 10 (a variável externa)
}

/* Codigo MEPA esperado
main: NADA
        AMEM 1
        CRCT 10
        ARMZ 0
        CRCT 1
        DSVF L1
        AMEM 1
        CRCT 20
        ARMZ 1
        CRVL 1
        ESCRV
        DMEM 1
        DSVS L2
L1: NADA
L2: NADA
        CRVL 0
        ESCRV
        RETU
*/
