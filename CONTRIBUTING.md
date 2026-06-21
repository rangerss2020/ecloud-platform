# Contributing to ECloud

Thank you for your interest in contributing!

## How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Development Setup

```bash
git clone https://github.com/rangerss2020/ecloud-platform.git
cd ecloud-platform
pip install -r requirements.txt
mysql -uroot -p -e "CREATE DATABASE ecloud_platform DEFAULT CHARSET utf8mb4;"
# edit ecloud_platform/settings.py database password
python manage.py migrate
python manage.py initdata
python manage.py runserver 0.0.0.0:8000
```

## Code Style

- Follow PEP 8 for Python code
- Use Django conventions
- Keep templates clean and semantic

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
