// Проверки короткоживущего результата без сети и интерфейса.
import Foundation

@main struct StateTests {
    static func main() {
        var state = VerificationState()
        assert(!state.accept("proof", at: 0)) // Непрошенное сообщение не принимается.
        assert(state.begin(at: 0))
        assert(!state.begin(at: 1)) // Двойное нажатие не запускает вторую проверку.
        assert(!state.accept("", at: 1))
        assert(!state.accept("bad proof", at: 1))
        assert(state.accept("verification-result", at: 2))
        assert(state.result(at: 3) == "verification-result")
        assert(!state.accept("replacement", at: 4))
        assert(state.result(at: 113) == nil) // Запас к двухминутному сроку Google.
        assert(state.begin(at: 114))
        state.fail()
        assert(state.result(at: 115) == nil)
        assert(!state.begin(at: 116)) // Пауза сохраняется после ошибки.
        assert(state.begin(at: 175))
        assert(!state.accept(String(repeating: "x", count: 8193), at: 176))
        assert(!state.accept("late-result", at: 356)) // Просроченная проверка.
        print("Проверки состояния помощника: пройдены")
    }
}
