// Результат Google хранится в памяти максимум 110 секунд и не заменяется сообщениями без запроса.
import Foundation

struct VerificationState {
    private var pendingUntil: TimeInterval = 0
    private var nextAllowed: TimeInterval = 0
    private var expires: TimeInterval = 0
    private var token: String?

    mutating func begin(at now: TimeInterval) -> Bool {
        guard now >= nextAllowed, now >= pendingUntil, result(at: now) == nil else { return false }
        token = nil
        pendingUntil = now + 180
        nextAllowed = now + 60
        return true
    }
    mutating func accept(_ value: String, at now: TimeInterval) -> Bool {
        guard pendingUntil > now, !value.isEmpty, value.count <= 8192,
              !value.contains(where: { $0.isWhitespace }) else { return false }
        token = value
        expires = now + 110
        pendingUntil = 0
        return true
    }
    mutating func fail() { token = nil; pendingUntil = 0; expires = 0 }
    mutating func result(at now: TimeInterval) -> String? {
        if now >= expires { token = nil }
        return token
    }
    func canBegin(at now: TimeInterval) -> Bool { now >= nextAllowed && now >= pendingUntil && now >= expires }
}
