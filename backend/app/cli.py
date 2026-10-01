"""Comandos administrativos executados no servidor.

Uso:
    python -m app.cli create-admin --email admin@empresa.com --name "Nome"

A senha é pedida no terminal (não aparece no histórico do shell).
"""

import argparse
import getpass
import sys

from pydantic import ValidationError

from app.core.errors import AppError
from app.db.session import get_sessionmaker
from app.schemas.admin import AdminCreate
from app.services import admin_service, audit


def create_admin(email: str, name: str) -> int:
    password = getpass.getpass("Senha: ")
    if password != getpass.getpass("Confirme a senha: "):
        print("As senhas não conferem.", file=sys.stderr)
        return 1
    try:
        data = AdminCreate(email=email, name=name, password=password)
    except ValidationError as exc:
        print(exc, file=sys.stderr)
        return 1
    with get_sessionmaker()() as db:
        try:
            admin = admin_service.create(db, data, audit.SYSTEM)
        except AppError as exc:
            print(exc.message, file=sys.stderr)
            return 1
    print(f"Administrador criado (id {admin.id}).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-admin", help="Cria um administrador")
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    args = parser.parse_args(argv)
    if args.command == "create-admin":
        return create_admin(args.email, args.name)
    return 2


if __name__ == "__main__":
    sys.exit(main())
