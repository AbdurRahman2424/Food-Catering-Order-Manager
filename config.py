import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE_PATH = os.path.join(BASE_DIR, '.env')

DEFAULT_ENV_VALUES = {
    'MYSQL_HOST': 'localhost',
    'MYSQL_USER': 'root',
    'MYSQL_PASSWORD': '',
    'MYSQL_DB': 'catering_db',
    'MYSQL_PORT': '3306',
    'SECRET_KEY': 'dev_secret_key_123',
    'GROQ_API_KEY_1': '',
    'GROQ_API_KEY_2': '',
    'GROQ_MODEL': 'llama-3.3-70b-versatile',
    'OPENROUTER_API_KEY_1': '',
    'OPENROUTER_API_KEY_2': '',
    'OPENROUTER_MODEL': 'openai/gpt-4.1-mini'
}

def ensure_env_file():
    if os.path.exists(ENV_FILE_PATH):
        return

    lines = [f'{key}={value}' for key, value in DEFAULT_ENV_VALUES.items()]
    with open(ENV_FILE_PATH, 'w', encoding='utf-8') as env_file:
        env_file.write('\n'.join(lines) + '\n')

def load_env_file():
    env_values = {}
    if not os.path.exists(ENV_FILE_PATH):
        return env_values

    with open(ENV_FILE_PATH, 'r', encoding='utf-8') as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            env_values[key.strip()] = value.strip()

    return env_values

def get_env_value(key):
    if key in os.environ:
        return os.environ[key]
    file_values = load_env_file()
    return file_values.get(key, DEFAULT_ENV_VALUES.get(key, ''))

class Config:
    MYSQL_HOST = get_env_value('MYSQL_HOST')
    MYSQL_USER = get_env_value('MYSQL_USER')
    MYSQL_PASSWORD = get_env_value('MYSQL_PASSWORD')
    MYSQL_DB = get_env_value('MYSQL_DB')
    MYSQL_PORT = get_env_value('MYSQL_PORT')
    SECRET_KEY = get_env_value('SECRET_KEY')

    GROQ_API_KEY_1 = get_env_value('GROQ_API_KEY_1')
    GROQ_API_KEY_2 = get_env_value('GROQ_API_KEY_2')
    GROQ_MODEL = get_env_value('GROQ_MODEL')

    OPENROUTER_API_KEY_1 = get_env_value('OPENROUTER_API_KEY_1')
    OPENROUTER_API_KEY_2 = get_env_value('OPENROUTER_API_KEY_2')
    OPENROUTER_MODEL = get_env_value('OPENROUTER_MODEL')
