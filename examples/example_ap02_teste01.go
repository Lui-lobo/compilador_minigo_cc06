package main

/* Programa que calcula o fatorial de um número */
func main() {
    var fat int = 1;      // fatorial inicializado em 1
    var num int = 5;      // simula leitura (read(num))
    var cont int = 2;     // contador inicial

    for cont <= num {
        fat = fat * cont;
        cont = cont + 1;
    }

    fmt.Println(fat);     // imprime resultado
}

/* MEPA Esperado 

main: NADA
	AMEM 1
	CRCT 1
	ARMZ 0
	AMEM 1
	CRCT 5
	ARMZ 1
	AMEM 1
	CRCT 2
	ARMZ 2
L1: NADA
	CRVL 2
	CRVL 1
	CMEG
	DSVF L2
	CRVL 0
	CRVL 2
	MULT
	ARMZ 0
	CRVL 2
	CRCT 1
	SOMA
	ARMZ 2
	DSVS L1
L2: NADA
	CRVL 0
	ESCRV
	RETU
 
*/
