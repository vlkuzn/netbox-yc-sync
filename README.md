# NetBox Yandex Cloud Sync

Утилита для синхронизации данных между Yandex Cloud и NetBox. Позволяет автоматически создавать и обновлять записи о виртуальных машинах, дисках и сетевых интерфейсах в NetBox на основе данных из Yandex Cloud.

## Особенности

- Автоматическое создание иерархии в NetBox: облако -> папка -> ВМ
- Синхронизация параметров ВМ:
  - Статус (active/offline)
  - vCPUs
  - RAM (в MB)
  - Размер диска (сумма всех дисков в MB)
- Поддержка нескольких облаков и папок
- Режим dry-run для предварительного просмотра изменений
- Структурированное логирование
- Контейнеризация через Docker

## Требования

- Python 3.8+
- NetBox 3.0+
- Доступ к API Yandex Cloud
- IAM токен для федеративного аккаунта Yandex Cloud

## Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/your-username/netbox-yc-sync.git
cd netbox-yc-sync
```

2. Создайте виртуальное окружение и установите зависимости:
```bash
python -m venv venv
source venv/bin/activate  # для Linux/Mac
# или
.\venv\Scripts\activate  # для Windows
pip install -r requirements.txt
```

3. Создайте файл `.env` с необходимыми переменными окружения:
```env
# NetBox
NETBOX_URL=https://your-netbox-instance
NETBOX_TOKEN=your-netbox-token
NETBOX_SITE=your-site-name

# Yandex Cloud
YC_IAM_TOKEN=your-iam-token
```

## Использование

### Запуск в режиме dry-run

```bash
python main.py --dry-run
```

### Запуск синхронизации

```bash
python main.py
```

### Запуск в Docker

```bash
docker build -t netbox-yc-sync .
docker run --env-file .env netbox-yc-sync
```

## Структура проекта

```
netbox-yc-sync/
├── collectors/           # Модули для сбора данных
│   ├── netbox.py        # Работа с NetBox API
│   └── yandex_cloud.py  # Работа с Yandex Cloud API
├── sync/                # Логика синхронизации
│   └── logic.py        # Сравнение и планирование действий
├── main.py             # Основной скрипт
├── logging_config.py   # Конфигурация логирования
├── requirements.txt    # Зависимости проекта
└── Dockerfile         # Конфигурация Docker
```

## Логирование

Утилита использует структурированное логирование с помощью `structlog`. Логи включают:
- Информацию о найденных ВМ в Yandex Cloud и NetBox
- Планируемые действия (создание/обновление ВМ)
- Результаты выполнения действий
- Ошибки и предупреждения

## Разработка

1. Создайте новую ветку для ваших изменений:
```bash
git checkout -b feature/your-feature-name
```

2. Внесите изменения и зафиксируйте их:
```bash
git add .
git commit -m "Description of your changes"
```

3. Отправьте изменения в репозиторий:
```bash
git push origin feature/your-feature-name
```

## Лицензия

MIT 