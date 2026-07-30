<!-- handwritten -->
To start the service: 
`docker compose up`

To set up to run django commands locally
```
brew install mise
echo 'eval "$(mise activate zsh)"' >> ~/.zshrc
exec zsh
pip install django-admin
```

To view/edit project management issues:
```
pip install lattice-tracker
lattice dashboard
```

To view the local database (assuming defaults)
`psql postgres://hexmodal:hexmodal@localhost:5433/hexmodal`

## API authentication

The API uses DRF token auth; every request needs a token. One-time setup
(drop the `docker compose exec web` prefix to run locally instead):
```
docker compose exec web python manage.py migrate            # creates the token table
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py drf_create_token <username>
```

Requests send the header: `Authorization: Token <key>`