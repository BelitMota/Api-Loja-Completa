"""
API Loja Online — versão monolítica para exercício de refatoração.

Este arquivo contém tudo em um único app.py. A API funciona, mas a proposta é que
os alunos separem o código em app.py, config.py, database.py, auth.py e routes/.

No Render, use: gunicorn app:app
"""

import os
import sqlite3
from datetime import datetime, timedelta, timezone
import jwt
from flask import Flask, request, jsonify
from flask_cors import CORS

BASE_DIR = os.path.dirname(__file__)
DATABASE_PATH = os.path.join(BASE_DIR, "loja.db")
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "chave-local-apenas-para-aula")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 2

app = Flask(__name__)
CORS(app)


def conectar():
    conexao = sqlite3.connect(DATABASE_PATH)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao


def criar_tabelas(cursor):
    cursor.execute("CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, email TEXT NOT NULL UNIQUE, senha TEXT NOT NULL, perfil TEXT NOT NULL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS categorias (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL UNIQUE, descricao TEXT)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            descricao TEXT,
            preco REAL NOT NULL,
            estoque INTEGER NOT NULL,
            imagem TEXT,
            sku TEXT UNIQUE,
            ativo INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (categoria_id) REFERENCES categorias(id)
        )
    """)
    cursor.execute("CREATE TABLE IF NOT EXISTS pedidos (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER NOT NULL, data_criacao TEXT NOT NULL, status TEXT NOT NULL, observacao TEXT, FOREIGN KEY (usuario_id) REFERENCES usuarios(id))")
    cursor.execute("CREATE TABLE IF NOT EXISTS itens_pedido (id INTEGER PRIMARY KEY AUTOINCREMENT, pedido_id INTEGER NOT NULL, produto_id INTEGER NOT NULL, quantidade INTEGER NOT NULL, preco_unitario REAL NOT NULL, FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE CASCADE, FOREIGN KEY (produto_id) REFERENCES produtos(id))")


def contar(cursor, tabela):
    cursor.execute(f"SELECT COUNT(*) AS total FROM {tabela}")
    return cursor.fetchone()["total"]


def inserir_seed(cursor):
    if contar(cursor, "usuarios") == 0:
        cursor.executemany("INSERT INTO usuarios (nome, email, senha, perfil) VALUES (?, ?, ?, ?)", [("Administrador", "admin@loja.com", "123456", "admin"), ("Professor", "professor@loja.com", "123456", "professor"), ("Aluno Teste", "aluno@loja.com", "123456", "cliente")])
    if contar(cursor, "categorias") == 0:
        cursor.executemany("INSERT INTO categorias (nome, descricao) VALUES (?, ?)", [("Periféricos", "Mouse, teclado, webcam e itens semelhantes."), ("Computadores", "Notebooks, desktops e monitores."), ("Acessórios", "Suportes, cabos e acessórios diversos.")])
    if contar(cursor, "produtos") == 0:
        cursor.executemany("""
            INSERT INTO produtos (categoria_id, nome, descricao, preco, estoque, imagem, sku, ativo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [(1, "Mouse USB", "Mouse simples para uso diário.", 49.90, 30, "https://picsum.photos/seed/mouse/300/200", "MOU-001", 1), (1, "Teclado ABNT2", "Teclado no padrão brasileiro.", 89.90, 20, "https://picsum.photos/seed/teclado/300/200", "TEC-002", 1), (1, "Webcam Full HD", "Webcam para aulas e reuniões.", 199.90, 12, "https://picsum.photos/seed/webcam/300/200", "WEB-003", 1), (2, "Notebook Acadêmico", "Notebook para estudos e programação.", 3499.90, 8, "https://picsum.photos/seed/notebook/300/200", "NOT-004", 1), (2, "Monitor 24 polegadas", "Monitor LED para produtividade.", 799.90, 10, "https://picsum.photos/seed/monitor/300/200", "MON-005", 1), (3, "Suporte para Notebook", "Suporte ergonômico ajustável.", 129.90, 25, "https://picsum.photos/seed/suporte/300/200", "SUP-006", 1)])
    if contar(cursor, "pedidos") == 0:
        cursor.execute("INSERT INTO pedidos (usuario_id, data_criacao, status, observacao) VALUES (?, datetime('now'), ?, ?)", (3, "aberto", "Pedido inicial do aluno."))
        p1 = cursor.lastrowid
        cursor.executemany("INSERT INTO itens_pedido (pedido_id, produto_id, quantidade, preco_unitario) VALUES (?, ?, ?, ?)", [(p1, 1, 2, 49.90), (p1, 2, 1, 89.90)])
        cursor.execute("UPDATE produtos SET estoque = estoque - 2 WHERE id = 1")
        cursor.execute("UPDATE produtos SET estoque = estoque - 1 WHERE id = 2")


