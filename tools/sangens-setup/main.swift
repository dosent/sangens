// Разовый помощник для общей настройки HA. Не читает данные установленного приложения.
import AppKit
import WebKit

final class SetupDelegate: NSObject, NSApplicationDelegate, WKScriptMessageHandler, WKNavigationDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var status: NSTextField!
    var beginButton: NSButton!
    var copyButton: NSButton!
    var state = VerificationState()
    var timer: Timer?
    var copiedToken: String?
    var copiedChangeCount: Int?
    var sdkReady = false
    var currentRequest: String?
    var waiting = false
    var now: TimeInterval { ProcessInfo.processInfo.systemUptime }

    func applicationDidFinishLaunching(_ notification: Notification) {
        let menu = NSMenu()
        let item = NSMenuItem(); menu.addItem(item)
        let submenu = NSMenu(); submenu.addItem(withTitle: "Завершить", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        item.submenu = submenu; NSApplication.shared.mainMenu = menu
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 700, height: 620), styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "Sangens — разовая проверка для Home Assistant"
        window.minSize = NSSize(width: 600, height: 540)
        let root = NSStackView(); root.orientation = .vertical; root.spacing = 14; root.edgeInsets = NSEdgeInsets(top: 22, left: 22, bottom: 22, right: 22)
        root.translatesAutoresizingMaskIntoConstraints = false
        window.contentView!.addSubview(root)
        NSLayoutConstraint.activate([root.leadingAnchor.constraint(equalTo: window.contentView!.leadingAnchor),root.trailingAnchor.constraint(equalTo: window.contentView!.trailingAnchor),root.topAnchor.constraint(equalTo: window.contentView!.topAnchor),root.bottomAnchor.constraint(equalTo: window.contentView!.bottomAnchor)])
        let heading = NSTextField(labelWithString: "Подключим печь к вашему дому")
        heading.font = .boldSystemFont(ofSize: 23); root.addArrangedSubview(heading)
        let description = NSTextField(wrappingLabelWithString: "Неофициальный помощник воспроизводит проверку Google во встроенном окне приложения Sangens. Он не запрашивает почту, код из письма или пароль. После проверки скопируйте результат и сразу вставьте его в форму HA.")
        description.font = .systemFont(ofSize: 14); root.addArrangedSubview(description)
        let buttons = NSStackView(); buttons.spacing = 12
        beginButton = NSButton(title: "Пройти проверку", target: self, action: #selector(begin)); beginButton.isEnabled = false
        copyButton = NSButton(title: "Скопировать результат", target: self, action: #selector(copyResult)); copyButton.isEnabled = false
        buttons.addArrangedSubview(beginButton); buttons.addArrangedSubview(copyButton)
        buttons.addArrangedSubview(NSButton(title: "Перезагрузить", target: self, action: #selector(reloadPage)))
        root.addArrangedSubview(buttons)
        status = NSTextField(wrappingLabelWithString: "Загрузка Google reCAPTCHA…"); root.addArrangedSubview(status)
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        configuration.userContentController.add(self, name: "captcha")
        web = WKWebView(frame: .zero, configuration: configuration)
        web.navigationDelegate = self
        root.addArrangedSubview(web)
        web.widthAnchor.constraint(equalTo: root.widthAnchor, constant: -44).isActive = true
        web.heightAnchor.constraint(greaterThanOrEqualToConstant: 280).isActive = true
        loadPage()
        timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in self?.tick() }
        window.center(); window.makeKeyAndOrderFront(nil); NSApplication.shared.activate(ignoringOtherApps: true)
    }
    func loadPage() {
        guard let path = Bundle.main.url(forResource: "captcha", withExtension: "html"), let html = try? String(contentsOf: path, encoding: .utf8) else {
            status.stringValue = "Не найден файл проверки в приложении."; window.center(); window.makeKeyAndOrderFront(nil); return
        }
        // Такой baseURL использует исходный мобильный WebView; никакой подмены ответа проверки нет.
        web.loadHTMLString(html, baseURL: URL(string: "https://api.sangens.com/"))
    }
    @objc func reloadPage() {
        clearClipboard(); state.fail(); currentRequest = nil; waiting = false; sdkReady = false
        beginButton.isEnabled = false; copyButton.isEnabled = false
        status.stringValue = "Загрузка Google reCAPTCHA…"
        loadPage()
    }
    @objc func begin() {
        guard sdkReady, state.begin(at: now) else { return }
        clearClipboard(); beginButton.isEnabled = false; copyButton.isEnabled = false
        status.stringValue = "Проверка выполняется. Если появится задание Google, выполните его внизу."
        currentRequest = UUID().uuidString
        waiting = true
        web.evaluateJavaScript("beginVerification('\(currentRequest!)')") { [weak self] _, error in
            if error != nil { self?.failed() }
        }
    }
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.frameInfo.isMainFrame, message.frameInfo.securityOrigin.host == "api.sangens.com",
              let data = message.body as? [String: String], let kind = data["kind"] else { return }
        if kind == "ready" { sdkReady = true; beginButton.isEnabled = state.canBegin(at: now); status.stringValue = "Готово. Нажмите «Пройти проверку»." }
        else if kind == "sdk-error" { status.stringValue = "Не удалось загрузить Google reCAPTCHA. Проверьте сеть и нажмите «Перезагрузить»." }
        else if data["request"] != currentRequest { return }
        else if kind == "result", let value = data["value"], state.accept(value, at: now) {
            waiting = false
            copyButton.isEnabled = true
            status.stringValue = "Результат получен. Скопируйте его и вставьте в HA в течение 110 секунд. Это ещё не подтверждение входа в Sangens."
        } else if kind == "error" { failed() }
    }
    func failed() {
        state.fail(); waiting = false; currentRequest = nil; copyButton.isEnabled = false
        status.stringValue = "Проверка не завершилась. Автоповтора нет. Проверьте сеть; новая попытка доступна после паузы."
    }
    @objc func copyResult() {
        guard let result = state.result(at: now) else { return }
        let clipboard = NSPasteboard.general
        clipboard.clearContents(); clipboard.setString(result, forType: .string)
        copiedToken = result; copiedChangeCount = clipboard.changeCount
        status.stringValue = "Скопировано. Вставьте результат в поле «Результат проверки reCAPTCHA» в HA и нажмите «Подтвердить»."
    }
    func clearClipboard() {
        let clipboard = NSPasteboard.general
        if let count = copiedChangeCount, clipboard.changeCount == count,
           clipboard.string(forType: .string) == copiedToken { clipboard.clearContents() }
        copiedToken = nil; copiedChangeCount = nil
    }
    func tick() {
        if waiting && state.canBegin(at: now) { failed() }
        if state.result(at: now) == nil, copyButton.isEnabled {
            copyButton.isEnabled = false; clearClipboard()
            status.stringValue = "Срок результата истёк. Для продолжения нужна новая ручная проверка."
        }
        beginButton.isEnabled = sdkReady && state.canBegin(at: now)
    }
    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        // Ссылки политики открываются отдельно и не уничтожают локальную страницу проверки.
        if navigationAction.navigationType == .linkActivated,
           navigationAction.targetFrame?.isMainFrame != false,
           let url = navigationAction.request.url {
            if url.scheme == "https" { NSWorkspace.shared.open(url) }
            decisionHandler(.cancel)
            return
        }
        decisionHandler(.allow)
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        status.stringValue = "Не удалось загрузить страницу Google. Проверьте подключение к интернету."
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
    func applicationWillTerminate(_ notification: Notification) { timer?.invalidate(); state.fail(); clearClipboard() }
}
let application = NSApplication.shared
let delegate = SetupDelegate()
application.delegate = delegate
application.setActivationPolicy(.regular)
application.run()
