# API Loja Online — Versão Monolítica

Este projeto contém a API inteira em um único `app.py`.

A API já funciona. A proposta do exercício é reorganizar o código em uma estrutura semelhante à versão dividida.

## Tarefa dos alunos

Separar o código em arquivos como:

```text
app.py
config.py
database.py
auth.py
routes/
```

O comportamento final deve continuar igual.

## Rodando localmente

```bash
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

Linux, macOS ou WSL:

```bash
source venv/bin/activate
```

```bash
pip install -r requirements.txt
python app.py
```

## Login

```text
POST /login
```

```json
{
  "email": "admin@loja.com",
  "senha": "123456"
}
```

## Deploy no Render

Build Command:

```bash
pip install -r requirements.txt
```

Start Command:

```bash
gunicorn app:app
```

Variável de ambiente:

```text
JWT_SECRET_KEY
```

## Endpoints

```text
GET    /usuarios
GET    /usuarios/1
POST   /usuarios
PUT    /usuarios/1
DELETE /usuarios/1

GET    /categorias
GET    /categorias/1
POST   /categorias
PUT    /categorias/1
DELETE /categorias/1

GET    /produtos
GET    /produtos?categoria_id=1
GET    /produtos/1
POST   /produtos
PUT    /produtos/1
DELETE /produtos/1

GET    /pedidos
GET    /pedidos/1
POST   /pedidos
PUT    /pedidos/1/status
DELETE /pedidos/1
```

## Observação

O projeto usa SQLite para fins didáticos. No Render Free, o arquivo SQLite pode ser perdido em redeploys ou reinicializações.