def iniciar_banco():
    conexao = conectar(); cursor = conexao.cursor()
    criar_tabelas(cursor); inserir_seed(cursor)
    conexao.commit(); conexao.close()


def autenticar_usuario(email, senha):
    conexao = conectar(); cursor = conexao.cursor()
    cursor.execute("SELECT id, nome, email, perfil FROM usuarios WHERE email = ? AND senha = ?", (email, senha))
    usuario = cursor.fetchone(); conexao.close(); return usuario


def gerar_token(usuario):
    payload = {"sub": str(usuario["id"]), "nome": usuario["nome"], "email": usuario["email"], "perfil": usuario["perfil"], "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def extrair_token():
    cabecalho = request.headers.get("Authorization")
    if not cabecalho: return None
    partes = cabecalho.split()
    if len(partes) != 2 or partes[0].lower() != "bearer": return None
    return partes[1]


def decodificar_token(token):
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def token_opcional():
    token = extrair_token()
    return None if token is None else decodificar_token(token)


def token_obrigatorio():
    token = extrair_token()
    if token is None: return None, (jsonify({"erro": "Token JWT não enviado"}), 401)
    payload = decodificar_token(token)
    if payload is None: return None, (jsonify({"erro": "Token JWT inválido ou expirado"}), 401)
    return payload, None


def formatar_usuario(linha, autenticado):
    u = {"id": linha["id"], "nome": linha["nome"]}
    if autenticado: u.update({"email": linha["email"], "perfil": linha["perfil"]})
    return u


def formatar_categoria(linha, autenticado):
    c = {"id": linha["id"], "nome": linha["nome"]}
    if autenticado: c.update({"descricao": linha["descricao"], "total_produtos": linha["total_produtos"]})
    return c


def formatar_produto(linha, autenticado):
    p = {"id": linha["id"], "nome": linha["nome"], "preco": linha["preco"], "imagem": linha["imagem"], "categoria": {"id": linha["categoria_id"], "nome": linha["categoria_nome"]}}
    if autenticado: p.update({"descricao": linha["descricao"], "estoque": linha["estoque"], "sku": linha["sku"], "ativo": bool(linha["ativo"])})
    return p


def consultar_produtos(where="", params=()):
    conexao = conectar(); cursor = conexao.cursor()
    cursor.execute(f"""
        SELECT produtos.id, produtos.categoria_id, categorias.nome AS categoria_nome, produtos.nome, produtos.descricao, produtos.preco, produtos.estoque, produtos.imagem, produtos.sku, produtos.ativo
        FROM produtos INNER JOIN categorias ON categorias.id = produtos.categoria_id {where} ORDER BY produtos.id
    """, params)
    rows = cursor.fetchall(); conexao.close(); return rows


def consultar_pedidos(where="", params=()):
    conexao = conectar(); cursor = conexao.cursor()
    cursor.execute(f"""
        SELECT pedidos.id, pedidos.usuario_id, usuarios.nome AS usuario_nome, usuarios.email AS usuario_email, pedidos.data_criacao, pedidos.status, pedidos.observacao, COALESCE(SUM(itens_pedido.quantidade * itens_pedido.preco_unitario), 0) AS valor_total
        FROM pedidos INNER JOIN usuarios ON usuarios.id = pedidos.usuario_id LEFT JOIN itens_pedido ON itens_pedido.pedido_id = pedidos.id
        {where}
        GROUP BY pedidos.id, pedidos.usuario_id, usuarios.nome, usuarios.email, pedidos.data_criacao, pedidos.status, pedidos.observacao ORDER BY pedidos.id
    """, params)
    rows = cursor.fetchall(); conexao.close(); return rows


def listar_itens(pedido_id):
    conexao = conectar(); cursor = conexao.cursor()
    cursor.execute("""
        SELECT itens_pedido.id, itens_pedido.produto_id, produtos.nome AS produto_nome, produtos.sku AS produto_sku, itens_pedido.quantidade, itens_pedido.preco_unitario, (itens_pedido.quantidade * itens_pedido.preco_unitario) AS subtotal
        FROM itens_pedido INNER JOIN produtos ON produtos.id = itens_pedido.produto_id WHERE itens_pedido.pedido_id = ? ORDER BY itens_pedido.id
    """, (pedido_id,))
    rows = cursor.fetchall(); conexao.close(); return rows


def formatar_pedido(pedido, autenticado):
    p = {"id": pedido["id"], "data_criacao": pedido["data_criacao"], "status": pedido["status"], "valor_total": pedido["valor_total"]}
    if autenticado:
        p["observacao"] = pedido["observacao"]
        p["usuario"] = {"id": pedido["usuario_id"], "nome": pedido["usuario_nome"], "email": pedido["usuario_email"]}
        p["itens"] = [{"id": i["id"], "produto": {"id": i["produto_id"], "nome": i["produto_nome"], "sku": i["produto_sku"]}, "quantidade": i["quantidade"], "preco_unitario": i["preco_unitario"], "subtotal": i["subtotal"]} for i in listar_itens(pedido["id"])]
    return p


@app.route("/", methods=["GET"])
def home():
    return jsonify({"mensagem": "API Loja Online funcionando", "login": "POST /login", "usuario_teste": {"email": "admin@loja.com", "senha": "123456"}, "observacao": "Versão monolítica para exercício de divisão."})


@app.route("/login", methods=["POST"])
def login():
    dados = request.get_json()
    if dados is None: return jsonify({"erro": "JSON não enviado"}), 400
    usuario = autenticar_usuario(dados.get("email"), dados.get("senha"))
    if usuario is None: return jsonify({"erro": "Email ou senha inválidos"}), 401
    return jsonify({"mensagem": "Login realizado", "tipo": "Bearer", "token": gerar_token(usuario), "usuario": formatar_usuario(usuario, True)})


@app.route("/usuarios", methods=["GET"])
def listar_usuarios():
    autenticado = token_opcional() is not None
    conexao = conectar(); cursor = conexao.cursor(); cursor.execute("SELECT id, nome, email, perfil FROM usuarios ORDER BY id")
    rows = cursor.fetchall(); conexao.close()
    return jsonify([formatar_usuario(r, autenticado) for r in rows])


@app.route("/usuarios/<int:id>", methods=["GET"])
def buscar_usuario(id):
    autenticado = token_opcional() is not None
    conexao = conectar(); cursor = conexao.cursor(); cursor.execute("SELECT id, nome, email, perfil FROM usuarios WHERE id = ?", (id,))
    row = cursor.fetchone(); conexao.close()
    if row is None: return jsonify({"erro": "Usuário não encontrado"}), 404
    return jsonify(formatar_usuario(row, autenticado))


@app.route("/usuarios", methods=["POST"])
def criar_usuario():
    payload, erro = token_obrigatorio()
    if erro is not None: return erro
    dados = request.get_json()
    if dados is None: return jsonify({"erro": "JSON não enviado"}), 400
    for campo in ["nome", "email", "senha", "perfil"]:
        if not dados.get(campo): return jsonify({"erro": f"Campo obrigatório: {campo}"}), 400
    conexao = conectar(); cursor = conexao.cursor()
    try:
        cursor.execute("INSERT INTO usuarios (nome, email, senha, perfil) VALUES (?, ?, ?, ?)", (dados["nome"], dados["email"], dados["senha"], dados["perfil"]))
        conexao.commit(); novo_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        conexao.close(); return jsonify({"erro": "E-mail já cadastrado"}), 409
    conexao.close(); return jsonify({"mensagem": "Usuário criado", "id": novo_id}), 201


@app.route("/usuarios/<int:id>", methods=["PUT"])
def atualizar_usuario(id):
    payload, erro = token_obrigatorio()
    if erro is not None: return erro
    dados = request.get_json()
    if dados is None: return jsonify({"erro": "JSON não enviado"}), 400
    conexao = conectar(); cursor = conexao.cursor()
    try:
        cursor.execute("UPDATE usuarios SET nome = ?, email = ?, senha = ?, perfil = ? WHERE id = ?", (dados.get("nome"), dados.get("email"), dados.get("senha"), dados.get("perfil"), id))
        conexao.commit(); linhas = cursor.rowcount
    except sqlite3.IntegrityError:
        conexao.close(); return jsonify({"erro": "E-mail já cadastrado"}), 409
    conexao.close()
    if linhas == 0: return jsonify({"erro": "Usuário não encontrado"}), 404
    return jsonify({"mensagem": "Usuário atualizado"})


@app.route("/usuarios/<int:id>", methods=["DELETE"])
def remover_usuario(id):
    payload, erro = token_obrigatorio()
    if erro is not None: return erro
    conexao = conectar(); cursor = conexao.cursor()
    try:
        cursor.execute("DELETE FROM usuarios WHERE id = ?", (id,)); conexao.commit(); linhas = cursor.rowcount
    except sqlite3.IntegrityError:
        conexao.close(); return jsonify({"erro": "Usuário possui pedidos vinculados"}), 409
    conexao.close()
    if linhas == 0: return jsonify({"erro": "Usuário não encontrado"}), 404
    return jsonify({"mensagem": "Usuário removido"})


@app.route("/categorias", methods=["GET"])
def listar_categorias():
    autenticado = token_opcional() is not None
    conexao = conectar(); cursor = conexao.cursor()
    cursor.execute("SELECT categorias.id, categorias.nome, categorias.descricao, COUNT(produtos.id) AS total_produtos FROM categorias LEFT JOIN produtos ON produtos.categoria_id = categorias.id GROUP BY categorias.id, categorias.nome, categorias.descricao ORDER BY categorias.id")
    rows = cursor.fetchall(); conexao.close()
    return jsonify([formatar_categoria(r, autenticado) for r in rows])


@app.route("/categorias/<int:id>", methods=["GET"])
def buscar_categoria(id):
    autenticado = token_opcional() is not None
    conexao = conectar(); cursor = conexao.cursor()
    cursor.execute("SELECT categorias.id, categorias.nome, categorias.descricao, COUNT(produtos.id) AS total_produtos FROM categorias LEFT JOIN produtos ON produtos.categoria_id = categorias.id WHERE categorias.id = ? GROUP BY categorias.id, categorias.nome, categorias.descricao", (id,))
    row = cursor.fetchone(); conexao.close()
    if row is None: return jsonify({"erro": "Categoria não encontrada"}), 404
    return jsonify(formatar_categoria(row, autenticado))


@app.route("/categorias", methods=["POST"])
def criar_categoria():
    payload, erro = token_obrigatorio()
    if erro is not None: return erro
    dados = request.get_json()
    if dados is None or not dados.get("nome"): return jsonify({"erro": "Campo obrigatório: nome"}), 400
    conexao = conectar(); cursor = conexao.cursor()
    try:
        cursor.execute("INSERT INTO categorias (nome, descricao) VALUES (?, ?)", (dados["nome"], dados.get("descricao"))); conexao.commit(); novo_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        conexao.close(); return jsonify({"erro": "Categoria já cadastrada"}), 409
    conexao.close(); return jsonify({"mensagem": "Categoria criada", "id": novo_id}), 201


@app.route("/categorias/<int:id>", methods=["PUT"])
def atualizar_categoria(id):
    payload, erro = token_obrigatorio()
    if erro is not None: return erro
    dados = request.get_json()
    if dados is None or not dados.get("nome"): return jsonify({"erro": "Campo obrigatório: nome"}), 400
    conexao = conectar(); cursor = conexao.cursor()
    try:
        cursor.execute("UPDATE categorias SET nome = ?, descricao = ? WHERE id = ?", (dados["nome"], dados.get("descricao"), id)); conexao.commit(); linhas = cursor.rowcount
    except sqlite3.IntegrityError:
        conexao.close(); return jsonify({"erro": "Categoria já cadastrada"}), 409
    conexao.close()
    if linhas == 0: return jsonify({"erro": "Categoria não encontrada"}), 404
    return jsonify({"mensagem": "Categoria atualizada"})


@app.route("/categorias/<int:id>", methods=["DELETE"])
def remover_categoria(id):
    payload, erro = token_obrigatorio()
    if erro is not None: return erro
    conexao = conectar(); cursor = conexao.cursor()
    try:
        cursor.execute("DELETE FROM categorias WHERE id = ?", (id,)); conexao.commit(); linhas = cursor.rowcount
    except sqlite3.IntegrityError:
        conexao.close(); return jsonify({"erro": "Categoria possui produtos vinculados"}), 409
    conexao.close()
    if linhas == 0: return jsonify({"erro": "Categoria não encontrada"}), 404
    return jsonify({"mensagem": "Categoria removida"})


@app.route("/produtos", methods=["GET"])
def listar_produtos():
    autenticado = token_opcional() is not None
    categoria_id = request.args.get("categoria_id")
    if categoria_id is not None:
        try: categoria_id = int(categoria_id)
        except ValueError: return jsonify({"erro": "categoria_id precisa ser inteiro"}), 400
        rows = consultar_produtos("WHERE produtos.categoria_id = ?", (categoria_id,))
    else:
        rows = consultar_produtos()
    return jsonify([formatar_produto(r, autenticado) for r in rows])


@app.route("/produtos/<int:id>", methods=["GET"])
def buscar_produto(id):
    autenticado = token_opcional() is not None
    rows = consultar_produtos("WHERE produtos.id = ?", (id,))
    if not rows: return jsonify({"erro": "Produto não encontrado"}), 404
    return jsonify(formatar_produto(rows[0], autenticado))


@app.route("/produtos", methods=["POST"])
def criar_produto():
    payload, erro = token_obrigatorio()
    if erro is not None: return erro
    dados = request.get_json()
    if dados is None: return jsonify({"erro": "JSON não enviado"}), 400
    for campo in ["categoria_id", "nome", "preco", "estoque"]:
        if dados.get(campo) is None: return jsonify({"erro": f"Campo obrigatório: {campo}"}), 400
    conexao = conectar(); cursor = conexao.cursor()
    try:
        cursor.execute("INSERT INTO produtos (categoria_id, nome, descricao, preco, estoque, imagem, sku, ativo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (dados["categoria_id"], dados["nome"], dados.get("descricao"), dados["preco"], dados["estoque"], dados.get("imagem"), dados.get("sku"), dados.get("ativo", 1)))
        conexao.commit(); novo_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        conexao.close(); return jsonify({"erro": "Categoria inexistente ou SKU já cadastrado"}), 409
    conexao.close(); return jsonify({"mensagem": "Produto criado", "id": novo_id}), 201


@app.route("/produtos/<int:id>", methods=["PUT"])
def atualizar_produto(id):
    payload, erro = token_obrigatorio()
    if erro is not None: return erro
    dados = request.get_json()
    if dados is None: return jsonify({"erro": "JSON não enviado"}), 400
    conexao = conectar(); cursor = conexao.cursor()
    try:
        cursor.execute("UPDATE produtos SET categoria_id = ?, nome = ?, descricao = ?, preco = ?, estoque = ?, imagem = ?, sku = ?, ativo = ? WHERE id = ?", (dados.get("categoria_id"), dados.get("nome"), dados.get("descricao"), dados.get("preco"), dados.get("estoque"), dados.get("imagem"), dados.get("sku"), dados.get("ativo", 1), id))
        conexao.commit(); linhas = cursor.rowcount
    except sqlite3.IntegrityError:
        conexao.close(); return jsonify({"erro": "Categoria inexistente ou SKU já cadastrado"}), 409
    conexao.close()
    if linhas == 0: return jsonify({"erro": "Produto não encontrado"}), 404
    return jsonify({"mensagem": "Produto atualizado"})


@app.route("/produtos/<int:id>", methods=["DELETE"])
def remover_produto(id):
    payload, erro = token_obrigatorio()
    if erro is not None: return erro
    conexao = conectar(); cursor = conexao.cursor()
    try:
        cursor.execute("DELETE FROM produtos WHERE id = ?", (id,)); conexao.commit(); linhas = cursor.rowcount
    except sqlite3.IntegrityError:
        conexao.close(); return jsonify({"erro": "Produto possui pedidos vinculados"}), 409
    conexao.close()
    if linhas == 0: return jsonify({"erro": "Produto não encontrado"}), 404
    return jsonify({"mensagem": "Produto removido"})


@app.route("/pedidos", methods=["GET"])
def listar_pedidos():
    autenticado = token_opcional() is not None
    return jsonify([formatar_pedido(p, autenticado) for p in consultar_pedidos()])


@app.route("/pedidos/<int:id>", methods=["GET"])
def buscar_pedido(id):
    autenticado = token_opcional() is not None
    rows = consultar_pedidos("WHERE pedidos.id = ?", (id,))
    if not rows: return jsonify({"erro": "Pedido não encontrado"}), 404
    return jsonify(formatar_pedido(rows[0], autenticado))


@app.route("/pedidos", methods=["POST"])
def criar_pedido():
    payload, erro = token_obrigatorio()
    if erro is not None: return erro
    dados = request.get_json()
    if dados is None: return jsonify({"erro": "JSON não enviado"}), 400
    if dados.get("usuario_id") is None or not isinstance(dados.get("itens"), list) or len(dados["itens"]) == 0: return jsonify({"erro": "Pedido precisa de usuario_id e itens"}), 400
    conexao = conectar(); cursor = conexao.cursor()
    cursor.execute("SELECT id FROM usuarios WHERE id = ?", (dados["usuario_id"],))
    if cursor.fetchone() is None: conexao.close(); return jsonify({"erro": "Usuário não encontrado"}), 404
    cursor.execute("INSERT INTO pedidos (usuario_id, data_criacao, status, observacao) VALUES (?, datetime('now'), ?, ?)", (dados["usuario_id"], "aberto", dados.get("observacao")))
    pedido_id = cursor.lastrowid
    for item in dados["itens"]:
        produto_id = item.get("produto_id"); quantidade = item.get("quantidade")
        if produto_id is None or quantidade is None or quantidade <= 0: conexao.rollback(); conexao.close(); return jsonify({"erro": "Item inválido"}), 400
        cursor.execute("SELECT id, preco, estoque FROM produtos WHERE id = ? AND ativo = 1", (produto_id,)); produto = cursor.fetchone()
        if produto is None: conexao.rollback(); conexao.close(); return jsonify({"erro": f"Produto {produto_id} não encontrado ou inativo"}), 400
        if produto["estoque"] < quantidade: conexao.rollback(); conexao.close(); return jsonify({"erro": f"Estoque insuficiente para produto {produto_id}"}), 400
        cursor.execute("INSERT INTO itens_pedido (pedido_id, produto_id, quantidade, preco_unitario) VALUES (?, ?, ?, ?)", (pedido_id, produto_id, quantidade, produto["preco"]))
        cursor.execute("UPDATE produtos SET estoque = estoque - ? WHERE id = ?", (quantidade, produto_id))
    conexao.commit(); conexao.close(); return jsonify({"mensagem": "Pedido criado", "id": pedido_id}), 201


@app.route("/pedidos/<int:id>/status", methods=["PUT"])
def atualizar_status(id):
    payload, erro = token_obrigatorio()
    if erro is not None: return erro
    dados = request.get_json()
    if dados is None or dados.get("status") not in ["aberto", "pago", "enviado", "cancelado"]: return jsonify({"erro": "Status inválido"}), 400
    conexao = conectar(); cursor = conexao.cursor(); cursor.execute("UPDATE pedidos SET status = ? WHERE id = ?", (dados["status"], id)); conexao.commit(); linhas = cursor.rowcount; conexao.close()
    if linhas == 0: return jsonify({"erro": "Pedido não encontrado"}), 404
    return jsonify({"mensagem": "Status atualizado"})


@app.route("/pedidos/<int:id>", methods=["DELETE"])
def remover_pedido(id):
    payload, erro = token_obrigatorio()
    if erro is not None: return erro
    conexao = conectar(); cursor = conexao.cursor(); cursor.execute("SELECT produto_id, quantidade FROM itens_pedido WHERE pedido_id = ?", (id,)); itens = cursor.fetchall()
    if not itens:
        cursor.execute("SELECT id FROM pedidos WHERE id = ?", (id,))
        if cursor.fetchone() is None: conexao.close(); return jsonify({"erro": "Pedido não encontrado"}), 404
    for item in itens: cursor.execute("UPDATE produtos SET estoque = estoque + ? WHERE id = ?", (item["quantidade"], item["produto_id"]))
    cursor.execute("DELETE FROM pedidos WHERE id = ?", (id,)); conexao.commit(); conexao.close()
    return jsonify({"mensagem": "Pedido removido e estoque devolvido"})


iniciar_banco()

if __name__ == "__main__":
    app.run(debug=True)
