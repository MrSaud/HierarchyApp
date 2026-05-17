# Production deploy (server)

Run on the app host after changes are merged to `main`.

```bash
cd /var/www/hierarchyapp

git pull origin main

source .venv/bin/activate

pip install -r requirements.txt

python manage.py migrate

python manage.py collectstatic --noinput

sudo systemctl restart hierarchyapp

sudo systemctl reload nginx
```

## Checklist

1. **Pull** — latest code from `main`
2. **venv** — activate project virtualenv
3. **Dependencies** — install/update Python packages
4. **Database** — apply migrations
5. **Static files** — collect into `STATIC_ROOT`
6. **App** — restart Gunicorn/uWSGI (or whatever `hierarchyapp` unit runs)
7. **Nginx** — reload config (no full restart usually needed)

## Optional

- `python manage.py check` — before restart
- `sudo systemctl status hierarchyapp` — confirm app is running
- `sudo journalctl -u hierarchyapp -n 50 --no-pager` — if restart fails
