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