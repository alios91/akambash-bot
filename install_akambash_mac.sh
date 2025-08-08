#!/bin/bash

echo "🔧 Установка зависимостей для сборки aiohttp..."
brew install cmake openssl pyenv

echo "🐍 Установка Python 3.11 через pyenv..."
pyenv install 3.11.9
pyenv global 3.11.9

echo "📦 Создание виртуального окружения..."
python3 -m venv venv
source venv/bin/activate

echo "⚙️ Установка aiohttp с указанием путей к OpenSSL..."
LDFLAGS="-L$(brew --prefix openssl)/lib" \
CPPFLAGS="-I$(brew --prefix openssl)/include" \
pip install aiohttp

echo "📥 Установка остальных зависимостей..."
pip install -r requirements.txt

echo "✅ Готово. Чтобы запустить бота, выполни:"
echo "source venv/bin/activate && python bot.py"
