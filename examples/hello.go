package main

func soma(a int, b int) int {
    return a + b
}

func main() {
    var x int = 10;
    var y float64 = 3.5e1;
    var s string = "hello\nworld";
	y := x + 5;
    if x < 20 && y >= 10 {
        x++
    } else {
        x = x - 1
    }
    fmt.Println(s, soma(x, 2));
}