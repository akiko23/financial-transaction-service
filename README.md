# Financial Category Analyzer
Кейс Хакатона от Центр-Инвест Банка

## 📜 Функционал
Реализован весь основной функционал, представленный в ТЗ

## 🔧 Стек технологий

- **FastAPI** — фреймворк для создания веб API серверной части приложения.
- **Redis** — хранилище данных в памяти для кэширования уведомлений.
- **SQLAlchemy** — библиотека для работы с СУБД на уровне ЯП.
- **Pydantic** — валидация и сериализация данных.
- **celery** - таск менеджер, для упрощенного межсервисного взаимодействия.
- **toml** — конфигурация сервиса.
- **PostgreSQL** — реляционная СУБД.
- **pytest** - Фрейиворк для создания тестов любого типа на python.
- **Unittest** - Стандартная библиотека python для написания unit тестов.
- **3 Layer Architecture** - набор принципов по написанию легко поддерживаемого и устойчивого к разного рода изменениям ПО (services, controllers, repositories)
- **dishka** - DI фреймворк для внедрения зависимостей через ioc_container в различные компоненты приложения.
- **uv** - all in one утилита для python проектов (virtual-venv, pip, setup-tools)

## Установка

1. Склонируйте репозиторий
```bash
git clone https://github.com/akiko23/financial-transaction-service
cd financial-transaction-service
```

2. Запустите проект с помощью docker compose
```bash
docker compose up -d
```

3. После запуска можно зайти на клиентскую часть (http://localhost:8000) 
   или Swagger (http://localhost:8000/docs)
