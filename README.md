![Минимальная версия HA пока не проверена](https://img.shields.io/badge/HA-проверяется-lightgrey)

# Управление электрическими печами Sangens в Home Assistant

## Важно

Компонент создается с применением методов обратного проектирования, поскольку официальный производитель отказался предоставить необходимую документацию. Интеграция осуществляется на ваш страх и риск, и ни разработчик, ни производитель не несут ответственности за корректность работы данного компонента. С моей стороны будут предприняты максимальные меры для того, чтобы избежать любых негативных последствий для вашего оборудования.

## Установка

### HACS

[![Установка через HACS](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration) [![Проверка HACS](https://github.com/dosent/sangens/actions/workflows/hacs.yml/badge.svg)](https://github.com/dosent/sangens/actions/workflows/hacs.yml) [![Проверка hassfest](https://github.com/dosent/sangens/actions/workflows/hassfest.yml/badge.svg)](https://github.com/dosent/sangens/actions/workflows/hassfest.yml)

## Разработка

Проект ведётся на русском языке. Правила работы находятся в [AGENTS.md](AGENTS.md).

Ветка `codex/sangens-ha-control` содержит подготовку новой интеграции для Sangens W12G с блоком Sangens 6–9. Реализация и проверка на устройстве ещё не завершены.

- [Спецификация управления](docs/superpowers/specs/2026-10-27-sangens-ha-design.md).
- [План реализации](docs/superpowers/plans/2026-10-27-sangens-ha-control.md).

Подключение будет настраиваться администратором один раз для всех пользователей HA. Карточка будет использовать локальное видео дыма; оригинальные медиафайлы приложения в публичный репозиторий не входят.
